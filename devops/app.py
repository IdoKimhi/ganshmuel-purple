from flask import Flask, request, jsonify
# Import the function from your new file
from email_service import send_notification_email, send_simple_alert_email
import json
import os
import subprocess

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

@app.route('/trigger', methods=['POST'])
def trigger_handler():
    # Check for json content type
    if not request.is_json:
        return jsonify({"message": "Content-Type must be application/json"}), 400

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
    ref = data.get("ref", "")            # e.g. "refs/heads/devops"
    branch = ref.split("/")[-1] if ref else "unknown"
    print(f"Branch pushed: {branch}")

#    try:
 #       print(f"Running deploy script for branch: {branch}")
  #      result = subprocess.run(
   #         ["bash", "deploy.sh", branch],
    #        capture_output=True,
     #       text=True
      #  )
       # print("--- Deploy Script Output ---")
        #print(result.stdout)
        #print(result.stderr)
    #except Exception as e:
     #   print(f"Error running deploy script: {e}")
      #  return jsonify({"message": "Error running deploy script"}), 500


        #logic goes here, if action == 'created':...
    return jsonify({"message": "Webhook successfully processed"}), 200

@app.route('/mailtest', methods=['POST'])
def mail_test():
# Check for JSON content type
    if not request.is_json:
        return jsonify ({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    
    # 1. Extract Pusher Username
    pusher_data = data.get('pusher', {})
    pusher_username = pusher_data.get('name', 'UNKNOWN_USER')
    
    # 2. Extract Branch Name (Default to 'main' for simulation)
    # In a real push, 'ref' is "refs/heads/branch_name"
    ref = data.get('ref', 'refs/heads/main')
    branch_name = ref.split('/')[-1] # Extracts 'main' from 'refs/heads/main'

    print("--- Mail Test Webhook Received ---")
    print(f"Simulated Branch: {branch_name}")
    print(f"Simulated User: {pusher_username}")
    print("----------------------------------")
    
    # Send the test email using the new function
    try:
        send_simple_alert_email(branch_name, pusher_username)
        return jsonify({
            "message": "Mail test successfully processed and email sent",
            "branch": branch_name,
            "user": pusher_username
        }), 200
    except Exception as e:
        print(f"Error during email send: {e}")
        return jsonify({"message": f"Failed to send test email: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
