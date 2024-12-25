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

def get_date_ranges(period='current'):
    """
    Calculate the date ranges based on the specified period.
    
    Args:
        period (str): 'current' for current week/period
                     'last_week' for previous week
                     'custom' for custom date range (to be implemented)
    """
    today = datetime.now()
    is_friday = today.weekday() == 4
    
    if period == 'current':
        if is_friday:
            # If it's Friday, get the whole week's data
            start_date = today - timedelta(days=today.weekday())  # Monday of this week
            end_date = today  # Friday
        else:
            # If it's not Friday, only get the last 5 trading days
            start_date = today - timedelta(days=5)
            end_date = today
    
    elif period == 'last_week':
        # Calculate last week's date range (Monday to Friday)
        end_date = today - timedelta(days=today.weekday() + 3)  # Last Friday
        start_date = end_date - timedelta(days=4)  # Last Monday
        is_friday = True  # Force weekly data update for last week
    
    return start_date, end_date, is_friday

def check_data_completeness(conn, symbol, start_date, end_date, timeframe):
    """Check if we have complete data for the given period."""
    cursor = conn.cursor()
    
    # Convert dates to strings
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT COUNT(DISTINCT date)
        FROM stock_prices
        WHERE symbol = ? 
        AND timeframe = ?
        AND date BETWEEN ? AND ?
    """, (symbol, timeframe, start_str, end_str))
    
    existing_days = cursor.fetchone()[0]
    
    # Calculate expected number of records
    if timeframe == 'daily':
        # Count only weekdays
        delta = end_date - start_date
        expected_days = sum(1 for i in range(delta.days + 1) 
                          if (start_date + timedelta(days=i)).weekday() < 5)
    else:  # weekly
        expected_days = 1  # We expect one weekly record
        
    return existing_days >= expected_days

def update_database(db_path, period='current'):
    """Update database with stock data for the specified period."""
    conn = sqlite3.connect(db_path)
    stocks, total_stocks = get_stocks_to_update(db_path)
    
    print(f"Starting update process for {total_stocks} stocks...")
    print(f"Found stocks: {', '.join(stocks[:5])}{'...' if len(stocks) > 5 else ''}")
    
    # Get date ranges for the specified period
    start_date, end_date, is_friday = get_date_ranges(period)
    
    print(f"Fetching data for period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Processing {'weekly data' if is_friday else 'only daily data'}")
    
    records_added = {'daily': 0, 'weekly': 0}
    api_calls = {'daily': 0, 'weekly': 0}
    
    for idx, symbol in enumerate(stocks, 1):
        try:
            print(f"\nProcessing {symbol} ({idx}/{total_stocks})")
            
            # Check if we need to update daily data
            need_daily = not check_data_completeness(conn, symbol, start_date, end_date, 'daily')
            # Check if we need to update weekly data
            need_weekly = is_friday and not check_data_completeness(conn, symbol, start_date, end_date, 'weekly')
            
            if not need_daily and not need_weekly:
                print(f"Data is up to date for {symbol}")
                continue
                
            # Only create Ticker object if we need to fetch data
            stock = yf.Ticker(symbol)
            
            # Get daily data if needed
            if need_daily:
                api_calls['daily'] += 1
                daily_data = stock.history(start=start_date.strftime('%Y-%m-%d'),
                                         end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                                         interval='1d')
                
                print(f"Retrieved {len(daily_data)} daily records for {symbol}")
                
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
                    
                    for _, row in daily_data.iterrows():
                        if not check_existing_records(conn, symbol, row['date'], 'daily'):
                            try:
                                row.to_frame().T.to_sql('stock_prices', conn, if_exists='append', index=False)
                                if verify_insertion(conn, symbol, row['date'], 'daily'):
                                    records_added['daily'] += 1
                                    print(f"Successfully inserted daily record for {symbol} on {row['date']}")
                            except Exception as e:
                                print(f"Error inserting daily record for {symbol} on {row['date']}: {str(e)}")
            
            # Get weekly data if needed
            if need_weekly:
                api_calls['weekly'] += 1
                weekly_data = stock.history(start=start_date.strftime('%Y-%m-%d'),
                                          end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                                          interval='1wk')
                
                print(f"Retrieved {len(weekly_data)} weekly records for {symbol}")
                
                if not weekly_data.empty:
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
                    
                    for _, row in weekly_data.iterrows():
                        if not check_existing_records(conn, symbol, row['date'], 'weekly'):
                            try:
                                row.to_frame().T.to_sql('stock_prices', conn, if_exists='append', index=False)
                                if verify_insertion(conn, symbol, row['date'], 'weekly'):
                                    records_added['weekly'] += 1
                                    print(f"Successfully inserted weekly record for {symbol} on {row['date']}")
                            except Exception as e:
                                print(f"Error inserting weekly record for {symbol} on {row['date']}: {str(e)}")
            
            conn.commit()
            
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")
            continue
    
    print("\nUpdate Summary:")
    print(f"Daily records added: {records_added['daily']} (API calls: {api_calls['daily']})")
    print(f"Weekly records added: {records_added['weekly']} (API calls: {api_calls['weekly']})")
    
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
    
    # To update current week's data:
    update_database(DB_PATH, period='current')
    
    # To update last week's data:
    #update_database(DB_PATH, period='last_week')