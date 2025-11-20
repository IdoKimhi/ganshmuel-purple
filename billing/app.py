from flask import Flask, jsonify, request
import uuid
import db  # Assume db is a module that handles database operations

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "OK"}), 200


@app.route("/provider", methods=["POST"])
def create_provider():
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400
    provider_id = str(uuid.uuid4())
    return jsonify({"id": provider_id}), 201



@app.route("/provider/<int:provider_id>", methods=["PUT"])
def update_provider(provider_id):
    data = request.get_json()
    
    # Validate request
    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400
    name = data["name"]
    if not name or name.strip() == "":
        return jsonify({"error": "name cannot be empty"}), 400
    existing_provider = db.get_provider(provider_id)
    if existing_provider is None:
        return jsonify({"error": "Provider not found"}), 404
    success = db.update_provider(provider_id, name)
    if not success:
        return jsonify({"error": "Failed to update provider"}), 500
    return jsonify({"success": True}), 200


@app.route("/rates", methods=["POST"])
def upload_rates():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400
    file = request.files["file"]
    return jsonify({"message": "rates uploaded", "filename": file.filename}), 200




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
