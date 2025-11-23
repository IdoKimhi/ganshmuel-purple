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
        return "OK (placeholder)", 200

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
    @app.route("/rates", methods=["POST"])
    def upload_rates():
        return jsonify({"inserted": 0, "placeholder": True}), 201

    @app.route("/rates", methods=["GET"])
    def download_rates():
        return jsonify({"placeholder": "excel file would be here"}), 200

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
    @app.route("/bill/<int:provider_id>", methods=["GET"])
    def get_bill(provider_id: int):
        return jsonify({
            "id": str(provider_id),
            "name": "placeholder-provider",
            "from": "YYYYMMDDHHMMSS",
            "to": "YYYYMMDDHHMMSS",
            "truckCount": 0,
            "sessionCount": 0,
            "products": [],
            "total": 0,
            "placeholder": True
        }), 200

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

