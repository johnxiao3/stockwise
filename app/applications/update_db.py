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
        timestamp = datetime.now().strftime('[%Y%m%d]')
        if message == '':
            log_entry = f"{message}"
        else:
            log_entry = f"{timestamp}: {message}"
        print(message)  # Still print to console
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

def download_batch_data(symbols, start_date, end_date, interval):
    """Download data for multiple symbols in a single API call."""
    try:
        data = yf.download(
            tickers=symbols,
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            interval=interval,
            group_by='ticker',
            auto_adjust=False,
            actions=True,
            verify=False
        )
        
        if data.empty:
            return None
            
        return data
    except Exception as e:
        print(f"Full error details: {e.__class__.__name__}: {str(e)}")
        if "Too many requests" in str(e) or "429" in str(e):
            return None
        if "timezone" in str(e).lower():
            return None
        raise e

def process_batch_data(data, timeframe, conn, logger):
    """Process and insert batch data into database."""
    records_added = 0
    
    if data is None or data.empty:
        return 0

    # Get list of symbols from the multi-level columns
    symbols = list(set([col[0] for col in data.columns]))
    
    for symbol in symbols:
        try:
            # Create DataFrame for the symbol with correct column names
            symbol_data = pd.DataFrame({
                'date': data.index,
                'open': data[(symbol, 'Open')],
                'high': data[(symbol, 'High')],
                'low': data[(symbol, 'Low')],
                'close': data[(symbol, 'Close')],
                'volume': data[(symbol, 'Volume')],
                'dividends': data[(symbol, 'Dividends')],
                'stock_splits': data[(symbol, 'Stock Splits')]
            })
            
            # Convert date to string format
            symbol_data['date'] = symbol_data['date'].dt.strftime('%Y-%m-%d')
            
            # Add symbol and timeframe columns
            symbol_data['symbol'] = symbol
            symbol_data['timeframe'] = timeframe
            
            # Insert records into database
            for _, row in symbol_data.iterrows():
                if not check_existing_records(conn, row['symbol'], row['date'], timeframe):
                    try:
                        row.to_frame().T.to_sql('stock_prices', conn, if_exists='append', index=False)
                        if verify_insertion(conn, row['symbol'], row['date'], timeframe):
                            records_added += 1
                            logger.log(f"Successfully inserted {timeframe} record for {symbol} on {row['date']}")
                    except Exception as e:
                        logger.log(f"Error inserting {timeframe} record for {symbol} on {row['date']}: {str(e)}")
                        
        except Exception as e:
            logger.log(f"Error processing {symbol}: {str(e)}")
            continue
            
    return records_added

def update_database(db_path, period='current', batch_size=5):
    """Update database with stock data for the specified period."""
    logger = LogManager('./static/logs/update_db.txt')
    conn = sqlite3.connect(db_path)
    stocks, total_stocks = get_stocks_to_update(db_path)
    
    logger.log(f"Starting update process for {total_stocks} stocks...")
    start_date, end_date, is_friday = get_date_ranges(period)
    
    logger.log(f"Checking data completeness for period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Pre-filter stocks that need updates
    stocks_needing_update = []
    for symbol in stocks:
        need_daily = not check_data_completeness(conn, symbol, start_date, end_date, 'daily')
        need_weekly = is_friday and not check_data_completeness(conn, symbol, start_date, end_date, 'weekly')
        if need_daily or need_weekly:
            stocks_needing_update.append(symbol)
    
    if not stocks_needing_update:
        logger.log("All stocks are up to date. No downloads needed.")
        conn.close()
        return 0
        
    logger.log(f"Found {len(stocks_needing_update)} stocks needing updates")
    logger.log(f"Stocks to update: {', '.join(stocks_needing_update[:5])}{'...' if len(stocks_needing_update) > 5 else ''}")
    
    records_added = {'daily': 0, 'weekly': 0}
    api_calls = {'daily': 0, 'weekly': 0}
    
    # Process stocks in batches
    for i in range(0, len(stocks_needing_update), batch_size):
        batch = stocks_needing_update[i:i + batch_size]
        logger.log(f"\nProcessing batch {i//batch_size + 1}/{(len(stocks_needing_update) + batch_size - 1)//batch_size}")
        logger.log(f"Batch symbols: {', '.join(batch)}")
        
        # Daily data
        api_calls['daily'] += 1
        daily_data = download_batch_data(batch, start_date, end_date, '1d')
        
        if daily_data is None:
            logger.log("Rate limit reached for daily data. Stopping updates.")
            break
            
        records_added['daily'] += process_batch_data(daily_data, 'daily', conn, logger)
        
        # Weekly data (only on Fridays)
        if is_friday:
            api_calls['weekly'] += 1
            weekly_data = download_batch_data(batch, start_date, end_date, '1wk')
            
            if weekly_data is None:
                logger.log("Rate limit reached for weekly data. Stopping updates.")
                break
                
            records_added['weekly'] += process_batch_data(weekly_data, 'weekly', conn, logger)
        
        conn.commit()
        time.sleep(1)  # Respect rate limits
    
    # Log summary
    logger.log("\nUpdate Summary:")
    logger.log(f"Daily records added: {records_added['daily']} (API calls: {api_calls['daily']})")
    logger.log(f"Weekly records added: {records_added['weekly']} (API calls: {api_calls['weekly']})")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stock_prices WHERE timeframe = 'daily'")
    total_daily = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stock_prices WHERE timeframe = 'weekly'")
    total_weekly = cursor.fetchone()[0]
    
    logger.log(f"\nFinal Database State:")
    logger.log(f"Total daily records: {total_daily}")
    logger.log(f"Total weekly records: {total_weekly}")
    
    conn.close()
    logger.log("Update process completed!")

    return records_added['daily'] + records_added['weekly']



# Keep existing helper functions (is_holiday, get_stocks_to_update, check_existing_records, 
# verify_insertion, get_date_ranges, check_data_completeness) as they are

if __name__ == "__main__":
    DB_PATH = "static/stock_data.db"
    update_database(DB_PATH, period='current', batch_size=5)

'''
if __name__ == "__main__":
    DB_PATH = "static/stock_data.db"
    
    # To update current week's data:
    update_database(DB_PATH, period='current')
    
    # To update last week's data:
    #update_database(DB_PATH, period='last_week')
'''