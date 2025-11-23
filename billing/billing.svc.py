import os
from flask import Flask, request, jsonify

def create_app():
    app = Flask(__name__)

    # ---------------------------------------------------------------
    # Helpers (placeholders)
    # ---------------------------------------------------------------

    def get_db_connection():
        return None  # placeholder

    def parse_datetime_param(name: str) -> str:
        return "YYYYMMDDHHMMSS"  # placeholder

    def call_weight_service(path: str, params=None):
        return {"placeholder": True}  # placeholder

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

