import yfinance as yf
import sqlite3,os
import pandas as pd

# Database path in static folder
DB_PATH = 'static/stock_data.db'

def ensure_static_folder():
    """Ensure static folder exists"""
    if not os.path.exists('static'):
        os.makedirs('static')

def get_db_connection():
    """Get database connection"""
    ensure_static_folder()
    return sqlite3.connect(DB_PATH)

def fetch_and_save_stock_data(symbol):
    """
    Fetch all available historical data for a stock using period="max"
    """
    try:
        conn = get_db_connection()
        
        # Get stock data
        stock = yf.Ticker(symbol)
        
        print(f"Fetching all historical data for {symbol}...")
        
        # Fetch complete daily data using period="max"
        daily_data = stock.history(period="max", interval='1d')
        daily_data['Symbol'] = symbol
        daily_data['TimeFrame'] = 'daily'
        daily_data.index = daily_data.index.strftime('%Y-%m-%d')
        
        # Fetch complete weekly data using period="max"
        weekly_data = stock.history(period="max", interval='1wk')
        weekly_data['Symbol'] = symbol
        weekly_data['TimeFrame'] = 'weekly'
        weekly_data.index = weekly_data.index.strftime('%Y-%m-%d')
        
        # Save to database
        for df in [daily_data, weekly_data]:
            df.reset_index(inplace=True)
            df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Dividends': 'dividends',
                'Stock Splits': 'stock_splits',
                'Symbol': 'symbol',
                'TimeFrame': 'timeframe'
            }, inplace=True)
            
            # Delete existing data for this symbol and timeframe
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM stock_prices 
                WHERE symbol = ? AND timeframe = ?
            ''', (symbol, df['timeframe'].iloc[0]))
            
            # Insert new data
            df.to_sql('stock_prices', conn, if_exists='append', index=False)
            conn.commit()
        
        conn.close()
        return True
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return False



screener = pd.read_csv("./nasdaq_screener.csv")
tickers = screener['Symbol']
print(f"Loaded {len(tickers)} tickers from CSV file")

for symbol in tickers:
    if symbol not in ['GOOGL','AAPL','MSFT','NVDA']:
        print(symbol)
        try:
            fetch_and_save_stock_data(symbol)
        except:
            pass