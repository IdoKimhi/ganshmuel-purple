import os
import io
from datetime import datetime
from typing import Optional, Dict, Any, List
from flask import Flask, request, jsonify, send_file
import pymysql
from pymysql.err import IntegrityError
import requests
from openpyxl import load_workbook, Workbook

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "12345678"),
    "database": os.environ.get("DB_NAME", "billdb"),
    "port": int(os.environ.get("DB_PORT", 3306)),
}

# Base URL of Weight service, e.g. "http://weight:5000"
WEIGHT_SERVICE_URL = os.environ.get("WEIGHT_SERVICE_URL", "http://weight:5000")

# Directory inside container where rates files live (mounted volume)
RATES_DIR = os.environ.get("RATES_DIR", "/in")


def create_app() -> Flask:
    app = Flask(__name__)

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------

    def get_db_connection():
        return pymysql.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            port=DB_CONFIG["port"],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )

    def parse_datetime_param(name: str) -> str:
        """
        Parse t1/t2 from query: yyyymmddhhmmss.
        Defaults:
        - from: 1st of month at 000000
        - to:   now
        """
        value = request.args.get(name)
        if value:
            return value

        now = datetime.now()
        if name == "from":
            dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            dt = now
        return dt.strftime("%Y%m%d%H%M%S")

    def call_weight_service(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Call Weight microservice (GET only, as per spec).
        """
        url = WEIGHT_SERVICE_URL.rstrip("/") + path
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()

    # ---------------------------------------------------------------
    # GET /health
    # ---------------------------------------------------------------
    @app.route("/health", methods=["GET"])
    def health():
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            return "OK", 200
        except Exception as e:
            # Failure of Weight is NOT relevant for Billing health
            return jsonify({"status": "Failure", "details": str(e)}), 500

    # ---------------------------------------------------------------
    # Providers
    # ---------------------------------------------------------------
    @app.route("/provider", methods=["POST"])
    def create_provider():
        return jsonify({"id": "placeholder"}), 201

    @app.route("/provider/<int:provider_id>", methods=["PUT"])
    def update_provider(provider_id: int):
        return jsonify({"id": provider_id, "name": "placeholder"}), 200

    # ---------------------------------------------------------------
    # Rates
    # ---------------------------------------------------------------

    def replace_all_rates(rates: List[Dict[str, Any]]) -> None:
        """
        Delete all rows from Rates and insert the provided ones.
        Each item: { "product_id": str, "rate": int, "scope": str }
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM Rates")
                sql = "INSERT INTO Rates (product_id, rate, scope) VALUES (%s, %s, %s)"
                for r in rates:
                    cur.execute(sql, (r["product_id"], r["rate"], r["scope"]))
        finally:
            conn.close()

    @app.route("/rates", methods=["POST"])
    def upload_rates():
        """
        POST /rates
        - file=<filename> (query string)
        Reads Excel from "/in/<filename>" inside container.
        Rate Excel must have columns: Product, Rate, Scope
        - Product : product id (e.g. "Navel")
        - Rate    : integer (agorot)
        - Scope   : "ALL" or provider id (as string)
        New rates overwrite old ones.
        """
        filename = request.args.get("file")
        if not filename:
            return jsonify({"error": "file parameter is required, e.g. ?file=rates.xlsx"}), 400

        rates_path = os.path.join(RATES_DIR, filename)
        if not os.path.isfile(rates_path):
            return jsonify({"error": "file not found in /in", "path": rates_path}), 404

        try:
            wb = load_workbook(rates_path, data_only=True)
            ws = wb.active

            header_row = next(ws.iter_rows(min_row=1, max_row=1))
            headers = [
                (str(cell.value).strip() if cell.value is not None else "")
                for cell in header_row
            ]
            header_map = {h.lower(): i for i, h in enumerate(headers)}

            required = ["product", "rate", "scope"]
            for col in required:
                if col not in header_map:
                    return jsonify({"error": f"missing '{col}' column in header"}), 400

            rates: List[Dict[str, Any]] = []
            for row in ws.iter_rows(min_row=2):
                product_cell = row[header_map["product"]].value
                rate_cell = row[header_map["rate"]].value
                scope_cell = row[header_map["scope"]].value

                # skip empty rows
                if product_cell is None and rate_cell is None and scope_cell is None:
                    continue

                product_id = str(product_cell).strip()
                try:
                    rate_int = int(rate_cell)
                except (TypeError, ValueError):
                    return jsonify({"error": f"invalid rate value: {rate_cell!r}"}), 400

                scope = "ALL" if scope_cell is None else str(scope_cell).strip()

                rates.append(
                    {
                        "product_id": product_id,
                        "rate": rate_int,
                        "scope": scope,
                    }
                )

            replace_all_rates(rates)
        except Exception as e:
            return jsonify({"error": "failed to process rates file", "details": str(e)}), 400

        return jsonify({"inserted": len(rates)}), 201

    # ---------------------------------------------------------------
    # Trucks
    # ---------------------------------------------------------------
    @app.route("/truck", methods=["POST"])
    def create_truck():
        return jsonify({"id": "TRUCK123", "provider": 0}), 201

    @app.route("/truck/<truck_id>", methods=["PUT"])
    def update_truck(truck_id: str):
        return jsonify({"id": truck_id, "provider": 0}), 200

    @app.route("/truck/<truck_id>", methods=["GET"])
    def get_truck_info(truck_id: str):
        return jsonify({
            "id": truck_id,
            "tara": 0,
            "sessions": [],
            "placeholder": True
        }), 200

    # ---------------------------------------------------------------
    # Billing
    # ---------------------------------------------------------------
    
    def get_provider(provider_id: int) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM Provider WHERE id = %s", (provider_id,))
                return cur.fetchone()
        finally:
            conn.close()

    def get_trucks_for_provider(provider_id: int) -> List[str]:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM Trucks WHERE provider_id = %s", (provider_id,))
                rows = cur.fetchall()
                return [row["id"] for row in rows]
        finally:
            conn.close()

    def get_all_rates() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT product_id, rate, scope FROM Rates")
                return cur.fetchall()
        finally:
            conn.close()

    def select_rate_for_product(
        rates: List[Dict[str, Any]], product_id: str, provider_id: int
    ) -> Optional[int]:
        """
        Scoped rate has higher precedence than ALL.
        """
        scoped_rate = None
        all_rate = None
        for r in rates:
            if r["product_id"] != product_id:
                continue
            if r["scope"] == "ALL":
                if all_rate is None:
                    all_rate = r["rate"]
            elif str(r["scope"]) == str(provider_id):
                if scoped_rate is None:
                    scoped_rate = r["rate"]
        return scoped_rate if scoped_rate is not None else all_rate

    @app.route("/bill/<int:provider_id>", methods=["GET"])
    def get_bill(provider_id: int):
        """
        GET /bill/<id>?from=t1&to=t2
        - id is provider id
        Returns:
        {
          "id": <str>,
          "name": <str>,
          "from": <str>,
          "to": <str>,
          "truckCount": <int>,
          "sessionCount": <int>,
          "products": [
            {
              "product": <str>,
              "count": <int>,   // number of sessions
              "amount": <int>,  // total kg
              "rate": <int>,    // agorot
              "pay": <int>      // agorot
            },
            ...
          ],
          "total": <int>       // agorot
        }
        """
        provider = get_provider(provider_id)
        if not provider:
            return jsonify({"error": "provider not found"}), 404

        t1 = parse_datetime_param("from")
        t2 = parse_datetime_param("to")

        truck_ids = get_trucks_for_provider(provider_id)
        rates = get_all_rates()

        product_stats: Dict[str, Dict[str, Any]] = {}
        total_sessions = 0

        # For each truck, get sessions from Weight via GET /item/<truck>
        for truck_id in truck_ids:
            try:
                item = call_weight_service(
                    f"/item/{truck_id}", params={"from": t1, "to": t2}
                )
            except requests.exceptions.RequestException as e:
                return jsonify({"error": "failed to reach Weight service", "details": str(e)}), 502

            sessions = item.get("sessions") or []
            for session_id in sessions:
                try:
                    session_data = call_weight_service(f"/session/{session_id}")
                except requests.exceptions.RequestException as e:
                    return jsonify({"error": "failed to reach Weight service", "details": str(e)}), 502

                neto = session_data.get("neto")
                if neto == "na" or neto is None:
                    continue

                try:
                    neto_int = int(neto)
                except (TypeError, ValueError):
                    continue

                product_id = (
                    session_data.get("produce")
                    or session_data.get("product")
                )
                if not product_id:
                    continue

                total_sessions += 1
                if product_id not in product_stats:
                    product_stats[product_id] = {
                        "product": product_id,
                        "count": 0,
                        "amount": 0,
                        "rate": 0,
                        "pay": 0,
                    }

                stat = product_stats[product_id]
                stat["count"] += 1
                stat["amount"] += neto_int

        # Apply rates, compute pay per product and total
        total_pay = 0
        for product_id, stat in product_stats.items():
            rate = select_rate_for_product(rates, product_id, provider_id)
            if rate is None:
                rate = 0
            stat["rate"] = int(rate)
            stat["pay"] = int(stat["amount"]) * int(rate)
            total_pay += stat["pay"]

        response = {
            "id": str(provider["id"]),
            "name": provider["name"],
            "from": t1,
            "to": t2,
            "truckCount": len(truck_ids),
            "sessionCount": total_sessions,
            "products": list(product_stats.values()),
            "total": total_pay,
        }
        return jsonify(response), 200

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
