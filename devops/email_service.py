import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# --- Internal Helper to Send the Actual Email ---
def _send_via_smtp(subject, html_body):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = os.getenv('EMAIL_USER')
    SENDER_PASSWORD = os.getenv('EMAIL_PASS')
    RECEIVER_EMAIL = os.getenv('EMAIL_USER')

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Error: Email credentials not found in environment variables.")
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"Email successfully sent to {RECEIVER_EMAIL}")
    except Exception as e:
        print(f"Failed to send email: {e}")
    finally:
        try:
            # Standard practice: Check if server exists before quitting 
            if 'server' in locals() and server is not None:
                 server.quit()
        except:
            pass

# --- 1. Function for Flask (Original Webhook) ---
def send_notification_email(pusher_name, commit_url):
    subject = f"Alert: New Push to 'devops' branch by {pusher_name}"
    
    body = f"""
    <h2>CI Server Alert</h2>
    <p><strong>User:</strong> {pusher_name}</p>
    <p><strong>Action:</strong> Pushed code to the devops branch.</p>
    <p><a href="{commit_url}">View Commit on GitHub</a></p>
    """
    _send_via_smtp(subject, body)

# --- 2. New Function for /mailtest (Simple Alert) ---
def send_simple_alert_email(branch, user):
    subject = f"CI Service Alert: Push to {branch} detected"
    
    body = f"""
    <h2>CI Service Alert</h2>
    <p>A push to the <strong>{branch}</strong> branch was detected by <strong>{user}</strong>.</p>
    <p>This is a simulated test of the email notification system.</p>
    """
    print(f"Attempting to send simple alert email for branch {branch} by user {user}")
    _send_via_smtp(subject, body)


# --- 3. Function for Bash (Test Results) ---
def send_build_status_email(status, branch):
    # Set color based on status
    color = "green" if status == "Success" else "red"
    subject = f"Build {status}: Branch '{branch}'"
    
    body = f"""
    <h2 style="color: {color};">CI Build {status}</h2>
    <p><strong>Branch:</strong> {branch}</p>
    <p><strong>Status:</strong> <span style="color: {color}; font-weight: bold;">{status}</span></p>
    <p>Please check the server logs for details.</p>
    """
    _send_via_smtp(subject, body)

# --- 4. Main Block (CLI Handler) ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python email_service.py <STATUS> <BRANCH>")
        sys.exit(1)

    input_status = sys.argv[1]
    input_branch = sys.argv[2]

    print(f"Processing CLI email for {input_status} on {input_branch}...")
    send_build_status_email(input_status, input_branch)