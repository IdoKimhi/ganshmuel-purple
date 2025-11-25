import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
from dotenv import load_dotenv

# Ensure environment variables are loaded (this is also done in app.py, but good practice here)
load_dotenv(dotenv_path='recipient_config.env')

# --- Internal Helper to Send the Actual Email ---
def _send_via_smtp(subject, html_body, to_emails=None):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = os.getenv('EMAIL_USER')
    SENDER_PASSWORD = os.getenv('EMAIL_PASS')

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Error: Email credentials (EMAIL_USER/EMAIL_PASS) not found in environment variables.")
        return

    # Normalize recipients: can be a string (comma-separated) or a list
    if isinstance(to_emails, str):
        recipient_list = [e.strip() for e in to_emails.split(',') if e.strip()]
    elif isinstance(to_emails, list):
        recipient_list = to_emails
    else:
        # Fallback to the single test user
        recipient_list = [os.getenv('EMAIL_USER')] 
    
    # --- Resolve Teams to Actual Email Addresses using recipient_config.env ---
    # Load emails from ENV variables (which are loaded from recipient_config.env)
    DEV_OPS_EMAILS = [e.strip() for e in os.getenv('DEVOPS_TEAM_EMAILS', '').split(',') if e.strip()]
    WEIGHT_TEAM_EMAILS = [e.strip() for e in os.getenv('WEIGHT_TEAM_EMAILS', '').split(',') if e.strip()]
    BILLING_TEAM_EMAILS = [e.strip() for e in os.getenv('BILLING_TEAM_EMAILS', '').split(',') if e.strip()]

    # Map team strings (passed from deploy.sh) to lists of emails
    team_map = {
        'DEVOPS': DEV_OPS_EMAILS,
        'WEIGHT': WEIGHT_TEAM_EMAILS,
        'BILLING': BILLING_TEAM_EMAILS,
    }

    final_recipients = set()
    for recipient_identifier in recipient_list:
        upper_identifier = recipient_identifier.upper()
        if upper_identifier in team_map:
            final_recipients.update(team_map[upper_identifier])
        else:
            final_recipients.add(recipient_identifier) # Assume it's a direct email address

    final_recipient_list = [e.strip() for e in final_recipients if e.strip()]

    if not final_recipient_list:
        print("Warning: No final recipients resolved. Email not sent.")
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
    msg['To'] = ", ".join(final_recipient_list) 
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, final_recipient_list, msg.as_string()) 
        print(f"CI Status Email successfully sent to {', '.join(final_recipient_list)}")
    except Exception as e:
        print(f"Failed to send email: {e}")
    finally:
        try:
            if 'server' in locals() and server is not None:
                 server.quit()
        except:
            pass

# --- NEW Function for Bash (Test Results) ---
def send_ci_status_email_v2(status, branch, pusher, team, failure_details=None):
    """
    Sends a comprehensive CI status email based on the user's template.
    
    :param status: 'Success' or 'Failure'
    :param branch: The branch that was pushed (should be 'dev').
    :param pusher: The username who pushed.
    :param team: The team associated with the pusher (e.g., 'devops', 'weight', 'billing').
    :param failure_details: List of failed scripts/modules.
    """
    # Cast failure_details to a list if it was passed as a single string from shell
    if isinstance(failure_details, str):
        # We need to handle the case where the shell passes the list as a single comma-separated string
        failure_details = [d.strip() for d in failure_details.split(',') if d.strip()]
    elif failure_details is None:
        failure_details = []

    color = "#10B981" if status.lower() == "success" else "#EF4444"
    subject = f"CI Server Alert: Build {status} on '{branch}'"
    
    # 1. Determine recipients: Always send to DEVOPS. Add team-specific groups on FAILURE.
    recipient_teams = ['DEVOPS'] 
    
    if status.lower() == "failure":
        # Determine the affected team for failure based on file path
        if any('weight' in detail for detail in failure_details):
            recipient_teams.append('WEIGHT')
        if any('billing' in detail for detail in failure_details):
            recipient_teams.append('BILLING')
        
        # Ensure recipients are unique
        recipient_teams = list(set(recipient_teams))
    
    # 2. Dynamic Body Content
    if status.lower() == "success":
        action_message = """
        <p style="margin-top: 20px; color: #374151;">
            <b>Action:</b> Pull request to <b>main</b> was created.
        </p>
        """
    else: # Failure
        failed_tests_html = "<ul style='padding-left: 20px; margin: 10px 0;'>" + "".join([f"<li style='color: #6B7280;'>{test}</li>" for test in failure_details]) + "</ul>"
        action_message = f"""
        <p style="margin-top: 20px; color: #374151;">
            <b>Tests failed:</b>
        </p>
        {failed_tests_html}
        <p style="color: #F59E0B; font-weight: bold; margin-top: 15px;">
            <b>Restored '{branch}' branch to latest stable commit.</b>
        </p>
        """

    # 3. HTML Body Template (Tailored to the user's layout)
    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; padding: 25px; border-radius: 8px; border: 1px solid #E5E7EB; max-width: 600px; margin: auto; background-color: #F9FAFB;">
        <h2 style="color: #1F2937; margin-bottom: 5px;">CI Server Alert: Build {status}</h2>
        <hr style="border-color: #E5E7EB; margin-top: 15px; margin-bottom: 15px;">
        
        <p style="color: #4B5563; line-height: 1.5;">
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

# --- Redundant/Legacy Functions (Kept for compatibility with mailtest route) ---
def send_notification_email(pusher_name, commit_url): pass
def send_simple_alert_email(branch_name, pusher_username): pass
def send_build_status_email(status, branch): pass
def send_build_status_email_test(status, branch): pass
def send_team_notification(branch_name, pusher_username, recipient_emails): pass
# --- End Redundant Functions ---

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
    # The new CLI handler expects at least 4 arguments
    if len(sys.argv) < 5:
        print("Usage: python email_service.py <STATUS> <BRANCH> <PUSHER> <TEAM> [FAILURE_DETAILS...]")
        sys.exit(1)

    input_status = sys.argv[1]
    input_branch = sys.argv[2]
    input_pusher = sys.argv[3]
    input_team = sys.argv[4]
    # failure_details are all arguments from index 5 onwards, passed as separate strings
    failure_details = sys.argv[5:] 

    print(f"Processing CLI email for {input_status} on {input_branch}...")
    send_ci_status_email_v2(input_status, input_branch, input_pusher, input_team, failure_details)