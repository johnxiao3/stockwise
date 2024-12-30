import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import sqlite3

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
        with open('./templates/daily_email_combined.html', 'r') as f:
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
def get_db_connection():
    conn = sqlite3.connect("./static/stock_data.db")
    conn.row_factory = sqlite3.Row
    return conn
def send_emails_to_all_subscribers():
    # Get database connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all email addresses
        cursor.execute('SELECT email FROM email_subscriptions')
        subscribers = cursor.fetchall()
        
        if not subscribers:
            print("No subscribers found in the database.")
            return
        
        # Get current date for email subject
        current_date = datetime.now().strftime("%Y-%m-%d")
        subject = f"StockWise Daily Analysis - {current_date}"
        
        # Counter for successful and failed sends
        successful = 0
        failed = 0
        
        print(f"\nSending emails to {len(subscribers)} subscribers...")
        print("-" * 60)
        
        # Send email to each subscriber
        for sub in subscribers:
            email = sub['email']
            print(f"Sending to: {email}...")
            
            if send_email(email, subject):
                successful += 1
                print(f"✓ Successfully sent to {email}")
            else:
                failed += 1
                print(f"✗ Failed to send to {email}")
            
            print("-" * 60)
        
        # Print summary
        print(f"\nEmail sending complete:")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total attempted: {len(subscribers)}\n")
        
    except Exception as e:
        print(f"Error in send_emails_to_all_subscribers: {e}")
    
    finally:
        conn.close()

if __name__ == "__main__":
    current_date = datetime.now().strftime("%Y-%m-%d")
    send_email(
        "xiaozhiyong1988@gmail.com",
        f"StockWise Daily Volume Analysis - {current_date}"
    )