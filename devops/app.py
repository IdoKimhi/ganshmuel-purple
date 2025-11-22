from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200


@app.route("/webhookcallback", methods=["POST"])
def hook():
    print("Received GitHub Webhook Headers:", request.headers)
    print("Received GitHub Webhook JSON:", request.get_json(silent=True))
    return "Webhook Received by Flask Dev Server", 200


if __name__ == '__main__':
    # Flask app will run on port 8000 (standard for a simple server process)
    app.run(host='0.0.0.0', port=8080)