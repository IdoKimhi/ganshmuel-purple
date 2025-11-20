from flask import Flask, jsonify, request
import uuid

app = Flask(__name__)


# -------------------------------------
# HEALTH
# -------------------------------------
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "OK"}), 200


# -------------------------------------
# PROVIDER
# -------------------------------------
@app.route("/provider", methods=["POST"])
def create_provider():
    data = request.get_json()

    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400

    # TODO: IMPLEMENT - insert provider into DB
    provider_id = str(uuid.uuid4())

    return jsonify({"id": provider_id}), 201


@app.route("/provider/<id>", methods=["PUT"])
def update_provider(id):
    data = request.get_json()

    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400

    # TODO: IMPLEMENT - update provider name in DB
    # TODO: IMPLEMENT - return 404 if provider not found

    return jsonify({"id": id, "name": data["name"]}), 200


# -------------------------------------
# RATES
# -------------------------------------
@app.route("/rates", methods=["POST"])
def upload_rates():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    file = request.files["file"]

    # TODO: IMPLEMENT - process and store the uploaded Excel file

    return jsonify({"filename": file.filename}), 200


@app.route("/rates", methods=["GET"])
def download_rates():
    # TODO: IMPLEMENT - return stored rates Excel file

    return jsonify({"message": "rates file placeholder"}), 200


# -------------------------------------
# TRUCK
# -------------------------------------
@app.route("/truck", methods=["POST"])
def create_truck():
    data = request.get_json()

    if not data or "id" not in data or "provider_id" not in data:
        return jsonify({"error": "id and provider_id are required"}), 400

    # TODO: IMPLEMENT - insert truck into DB
    # TODO: IMPLEMENT - check provider exists

    return jsonify({
        "id": data["id"],
        "provider_id": data["provider_id"]
    }), 201


@app.route("/truck/<id>", methods=["PUT"])
def update_truck(id):
    data = request.get_json()

    if not data or "provider_id" not in data:
        return jsonify({"error": "provider_id is required"}), 400

    # TODO: IMPLEMENT - update truck provider mapping in DB
    # TODO: IMPLEMENT - return 404 if truck not found

    return jsonify({
        "id": id,
        "provider_id": data["provider_id"]
    }), 200


@app.route("/truck/<id>", methods=["GET"])
def get_truck(id):
    # TODO: IMPLEMENT - fetch last known tara + sessions from weight microservice

    return jsonify({
        "id": id,
        "tara": "placeholder",
        "sessions": []
    }), 200


# -------------------------------------
# BILL
# -------------------------------------
@app.route("/bill/<provider_id>", methods=["GET"])
def get_bill(provider_id):
    # TODO: IMPLEMENT - gather trucks from DB
    # TODO: IMPLEMENT - call weight microservice for sessions + neto weights
    # TODO: IMPLEMENT - group products and calculate pay using rates

    return jsonify({
        "id": provider_id,
        "name": "placeholder provider",
        "from": request.args.get("from", "placeholder"),
        "to": request.args.get("to", "placeholder"),
        "truckCount": 0,
        "sessionCount": 0,
        "products": [],
        "total": 0
    }), 200


# -------------------------------------
# MAIN
# -------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
