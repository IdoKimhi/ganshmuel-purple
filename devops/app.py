import subprocess
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import threading

# --- CRITICAL FIX: Import only the functions available in email_service.py ---
# We will primarily use the functions needed for the mailtest endpoint here.
# The main CI logic is in deploy.sh, which handles the status emails itself.
from email_service import send_ci_status_email_v2

# --- CRITICAL: Load Environment Variables ---
ENV_FILE_PATH = os.path.join(os.getcwd(), 'recipient_config.env')
print(f"Loading environment variables from: {ENV_FILE_PATH}")
load_dotenv(dotenv_path=ENV_FILE_PATH)
# -------------------------------------------

app = Flask(__name__)


# --- Mock Function: Infers the team based on the pusher's username ---
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

# =======================================================
# Non-blocking CI pipeline execution function (Restored)
# =======================================================
def run_ci_pipeline(branch, pusher_username, pusher_team):
    """
    Executes the CI/CD pipeline script in a separate process.
    This function should be run inside a dedicated thread.
    """
    script_path = os.path.join(os.getcwd(), 'deploy.sh')
    
    print(f"[CI THREAD] Starting CI script: /bin/bash {script_path} {branch} {pusher_username} {pusher_team}")
    
    try:
        # Execute deploy.sh using subprocess.run
        # The deploy.sh script handles its own success/failure logic and email sending
        result = subprocess.run(
            ['/bin/bash', script_path, branch, pusher_username, pusher_team],
            capture_output=True, text=True, timeout=900, # 15 minutes timeout
        )

        # Print the output from the CI script for logging/debugging
        print(f"--- Deploy Script Output (STDOUT for {branch}) ---")
        print(result.stdout)
        if result.stderr:
             print(f"--- Deploy Script Output (STDERR for {branch}) ---")
             print(result.stderr)
        
        # Check the result code
        if result.returncode != 0:
            print(f"!!! CI Pipeline FAILED for {branch} (Return Code: {result.returncode}) !!!")
        else:
            print(f"=== CI Pipeline SUCCESS for {branch} ===")

    except subprocess.TimeoutExpired:
        print(f"!!! Error running deploy script: Timeout expired (CI FAILURE) for {branch} !!!")
    except Exception as e:
        print(f"!!! Unexpected Error running deploy script: {e} !!!")

# =======================================================
# Webhook Trigger Handler
# =======================================================
@app.route('/trigger', methods=['POST'])
def trigger_handler():
    if not request.is_json:
        return jsonify({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    
    pusher_data = data.get('pusher', {})
    pusher_username = pusher_data.get('name', 'UNKNOWN_USER')
    ref = data.get("ref", "")
    branch = ref.split("/")[-1] if ref.startswith("refs/heads/") else "unknown"
    pusher_team = get_pusher_team(pusher_username) 

    # Logging for visibility
    print("--- GitHub Webhook Received ---")
    print(f"Pusher: {pusher_username}")
    print(f"Branch pushed: {branch}")
    print(f"Pusher Team: {pusher_team}")
    print("-------------------------------")

    # Only run CI on the 'dev' branch (as deploy.sh expects this)
    if branch == 'ido':
        print(f"Executing CI pipeline for branch: {branch}")
        # Start the CI process in a new, non-blocking thread
        ci_thread = threading.Thread(
            target=run_ci_pipeline, 
            args=(branch, pusher_username, pusher_team)
        )
        ci_thread.start()
        
        # Return 202 Accepted immediately to the webhook sender
        return jsonify({
            "message": f"Webhook successfully processed for branch '{branch}'. CI pipeline started asynchronously."
        }), 202
    
    else:
        # Final response for non-dev branches
        return jsonify({
            "message": f"Webhook received for branch '{branch}'. CI skipped (only runs on 'dev')."
        }), 200

# ============================================================\
# Mail Test Endpoint
# ============================================================\
@app.route('/mailtest', methods=['POST'])
def mail_test():
    if not request.is_json:
        return jsonify ({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    pusher_data = data.get('pusher', {})
    pusher_username = pusher_data.get('name', 'UNKNOWN_USER')
    ref = data.get('ref', 'refs/heads/main')
    branch_name = ref.split('/')[-1]
    
    # Use the appropriate status email function that actually exists
    try:
        # Note: We need a simpler test function, but we'll use v2 with default parameters
        # to ensure the app doesn't crash on import.
        pusher_team = get_pusher_team(pusher_username)
        # Assuming mailtest simulates a successful build for simplicity
        send_ci_status_email_v2('Success', branch_name, pusher_username, pusher_team, ['No Failures']) 
        return jsonify({
            "message": "Mail test successfully processed and email sent (using v2 status format).",
            "branch": branch_name,
            "user": pusher_username
        }), 200
    except Exception as e:
        print(f"Error during email send: {e}")
        return jsonify({"message": f"Mail test failed: {e}"}), 500


# run production
if __name__ == '__main__':
    # Flask must listen on 0.0.0.0 to be accessible from outside the container
    print("Starting Flask application on 0.0.0.0:8080...")
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)