import sqlite3
import os,sys
#from .config import DB_PATH

DB_PATH = 'static/stock_data.db'

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



def print_table_structure(db_path):
    """
    Print the structure of tables in the SQLite database
    
    Args:
        db_path (str): Path to the SQLite database file
    """
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Tables to analyze
        tables = ['stock_prices', 'nasdaq_screener']
        
        for table in tables:
            print(f"\nTable structure for: {table}")
            print("-" * 50)
            
            # Get table info using PRAGMA statement
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            
            # Print column details
            print("Column Name | Data Type | Nullable | Default | Primary Key")
            print("-" * 60)
            for col in columns:
                cid, name, dtype, notnull, default, pk = col
                print(f"{name:<11} | {dtype:<9} | {bool(notnull):<8} | {str(default):<7} | {bool(pk)}")
                
        conn.close()
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")


def delete_stock_records(db_path, symbol):
    """
    Delete all records for a given stock symbol from both tables
    
    Args:
        db_path (str): Path to the SQLite database file
        symbol (str): Stock symbol to delete (case sensitive)
    
    Returns:
        tuple: (success: bool, message: str, deleted_counts: dict)
    """
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")
        
        try:
            # Delete from stock_prices table (note: symbol is part of primary key)
            cursor.execute("DELETE FROM stock_prices WHERE symbol = ?", (symbol,))
            prices_deleted = cursor.rowcount
            
            # Delete from nasdaq_screener table (Symbol is not primary key)
            cursor.execute("DELETE FROM nasdaq_screener WHERE Symbol = ?", (symbol,))
            screener_deleted = cursor.rowcount
            
            # Commit the transaction
            conn.commit()
            
            deleted_counts = {
                "stock_prices": prices_deleted,
                "nasdaq_screener": screener_deleted
            }
            
            message = (f"Deleted {prices_deleted} records from stock_prices and "
                      f"{screener_deleted} records from nasdaq_screener for symbol '{symbol}'")
            success = True
            
        except sqlite3.Error as e:
            # If any error occurs, rollback the transaction
            cursor.execute("ROLLBACK")
            message = f"Error during deletion: {str(e)}"
            success = False
            deleted_counts = {}
            
        finally:
            conn.close()
            
        return success, message, deleted_counts
        
    except sqlite3.Error as e:
        return False, f"Database connection error: {str(e)}", {}
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", {}

# Usage example:


#if __name__ == "__main__":
    # print_table_structure('./static/stock_data.db')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <stock_id>")
        sys.exit(1)
        
    stock_id = sys.argv[1]
    success, message, counts = delete_stock_records('./static/stock_data.db', stock_id)
    if success:
        print(f"Success: {message}")
        print(f"Deleted counts: {counts}")
    else:
        print(f"Error: {message}")