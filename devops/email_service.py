import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# --- Internal Helper to Send the Actual Email ---
def _send_via_smtp(subject, html_body, to_emails=None):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = os.getenv('EMAIL_USER')
    SENDER_PASSWORD = os.getenv('EMAIL_PASS')

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Error: Email credentials not found in environment variables.")
        return

    # Normalize recipients: can be a string (comma-separated) or a list
    if isinstance(to_emails, str):
        # Handle the common case where ENV variables are comma-separated
        recipient_list = [e.strip() for e in to_emails.split(',') if e.strip()]
    elif isinstance(to_emails, list):
        recipient_list = to_emails
    else:
        # Fallback to the single test user if no specific recipients are passed
        recipient_list = [os.getenv('EMAIL_USER')] 
    
    if not recipient_list or recipient_list == ['']:
        print("Warning: No recipients specified. Email not sent.")
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    # For display, join them with a comma
    msg['To'] = ", ".join(recipient_list) 
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        # smtplib.sendmail requires a list of recipients for the second argument
        server.sendmail(SENDER_EMAIL, recipient_list, msg.as_string()) 
        print(f"Production Email successfully sent to {', '.join(recipient_list)}")
    except Exception as e:
        print(f"Failed to send email: {e}")
    finally:
        try:
            if 'server' in locals() and server is not None:
                 server.quit()
        except:
            pass
# --- 1. Function for Flask (Original Webhook) ---
def send_notification_email(pusher_name, commit_url):
    subject = "Repository Update Notification"
    html_body = f"""
    <h2>Deployment Notification</h2>
    <p>A change was detected in the repository.</p>
    <p>Pusher: <b>{pusher_name}</b></p>
    <p>Commit URL: <a href="{commit_url}">View Commit</a></p>
    """
    _send_via_smtp(subject, html_body)
    return True

# --- 2. New Function for /mailtest (Simple Alert) ---
def send_simple_alert_email(branch_name, pusher_username):
    subject = f"CI Alert: Simple Test Push to {branch_name}"
    html_body = f"""
    <h2>Simple CI Alert</h2>
    <p>A test push was performed on branch <b>{branch_name}</b> by user <b>{pusher_username}</b>.</p>
    <p>This is a low-priority notification.</p>
    """
    _send_via_smtp(subject, html_body)
    return True


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

def send_team_notification(branch_name, pusher_username, recipient_emails):
    """
    Sends a production deployment notification email to the actual DevOps team.
    
    :param branch_name: The branch that was pushed (should be 'dev').
    :param pusher_username: The GitHub user who made the push.
    :param recipient_emails: The actual list of DEVOPS_TEAM_EMAILS.
    """
    subject = f"CI ALERT: Production Push to '{branch_name}' detected by {pusher_username}"
    
    html_body = f"""
    <h2>CI/CD Notification</h2>
    <p>A **production-critical** push event was detected on the <b>'{branch_name}'</b> branch.</p>
    <p><b>Initiated By:</b> {pusher_username}</p>
    <p><b>Recipient Team:</b> DevOps Team</p>
    <p><b>Action Required:</b> DevOps Team is notified for immediate review/deployment steps.</p>
    """
    
    print(f"Sending production notification to DevOps Team: {', '.join(recipient_emails)}")
    _send_via_smtp(subject, html_body, recipient_emails)    
    return True

# --- 4. Main Block (CLI Handler) ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python email_service.py <STATUS> <BRANCH>")
        sys.exit(1)

    input_status = sys.argv[1]
    input_branch = sys.argv[2]

    print(f"Processing CLI email for {input_status} on {input_branch}...")
    send_build_status_email(input_status, input_branch)