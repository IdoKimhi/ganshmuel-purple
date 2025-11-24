from flask import Flask, request, jsonify
from email_service import send_notification_email, send_simple_alert_email, send_team_notification
#from self_update import trigger_update_async 
import json
import os
import subprocess
import threading
from dotenv import load_dotenv

load_dotenv(dotenv_path='recipient_config.env')

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

@app.route('/trigger', methods=['POST'])
def trigger_handler():
    # Check for JSON content type
    if not request.is_json:
        return jsonify({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    
    # Extract metadata
    pusher_data = data.get('pusher', {})
    pusher_username = pusher_data.get('name', 'UNKNOWN_USER')

    ref = data.get("ref", "")
    branch = ref.split("/")[-1] if ref.startswith("refs/heads/") else "unknown"

    action = data.get('action', 'N/A')
    repository_data = data.get('repository', {})
    branches_url = repository_data.get('branches_url', 'N/A')

    # Logging for visibility
    print("--- GitHub Webhook Received ---")
    print(f"Action: {action}")
    print(f"Pusher: {pusher_username}")
    print(f"Branch pushed: {branch}")
    print(f"Branches URL: {branches_url}")
    print("-------------------------------")

    # ============================================================
    # SPECIAL BEHAVIOR FOR BRANCH 'dev' (Send DevOps Team Email)
    # ============================================================
    if branch == 'dev':
        DEVOPS_EMAILS = [e.strip() for e in os.getenv('DEVOPS_TEAM_EMAILS', '').split(',') if e.strip()]

        if not DEVOPS_EMAILS:
            print("ERROR: DEVOPS_TEAM_EMAILS is not configured. Cannot send production email.")
        else:
            print(f"Sending production alert to DevOps team: {DEVOPS_EMAILS}")
            try:
                send_team_notification(
                    branch_name=branch,
                    pusher_username=pusher_username,
                    recipient_emails=DEVOPS_EMAILS
                )
                print("Production notification sent to DevOps team successfully!")
            except Exception as e:
                print(f"ERROR: Failed to send DevOps team notification: {e}")

    # ============================================================
    # RUN CI PIPELINE (deploy.sh)
    # ============================================================
    try:
        print(f"Running deploy script for branch: {branch}")
        result = subprocess.run(
            ["bash", "deploy.sh", branch],
            capture_output=True,
            text=True
        )

        print("--- Deploy Script Output ---")
        print(result.stdout)
        print(result.stderr)

    except Exception as e:
        print(f"Error running deploy script: {e}")
        return jsonify({"message": "Error running deploy script"}), 500

    # ============================================================
    # FINAL RESPONSE
    # ============================================================
    return jsonify({
        "message": f"Webhook successfully processed for branch '{branch}' by user '{pusher_username}'."
    }), 200

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

#run production


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
