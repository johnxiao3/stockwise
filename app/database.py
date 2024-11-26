import sqlite3
import os
from .config import DB_PATH



def initialize_database():
    """Initialize the database with necessary tables and indices"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DROP TABLE IF EXISTS stock_prices')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_prices (
        date TEXT,
        symbol TEXT,
        timeframe TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        dividends REAL,
        stock_splits REAL,
        PRIMARY KEY (date, symbol, timeframe)
    )
    ''')
    
    # Create indices
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON stock_prices(symbol)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timeframe ON stock_prices(timeframe)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON stock_prices(date)')
    
    conn.commit()
    conn.close()


# Database functions
def ensure_static_folder():
    """Ensure static folder exists"""
    if not os.path.exists('static'):
        os.makedirs('static')

def get_db_connection():
    """Get database connection"""
    ensure_static_folder()
    return sqlite3.connect(DB_PATH)


def get_database_size():
    """Get the size of the SQLite database in GB"""
    try:
        size_in_bytes = os.path.getsize(DB_PATH)
        return size_in_bytes / (1024 * 1024 * 1024)  # Convert to GB
    except Exception as e:
        print(f"Error getting database size: {str(e)}")
        return 0