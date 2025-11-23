from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

@app.route('/trigger', methods=['POST'])
def trigger_handler():
#check for json content type
    if not request.is_json:
        return jsonify ({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    action = data.get('action')
    pusher_data = data.get('pusher')
    repository_data = data.get('repository', {})
    branches_url = repository_data.get('branches_url')

    #process the extracted data

    if action and pusher_data and branches_url:
        pusher_username = pusher_data.get('name', 'N/A')
        print("--- GitHub Webhook Received ---")
        print(f"Action: **{action}**")
        print(f"Pusher: **{pusher_username}**")
        print(f"Branches URL: **{branches_url}**")
        print("-------------------------------")

        #logic goes here, if action == 'created':...
        return jsonify({"message": "Webhook successfully processed"}), 200
    else:
        print(f"Error: Missing data in payload. Action: {action}, Pusher: {pusher_data is not None}, Branches URL: {branches_url}")
        return jsonify({"message": "Missing required data in payload"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
