import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
import os

class LogManager:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.logs = []
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        # Clear existing file
        open(log_file_path, 'w').close()
    
    def log(self, message):
        timestamp = datetime.now().strftime('[%d%m%Y]')
        if message == '':
            log_entry = f"{message}"
        else:
            log_entry = f"{timestamp}: {message}"
        print(message,len(message))  # Still print to console
        self.logs.insert(0, log_entry)  # Insert at beginning for reverse order
        
        # Write all logs to file
        with open(self.log_file_path, 'w') as f:
            f.write('\n'.join(self.logs))

def is_holiday(date):
    """Check if the given date is a holiday."""
    # Christmas Day
    if date.month == 12 and date.day == 25:
        return True
    return False

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
    """Calculate the date ranges based on the specified period."""
    today = datetime.now()
    is_friday = today.weekday() == 4
    
    if period == 'current':
        if is_friday:
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        else:
            start_date = today - timedelta(days=5)
            end_date = today
    
    elif period == 'last_week':
        end_date = today - timedelta(days=today.weekday() + 3)
        start_date = end_date - timedelta(days=4)
        is_friday = True
    
    return start_date, end_date, is_friday

def check_data_completeness(conn, symbol, start_date, end_date, timeframe):
    """Check if we have complete data for the given period."""
    cursor = conn.cursor()
    
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
    
    if timeframe == 'daily':
        delta = end_date - start_date
        expected_days = sum(1 for i in range(delta.days + 1) 
                          if (start_date + timedelta(days=i)).weekday() < 5 
                          and not is_holiday(start_date + timedelta(days=i)))
    else:
        expected_days = 1
        
    return existing_days >= expected_days

def update_database(db_path, period='current'):
    """Update database with stock data for the specified period."""
    logger = LogManager('./static/logs/update_db.txt')
    conn = sqlite3.connect(db_path)
    stocks, total_stocks = get_stocks_to_update(db_path)
    
    logger.log(f"Starting update process for {total_stocks} stocks...")
    logger.log(f"Found stocks: {', '.join(stocks[:5])}{'...' if len(stocks) > 5 else ''}")
    
    start_date, end_date, is_friday = get_date_ranges(period)
    
    logger.log(f"Fetching data for period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.log(f"Processing {'weekly data' if is_friday else 'only daily data'}")
    
    records_added = {'daily': 0, 'weekly': 0}
    api_calls = {'daily': 0, 'weekly': 0}
    
    for idx, symbol in enumerate(stocks, 1):
        try:
            logger.log(f"Processing {symbol} ({idx}/{total_stocks})")
            
            need_daily = not check_data_completeness(conn, symbol, start_date, end_date, 'daily')
            need_weekly = is_friday and not check_data_completeness(conn, symbol, start_date, end_date, 'weekly')
            
            if not need_daily and not need_weekly:
                logger.log(f"Data is up to date for {symbol}\n")
                continue
                
            stock = yf.Ticker(symbol)
            
            if need_daily:
                api_calls['daily'] += 1
                daily_data = stock.history(start=start_date.strftime('%Y-%m-%d'),
                                         end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                                         interval='1d')
                
                logger.log(f"Retrieved {len(daily_data)} daily records for {symbol}")
                
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
                                    logger.log(f"Successfully inserted daily record for {symbol} on {row['date']}")
                            except Exception as e:
                                logger.log(f"Error inserting daily record for {symbol} on {row['date']}: {str(e)}")
            
            if need_weekly:
                api_calls['weekly'] += 1
                weekly_data = stock.history(start=start_date.strftime('%Y-%m-%d'),
                                          end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                                          interval='1wk')
                
                logger.log(f"Retrieved {len(weekly_data)} weekly records for {symbol}")
                
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
                                    logger.log(f"Successfully inserted weekly record for {symbol} on {row['date']}")
                            except Exception as e:
                                logger.log(f"Error inserting weekly record for {symbol} on {row['date']}: {str(e)}")
            
            conn.commit()
            
        except Exception as e:
            logger.log(f"Error processing {symbol}: {str(e)}")
            continue
    
    logger.log("Update Summary:")
    logger.log(f"Daily records added: {records_added['daily']} (API calls: {api_calls['daily']})")
    logger.log(f"Weekly records added: {records_added['weekly']} (API calls: {api_calls['weekly']})")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stock_prices WHERE timeframe = 'daily'")
    total_daily = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stock_prices WHERE timeframe = 'weekly'")
    total_weekly = cursor.fetchone()[0]
    
    logger.log(f"Final Database State:")
    logger.log(f"Total daily records: {total_daily}")
    logger.log(f"Total weekly records: {total_weekly}")
    
    conn.close()
    logger.log("Update process completed!")

if __name__ == "__main__":
    DB_PATH = "static/stock_data.db"
    
    # To update current week's data:
    update_database(DB_PATH, period='current')
    
    # To update last week's data:
    #update_database(DB_PATH, period='last_week')