from flask import Flask, request, jsonify
# Import the function from your new file
from email_service import send_notification_email

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
    
    # --- GitHub Push Event Parsing ---
    # GitHub Push events contain a 'ref' field (e.g., refs/heads/main)
    # They do usually NOT contain an 'action' field.
    
    ref = data.get('ref', '')
    pusher_data = data.get('pusher', {})
    pusher_name = pusher_data.get('name', 'Unknown Pusher')
    repository = data.get('repository', {})
    html_url = repository.get('html_url', '')

    print("--- GitHub Webhook Received ---")
    print(f"Ref: {ref}")
    print(f"Pusher: {pusher_name}")

    # --- Logic: Check for 'devops' branch ---
    if 'refs/heads/devops' in ref:
        print(">> Detected push to 'devops' branch. Initiating email sequence...")
        
        # Trigger the email function from the other file
        send_notification_email(pusher_name, html_url)
        
        return jsonify({"message": "Push to devops detected. Email sent."}), 200
        
    else:
        print(f">> Ignored: Event was for {ref}, not devops.")
        return jsonify({"message": "Event received but ignored (not devops branch)"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)