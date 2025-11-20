from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/provider", methods=["POST"])
def create_provider():
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400
    provider_id = str(uuid.uuid4())
    return jsonify({"id": provider_id}), 201

@app.route("/provider/<id>", methods=["PUT"])
def update_provider(id):
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "name is required"}), 400
    return jsonify({"id": id, "name": data["name"]}), 200


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
