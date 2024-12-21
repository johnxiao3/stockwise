import pandas as pd
import sqlite3
from pathlib import Path

def clean_numeric_data(value):
    """Clean numeric strings by removing '$', ',', and '%' characters"""
    if isinstance(value, str):
        # Remove '$' and ',' from currency values
        value = value.replace('$', '').replace(',', '')
        # Remove '%' from percentage values
        value = value.replace('%', '')
    return value

def import_csv_to_sqlite(csv_path, db_path='./static/stock_data.db', table_name='nasdaq_screener'):
    """
    Import CSV data into SQLite database table
    
    Parameters:
    csv_path (str): Path to the CSV file
    db_path (str): Path to SQLite database
    table_name (str): Name of the table to create/update
    """
    try:
        # Create database directory if it doesn't exist
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Read CSV file
        df = pd.read_csv(csv_path)
        
        # Clean numeric columns
        numeric_columns = ['Last Sale', 'Net Change', '% Change', 'Market Cap']
        for col in numeric_columns:
            df[col] = df[col].apply(clean_numeric_data).astype(float)
        
        # Clean volume to numeric
        df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
        
        # Clean IPO Year to numeric, allowing NaN for empty values
        df['IPO Year'] = pd.to_numeric(df['IPO Year'], errors='coerce')
        
        # Clean column names (remove spaces and special characters)
        df.columns = df.columns.str.replace(' ', '_').str.replace('[^a-zA-Z0-9_]', '')
        
        # Create SQLite connection
        conn = sqlite3.connect(db_path)
        
        # Save dataframe to SQLite
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        
        # Create indexes for commonly queried columns
        cursor = conn.cursor()
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_symbol ON {table_name} (Symbol)')
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_sector ON {table_name} (Sector)')
        
        # Close connection
        conn.close()
        
        print(f"Successfully imported {len(df)} rows into {table_name} table")
        print(f"Data types of columns:")
        for column in df.columns:
            print(f"{column}: {df[column].dtype}")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    # Example usage
    csv_path = "./nasdaq_screener.csv"  # Replace with your CSV file path
    import_csv_to_sqlite(csv_path)