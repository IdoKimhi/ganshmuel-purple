from flask import Flask, request, jsonify
# We are removing unused old imports to keep the file clean
import json
import os
import subprocess
from dotenv import load_dotenv

# Load the recipient configuration for the app
load_dotenv(dotenv_path='recipient_config.env')

app = Flask(__name__)

# --- Helper Function to Infer Team ---
def get_pusher_team(username):
    """
    Infers the team based on the pusher's username using a specific lookup 
    based on the names defined in recipient_config.env.
    """
    username = username.lower()
    
    # Names from BILLING_TEAM_EMAILS
    if any(name in username for name in ['lironsaada10', 'shay.shalom21', 'nyo1254']):
        return 'billing'
    
    # Names from WEIGHT_TEAM_EMAILS
    elif any(name in username for name in ['yosefs283', 'arielgabai555', 'lihina4']):
        return 'weight'
    
    # Default to DevOps for all others
    else:
        return 'devops'

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

@app.route('/trigger', methods=['POST'])
def trigger_handler():
    if not request.is_json:
        return jsonify({"message": "Content-Type must be application/json"}), 400

    data = request.get_json()
    
    # Extract metadata
    pusher_data = data.get('pusher', {})
    pusher_username = pusher_data.get('name', 'UNKNOWN_USER')

    ref = data.get("ref", "")
    branch = ref.split("/")[-1] if ref.startswith("refs/heads/") else "unknown"
    
    # Determine the pusher's team (Crucial step for deployment script)
    pusher_team = get_pusher_team(pusher_username)

    action = data.get('action', 'N/A')
    
    # Logging for visibility
    print("--- GitHub Webhook Received ---")
    print(f"Action: {action}")
    print(f"Pusher: {pusher_username}")
    print(f"Pusher Team: {pusher_team}")
    print(f"Branch pushed: {branch}")
    print("-------------------------------")
    
    # --- CRITICAL CHANGE: Check for 'ido' branch for local testing ---
    if branch == 'ido':
        try:
            print(f"Running deploy script for CI branch: {branch} (Pusher: {pusher_username}, Team: {pusher_team})")
            
            # Pass all three required arguments to deploy.sh using the correct path
            result = subprocess.run(
                ["bash", "deploy.sh", branch, pusher_username, pusher_team], 
                capture_output=True,
                text=True,
                check=True # Raise CalledProcessError if deploy.sh exits non-zero (i.e., failed tests)
            )

            print("--- Deploy Script Output ---")
            print(result.stdout)
            
            return jsonify({
                "message": f"Webhook processed. CI pipeline SUCCESS for '{branch}' by '{pusher_username}'.",
                "output": result.stdout.split('\n')[-5:] # Show last few lines of output
            }), 200

        except subprocess.CalledProcessError as e:
            # This catches CI failure (deploy.sh exited 1). Failure email is sent within deploy.sh.
            error_output = e.stdout + e.stderr
            print(f"CI Pipeline FAILED: {error_output}")
            
            return jsonify({
                "message": f"CI Pipeline FAILED for branch '{branch}'. Rollback executed and failure email sent.",
                "error_summary": error_output.split('\n')[-5:]
            }), 500

        except Exception as e:
            print(f"Error running deploy script: {e}")
            return jsonify({"message": f"Error running deploy script: {e}"}), 500
 
    # ============================================================
    # FINAL RESPONSE for non-CI branches
    # ============================================================
    return jsonify({
        # Ensure the skip message is accurate based on the branch name we are testing against ('ido')
        "message": f"Webhook successfully processed for branch '{branch}' by user '{pusher_username}'. CI skipped (only runs on 'ido')."
    }), 200

# run production
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)