import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to_email, subject, body):
    # Email settings
    smtp_host = "smtp"  # Service name from docker-compose
    smtp_port = 25
    from_email = "stockwise@tianshen.store"
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = f"StockWise <{from_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    
    # Add body
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Connect to SMTP server
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Test usage
if __name__ == "__main__":
    send_email(
        "xiaozhiyong1988@gmail.com",
        "Test Email from Python",
        "This is a test email sent from Python script."
    )