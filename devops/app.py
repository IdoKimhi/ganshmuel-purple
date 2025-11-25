import subprocess
import os
from flask import Flask, request, jsonify

# Assuming email_service is available for import if needed, 
# but the deploy.sh script handles the final email.
# from email_service import send_team_notification 

app = Flask(__name__)

# --- Mock Function: In a real app, this would use a database or config file ---
def get_pusher_team(username):
    """Infers the team based on the pusher's username."""
    username = username.lower()
    if 'billing' in username or 'finance' in username:
        return 'billing'
    elif 'weight' in username or 'logistics' in username:
        return 'weight'
    else:
        return 'devops'

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

    # ============================================================
    # RUN CI PIPELINE (deploy.sh)
    # ============================================================
    try:
        if branch == 'ido':
            print(f"Running deploy script for branch: {branch} with pusher: {pusher_username} and team: {pusher_team}")
            
            # Pass all three required arguments to deploy.sh
            result = subprocess.run(
                ["bash", "deploy.sh", branch, pusher_username, pusher_team],
                capture_output=True,
                text=True,
                check=True # Raise an exception if the command exits with a non-zero status
            )

            print("--- Deploy Script Output (STDOUT) ---")
            print(result.stdout)
            if result.stderr:
                 print("--- Deploy Script Output (STDERR) ---")
                 print(result.stderr)
            
            # If the script ran successfully (status code 0)
            return jsonify({
                "message": f"Webhook processed. CI pipeline SUCCESS for '{branch}' by '{pusher_username}'.",
                "output": result.stdout
            }), 200
        
        else:
            return jsonify({
                "message": f"Webhook received for branch '{branch}'. CI pipeline SKIPPED (only runs on 'dev')."
            }), 200

    except subprocess.CalledProcessError as e:
        # This catches errors where deploy.sh returns non-zero (i.e., test failure)
        # The failure email is handled inside deploy.sh, but we report the CI failure here.
        error_output = e.stdout + e.stderr
        print(f"Error running deploy script (CI FAILURE): {error_output}")
        
        return jsonify({
            "message": f"CI Pipeline FAILED for branch '{branch}'. Rollback executed and failure email sent.",
            "error_summary": error_output.split('\n')[-3:] # Show last few lines of output
        }), 500

    except Exception as e:
        # Catches general execution errors (e.g., file not found)
        print(f"Unexpected Error running deploy script: {e}")
        return jsonify({"message": f"Unexpected CI Server Error: {e}"}), 500