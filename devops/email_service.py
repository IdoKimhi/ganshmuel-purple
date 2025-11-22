import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_notification_email(pusher_name, commit_url):
    # --- CONFIGURATION ---
    # ideally, load these from os.environ for security
    SMTP_SERVER = "smtp.gmail.com" # Example for Gmail
    SMTP_PORT = 587
    SENDER_EMAIL = "your_email@gmail.com"
    SENDER_PASSWORD = "your_app_password" # Do NOT use your login password, use an App Password
    RECEIVER_EMAIL = "your_email@gmail.com"

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
        # Connect to the server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Secure the connection
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        # Send email
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"Email successfully sent to {RECEIVER_EMAIL}")
        
    except Exception as e:
        print(f"Failed to send email: {e}")
    finally:
        server.quit()