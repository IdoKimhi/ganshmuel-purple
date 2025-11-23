import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

def send_notification_email(pusher_name, commit_url):

    SMTP_SERVER = "smtp.gmail.com" 
    SMTP_PORT = 587
    SENDER_EMAIL = os.getenv('EMAIL_USER')
    SENDER_PASSWORD = os.getenv('EMAIL_PASS')
    RECEIVER_EMAIL = os.getenv('EMAIL_USER') #sending to myself

# Check if credentials exist before proceeding
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Error: Email credentials not found in environment variables.")
        return
    
    subject = f"Alert: New Push to 'devops' branch by {pusher_name}"
    
    body = f"""
    <h2>CI Server Alert</h2>
    <p><strong>User:</strong> {pusher_name}</p>
    <p><strong>Action:</strong> Pushed code to the devops branch.</p>
    <p><a href="{commit_url}">View Commit on GitHub</a></p>
    """

    # Create the email object
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"Email successfully sent to {RECEIVER_EMAIL}")
    except Exception as e:
        print(f"Failed to send email: {e}")
    finally:
        # Standard practice: Check if server exists before quitting 
        # to avoid errors if connection failed early
        try:
            server.quit()
        except:
            pass