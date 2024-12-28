from fastapi import APIRouter, HTTPException
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re

router = APIRouter(prefix="/api", tags=["email_subscriptions"])

def is_valid_email(email: str) -> bool:
    """Basic email validation using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def get_db_connection():
    conn = sqlite3.connect("./static/stock_data.db")
    conn.row_factory = sqlite3.Row
    return conn

def setup_email_subscriptions_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS email_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def send_welcome_email(to_email: str) -> bool:
    # Email settings
    smtp_host = "smtp"
    smtp_port = 25
    from_email = "stockwise@tianshen.store"
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['From'] = f"StockWise <{from_email}>"
    msg['To'] = to_email
    msg['Subject'] = "Welcome to StockWise Daily Updates!"
    
    # Welcome email HTML content
    welcome_html = """
    <html>
    <body>
        <h2>Welcome to StockWise Daily Updates!</h2>
        <p>Thank you for subscribing to our Daily Stock Updates!</p>
        <p>You'll now receive daily updates about:</p>
        <ul>
            <li>Stock market movements</li>
            <li>Volume analysis</li>
            <li>Trading insights</li>
        </ul>
        <p>If you wish to unsubscribe, you can do so by visiting our website.</p>
        <br>
        <p>Best regards,<br>Your StockWise Team</p>
    </body>
    </html>
    """
    
    try:
        # Attach HTML content
        msg.attach(MIMEText(welcome_html, 'html'))
        
        # Connect to SMTP server
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False

# Initialize the table when the module is imported
setup_email_subscriptions_table()

@router.post("/subscribe")
async def subscribe(email_data: dict):
    try:
        email = email_data.get('email')
        if not email or not is_valid_email(email):
            raise HTTPException(status_code=400, detail="Invalid email address")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO email_subscriptions (email) VALUES (?)', 
                         (email,))
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, 
                              detail="Email already subscribed")
        finally:
            conn.close()
            
        # Send welcome email using your existing function
        email_sent = send_welcome_email(email)
        if not email_sent:
            print(f"Warning: Welcome email could not be sent to {email}")
        
        return {"message": "Subscription successful"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, 
                          detail=str(e))

@router.post("/unsubscribe")
async def unsubscribe(email_data: dict):
    try:
        email = email_data.get('email')
        if not email or not is_valid_email(email):
            raise HTTPException(status_code=400, detail="Invalid email address")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if email exists
        cursor.execute('SELECT * FROM email_subscriptions WHERE email = ?', 
                      (email,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, 
                              detail="Email not found in subscription list")
        
        # Remove email from database
        cursor.execute('DELETE FROM email_subscriptions WHERE email = ?', 
                      (email,))
        conn.commit()
        conn.close()
        
        return {"message": "Unsubscription successful"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, 
                          detail=str(e))