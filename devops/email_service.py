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
        recipient_list = [e.strip() for e in to_emails.split(',') if e.strip()]
    elif isinstance(to_emails, list):
        recipient_list = to_emails
    else:
        # Fallback to the single test user
        recipient_list = [os.getenv('EMAIL_USER')] 
    
    # --- Resolve Teams to Actual Email Addresses ---
    DEV_OPS_EMAILS = [e.strip() for e in os.getenv('DEVOPS_TEAM_EMAILS', os.getenv('EMAIL_USER')).split(',') if e.strip()]
    WEIGHT_TEAM_EMAILS = [e.strip() for e in os.getenv('WEIGHT_TEAM_EMAILS', os.getenv('EMAIL_USER')).split(',') if e.strip()]
    BILLING_TEAM_EMAILS = [e.strip() for e in os.getenv('BILLING_TEAM_EMAILS', os.getenv('EMAIL_USER')).split(',') if e.strip()]

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
        print(f"Connecting to SMTP server to send email to {len(recipient_list)} recipients...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_list, msg.as_string())
        print("Email sent successfully.")
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False


def get_team_recipients(team_name):
    """Maps team names to actual email lists."""
    team_name = team_name.lower()
    if team_name == 'devops':
        return os.getenv('DEVOPS_TEAM_EMAILS', os.getenv('EMAIL_USER'))
    elif team_name == 'weight':
        return os.getenv('WEIGHT_TEAM_EMAILS', os.getenv('EMAIL_USER'))
    elif team_name == 'billing':
        return os.getenv('BILLING_TEAM_EMAILS', os.getenv('EMAIL_USER'))
    else:
        # Fallback
        return os.getenv('EMAIL_USER')


def send_simple_alert_email(branch, pusher):
    """
    Sends a simple alert email, primarily for testing purposes.
    """
    subject = f"CI Test Alert: Push detected on '{branch}' by {pusher}"
    
    html_body = f"""
    <h2>CI/CD Alert</h2>
    <p>A webhook was successfully processed.</p>
    <ul>
        <li><b>Branch:</b> {branch}</li>
        <li><b>User:</b> {pusher}</li>
    </ul>
    <p>This is a test notification.</p>
    """
    
    print(f"Sending simple alert email for {branch} to default recipient.")
    # Sends to the default EMAIL_USER or the first email in DEVOPS_TEAM_EMAILS if set
    _send_via_smtp(subject, html_body)
    
    return True

def send_ci_status_email_v2(status, branch, pusher, team, failure_details_str=""):
    """
    Sends a comprehensive CI status email.
    
    :param status: 'Success' or 'Failure'
    :param branch: Branch name (e.g., 'dev')
    :param pusher: User who pushed the code
    :param team: Team of the pusher (e.g., 'devops', 'weight', 'billing')
    :param failure_details_str: CRITICAL: Comma-separated string of failed tests.
    """
    
    # CRITICAL: Parse the comma-separated string back into a list
    failure_details = [f.strip() for f in failure_details_str.split(',') if f.strip()]
    
    color = "#10B981" if status.lower() == 'success' else "#EF4444"
    subject = f"CI/CD Build {status.upper()}: {branch} by {pusher}"
    
    # Resolve recipients: send to the pusher's team
    recipient_teams = get_team_recipients(team)
    
    action_message = ""
    if status.lower() == 'success':
        action_message = f"""
        <p style="margin-top: 20px; font-size: 1em; color: #10B981; font-weight: bold;">
            Action: Automated tests PASSED. Code is ready for merge or deployment.
        </p>
        """
    else:
        # Build the failure list for the email body
        failure_list_html = "".join([f"<li>❌ {f}</li>" for f in failure_details])
        
        action_message = f"""
        <p style="margin-top: 20px; font-size: 1em; color: #EF4444; font-weight: bold;">
            Action: Automated tests FAILED. Rollback was attempted.
        </p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid #FCA5A5; background-color: #FEF2F2; border-radius: 4px;">
            <p style="font-weight: bold; margin-bottom: 5px;">Failed Tests:</p>
            <ul style="list-style-type: none; padding-left: 0;">
                {failure_list_html}
            </ul>
        </div>
        """

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #E5E7EB; border-radius: 8px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <h1 style="color: #1F2937; border-bottom: 2px solid {color}; padding-bottom: 10px;">CI/CD Status Update</h1>
        
        <p style="line-height: 1.5;">
            Push to branch <b>{branch}</b> made by: 
            <span style="font-weight: bold; color: #1F2937;">{pusher}</span> 
            from team 
            <span style="font-weight: bold; color: #1F2937;">{team}</span>
        </p>
        
        <p style="margin-top: 15px; font-size: 1.1em;">
            Build status: 
            <span style="color: {color}; font-weight: 900; background-color: {color}1A; padding: 4px 8px; border-radius: 4px;">{status.upper()}</span>
        </p>
        
        {action_message}
        
        <p style="margin-top: 30px; font-size: 0.85em; color: #9CA3AF;">
            This email was sent automatically by the CI server. Check server logs for full details.
        </p>
    </div>
    """
    
    # Send email
    _send_via_smtp(subject, html_body, recipient_teams)


# --- 4. Main Block (CLI Handler) ---
if __name__ == "__main__":
    # The new CLI handler expects at least 5 arguments now: STATUS, BRANCH, PUSHER, TEAM, FAILURE_DETAILS
    if len(sys.argv) < 5:
        print("Usage: python email_service.py <STATUS> <BRANCH> <PUSHER> <TEAM> [FAILURE_DETAILS_CSV]")
        sys.exit(1)

    input_status = sys.argv[1]
    input_branch = sys.argv[2]
    input_pusher = sys.argv[3]
    input_team = sys.argv[4]
    # The fifth argument is the CSV string of failures (or empty string)
    input_failures = sys.argv[5] if len(sys.argv) > 5 else ""

    print(f"CLI: Attempting to send {input_status} email for {input_branch} by {input_pusher}.")
    send_ci_status_email_v2(input_status, input_branch, input_pusher, input_team, input_failures)