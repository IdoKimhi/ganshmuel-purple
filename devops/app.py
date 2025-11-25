import subprocess
import os
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Import necessary functions from email_service
from email_service import send_notification_email, send_simple_alert_email, send_team_notification 

# --- CRITICAL: Load Environment Variables ---
# The container's working directory is /app_root/devops. 
ENV_FILE_PATH = os.path.join(os.getcwd(), 'recipient_config.env')
print(f"Loading environment variables from: {ENV_FILE_PATH}")
load_dotenv(dotenv_path=ENV_FILE_PATH)
# -------------------------------------------

app = Flask(__name__)


# --- Helper to run deploy.sh asynchronously ---
def run_ci_pipeline_async(branch, pusher_username, pusher_team):
    """Executes the deploy.sh script in the background."""
    command = ['/bin/bash', 'deploy.sh', branch, pusher_username, pusher_team]
    
    print(f"[ASYNC] Starting CI script: {' '.join(command)}")

    try:
        # Execute the script synchronously within this dedicated thread
        # check=True will raise an error if deploy.sh exits non-zero (CI failure)
        result = subprocess.run(command, 
                                capture_output=True, 
                                text=True, 
                                check=True, 
                                cwd=os.getcwd()) 

        print(f"[ASYNC] CI Pipeline SUCCESS for {branch}.")
        print(result.stdout)
        
    except subprocess.CalledProcessError as e:
        # CI FAILURE - deploy.sh should handle the failure email
        error_output = e.stdout + e.stderr
        print(f"[ASYNC] CI Pipeline FAILED for {branch}. Error:\n{error_output}")
        
    except Exception as e:
        # General system error (e.g., deploy.sh not found, Docker not working)
        print(f"[ASYNC] UNEXPECTED SYSTEM ERROR: {e}")
        send_simple_alert_email("ERROR", "CI Server", f"CI Server encountered a major failure: {e}")


# --- Mock Function: Infers the team based on the pusher's username ---\
def get_pusher_team(username):
    """Infers the team based on the pusher's username."""
    username = username.lower()
    if 'billing' in username or 'finance' in username:
        return 'billing'
    elif 'weight' in username or 'logistics' in username:
        return 'weight'
    else:
        return 'devops'

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
    
    # Determine the pusher's team
    pusher_team = get_pusher_team(pusher_username) 

    # Logging for visibility
    print("--- GitHub Webhook Received ---")
    print(f"Pusher: {pusher_username}")
    print(f"Pusher Team: {pusher_team}")
    print(f"Branch pushed: {branch}")
    print("-------------------------------")

    
    # Check if the branch is 'ido' to proceed with the CI/CD pipeline
    if branch == 'ido':
        # *** CRITICAL FIX: Run the heavy lifting in a new thread ***
        thread = threading.Thread(target=run_ci_pipeline_async, args=(branch, pusher_username, pusher_team))
        thread.start()
        
        # Return immediate 202 Accepted response (non-blocking)
        return jsonify({
            "message": f"CI pipeline STARTED for branch '{branch}'. Check logs for status.",
            "status": "Job Accepted"
        }), 202
    
    # FINAL RESPONSE for non-ido branches
    return jsonify({
        "message": f"Webhook successfully processed for branch '{branch}'. CI skipped (only runs on 'ido')."
    }), 200


@app.route('/mailtest', methods=['POST'])
def mail_test():
    # ... (mail_test function remains the same)
    if not request.is_json:
        return jsonify ({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    
    pusher_data = data.get('pusher', {})
    pusher_username = pusher_data.get('name', 'UNKNOWN_USER')
    ref = data.get('ref', 'refs/heads/main')
    branch_name = ref.split('/')[-1]

    print("--- Mail Test Webhook Received ---")
    print(f"Simulated Branch: {branch_name}")
    print(f"Simulated User: {pusher_username}")
    print("----------------------------------")
    
    try:
        # Note: The original file had send_simple_alert_email, which is fine for a quick test
        send_simple_alert_email(branch_name, pusher_username)
        return jsonify({
            "message": "Mail test successfully processed and email sent",
            "branch": branch_name,
            "user": pusher_username
        }), 200
    except Exception as e:
        print(f"Error during email send: {e}")
        return jsonify({"message": f"Mail test failed: {e}"}), 500


# run production
if __name__ == '__main__':
    print("Starting Flask application on 0.0.0.0:8080...")
    # debug=True is okay for development, but in production, keep it False.
    app.run(host='0.0.0.0', port=8080, debug=True)