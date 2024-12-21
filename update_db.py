import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

def get_stocks_to_update(db_path):
    """Get list of unique stock symbols from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(DISTINCT symbol)
        FROM stock_prices
        WHERE timeframe = 'weekly'
    """)
    total_stocks = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT DISTINCT symbol
        FROM stock_prices
        WHERE timeframe = 'weekly'
    """)
    stocks = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return stocks, total_stocks

def check_existing_records(conn, symbol, date, timeframe):
    """Check if records already exist for the given symbol, date and timeframe."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM stock_prices
        WHERE symbol = ? AND date = ? AND timeframe = ?
    """, (symbol, date, timeframe))
    count = cursor.fetchone()[0]
    print(f"Found {count} existing records for {symbol} on {date} ({timeframe})")
    return count > 0

def verify_insertion(conn, symbol, date, timeframe):
    """Verify that the record was actually inserted."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM stock_prices
        WHERE symbol = ? AND date = ? AND timeframe = ?
    """, (symbol, date, timeframe))
    data = cursor.fetchone()
    return data is not None

def get_date_ranges():
    """Calculate the date ranges based on the current day."""
    today = datetime.now()
    is_friday = today.weekday() == 4
    
    if is_friday:
        # If it's Friday, get the whole week's data
        start_date = today - timedelta(days=today.weekday())  # Monday of this week
        end_date = today  # Friday
    else:
        # If it's not Friday, only get the last 5 trading days
        start_date = today - timedelta(days=5)
        end_date = today
    
    return start_date, end_date, is_friday

def update_database(db_path):
    """Update database with stock data based on the current day of the week."""
    conn = sqlite3.connect(db_path)
    stocks, total_stocks = get_stocks_to_update(db_path)
    
    print(f"Starting update process for {total_stocks} stocks...")
    print(f"Found stocks: {', '.join(stocks[:5])}{'...' if len(stocks) > 5 else ''}")
    
    # Get date ranges and check if it's Friday
    start_date, end_date, is_friday = get_date_ranges()
    
    print(f"Fetching data for period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Today is{' ' if is_friday else ' not '}Friday - {'will' if is_friday else 'will not'} update weekly data")
    
    records_added = {'daily': 0, 'weekly': 0}
    
    for idx, symbol in enumerate(stocks, 1):
        try:
            print(f"\nProcessing {symbol} ({idx}/{total_stocks})")
            
            stock = yf.Ticker(symbol)
            
            # Get daily data
            daily_data = stock.history(start=start_date.strftime('%Y-%m-%d'),
                                     end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                                     interval='1d')
            
            print(f"Retrieved {len(daily_data)} daily records for {symbol}")
            
            # Get weekly data only if it's Friday
            weekly_data = pd.DataFrame()
            if is_friday:
                weekly_data = stock.history(start=start_date.strftime('%Y-%m-%d'),
                                          end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                                          interval='1wk')
                print(f"Retrieved {len(weekly_data)} weekly records for {symbol}")
            
            # Process daily data
            if not daily_data.empty:
                daily_data['Symbol'] = symbol
                daily_data['TimeFrame'] = 'daily'
                daily_data.index = daily_data.index.strftime('%Y-%m-%d')
                daily_data.reset_index(inplace=True)
                daily_data.rename(columns={
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
                
                # Insert daily records if they don't exist
                for _, row in daily_data.iterrows():
                    if not check_existing_records(conn, symbol, row['date'], 'daily'):
                        try:
                            row.to_frame().T.to_sql('stock_prices', conn, if_exists='append', index=False)
                            if verify_insertion(conn, symbol, row['date'], 'daily'):
                                records_added['daily'] += 1
                                print(f"Successfully inserted daily record for {symbol} on {row['date']}")
                            else:
                                print(f"Failed to verify insertion for daily record: {symbol} on {row['date']}")
                        except Exception as e:
                            print(f"Error inserting daily record for {symbol} on {row['date']}: {str(e)}")
            
            # Process weekly data only if it's Friday
            if is_friday and not weekly_data.empty:
                weekly_data['Symbol'] = symbol
                weekly_data['TimeFrame'] = 'weekly'
                weekly_data.index = weekly_data.index.strftime('%Y-%m-%d')
                weekly_data.reset_index(inplace=True)
                weekly_data.rename(columns={
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
                
                # Insert weekly records if they don't exist
                for _, row in weekly_data.iterrows():
                    if not check_existing_records(conn, symbol, row['date'], 'weekly'):
                        try:
                            row.to_frame().T.to_sql('stock_prices', conn, if_exists='append', index=False)
                            if verify_insertion(conn, symbol, row['date'], 'weekly'):
                                records_added['weekly'] += 1
                                print(f"Successfully inserted weekly record for {symbol} on {row['date']}")
                            else:
                                print(f"Failed to verify insertion for weekly record: {symbol} on {row['date']}")
                        except Exception as e:
                            print(f"Error inserting weekly record for {symbol} on {row['date']}: {str(e)}")
            
            conn.commit()
            
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")
            continue
    
    print("\nUpdate Summary:")
    print(f"Daily records added: {records_added['daily']}")
    print(f"Weekly records added: {records_added['weekly']}")
    
    # Verify final database state
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stock_prices WHERE timeframe = 'daily'")
    total_daily = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stock_prices WHERE timeframe = 'weekly'")
    total_weekly = cursor.fetchone()[0]
    
    print(f"\nFinal Database State:")
    print(f"Total daily records: {total_daily}")
    print(f"Total weekly records: {total_weekly}")
    
    conn.close()
    print("\nUpdate process completed!")

if __name__ == "__main__":
    DB_PATH = "static/stock_data.db"
    update_database(DB_PATH)