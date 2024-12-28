import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def send_email(to_email, subject):
    # Email settings
    smtp_host = "smtp"
    smtp_port = 25
    from_email = "stockwise@tianshen.store"

    # Create message
    msg = MIMEMultipart('alternative')
    msg['From'] = f"StockWise <{from_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject

    # Read HTML content
    try:
        with open('./static/daily_email_combined.txt', 'r') as f:
            html_content = f.read()
        
        # Attach HTML content
        msg.attach(MIMEText(html_content, 'html'))

        # Connect to SMTP server
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

if __name__ == "__main__":
    current_date = datetime.now().strftime("%Y-%m-%d")
    send_email(
        "xiaozhiyong1988@gmail.com",
        f"StockWise Daily Volume Analysis - {current_date}"
    )