import yfinance as yf
import pandas as pd
import sqlite3,os
import json
from flask import Flask, render_template, redirect, url_for, jsonify, request
from datetime import datetime, timedelta
import plotly
import plotly.graph_objects as go
from functools import lru_cache
from flask import current_app




# Database path in static folder
DB_PATH = 'static/stock_data.db'

# Cache configuration
CACHE_DURATION = 300  # 5 minutes in seconds

@lru_cache(maxsize=1)
def get_top_gainers_data(timestamp):
    """Cache top gainers data with optimized queries"""
    conn = get_db_connection()
    try:
        # First query: Get top 20 stocks by percentage change (matching your original logic)
        top_stocks_query = """
        WITH LastWeekData AS (
            SELECT
                symbol,
                open,
                close,
                ((close - open) / open * 100) as percentage_change,
                date,
                ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
            FROM stock_prices
            WHERE timeframe = 'weekly'
        )
        SELECT
            symbol,
            open,
            close,
            percentage_change
        FROM LastWeekData
        WHERE rn = 1
        ORDER BY percentage_change DESC
        LIMIT 20
        """
        
        # Get top 20 symbols with their current week data
        current_week_data = pd.read_sql_query(top_stocks_query, conn)
        
        if current_week_data.empty:
            return []
            
        # Get symbols list for volume query
        symbols_list = "', '".join(current_week_data['symbol'].tolist())
        
        # Get volume data for these symbols (matching your original logic)
        volume_query = f"""
        WITH RankedData AS (
            SELECT
                symbol,
                volume,
                date,
                ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as week_num
            FROM stock_prices
            WHERE timeframe = 'weekly'
            AND symbol IN ('{symbols_list}')
        )
        SELECT
            symbol,
            volume,
            week_num
        FROM RankedData
        WHERE week_num <= 5
        ORDER BY symbol, week_num
        """
        
        # Get volume data
        volume_data = pd.read_sql_query(volume_query, conn)
        
        # Process volume data (keeping your original logic)
        volume_pivot = volume_data.pivot(
            index='symbol',
            columns='week_num',
            values='volume'
        )
        
        # Create final dataframe
        final_data = current_week_data.copy()
        
        # Calculate volume changes (keeping your original logic)
        for i in range(1, 5):
            if i+1 in volume_pivot.columns:
                week_current = volume_pivot[i]
                week_prev = volume_pivot[i+1]
                
                # Calculate percentage change with handling for zero values
                mask = (week_prev != 0) & week_prev.notnull() & week_current.notnull()
                pct_change = pd.Series(index=week_current.index, data=0.0)
                pct_change[mask] = ((week_current[mask] - week_prev[mask]) / week_prev[mask] * 100).round(2)
                
                final_data[f'vol_change_week{i}'] = final_data['symbol'].map(pct_change)
        
        # Ensure percentage_change is numeric and sort
        final_data['percentage_change'] = pd.to_numeric(final_data['percentage_change'], errors='coerce')
        final_data = final_data.sort_values('percentage_change', ascending=False)
        
        return final_data.to_dict('records')
        
    except Exception as e:
        current_app.logger.error(f"Error in get_top_gainers_data: {str(e)}")
        print(f"Error in get_top_gainers_data: {str(e)}")  # For immediate debugging
        return []
    finally:
        conn.close()



def calculate_macd(close_prices, slow=26, fast=12, signal=9):
    """
    Calculate MACD (Moving Average Convergence Divergence)
    
    Parameters:
    -----------
    close_prices : pd.Series or array-like
        The closing prices of the asset
    slow : int, default 26
        The longer period for EMA calculation
    fast : int, default 12
        The shorter period for EMA calculation
    signal : int, default 9
        The signal line period
        
    Returns:
    --------
    tuple: (macd_line, signal_line, histogram)
        macd_line: The MACD line (difference between fast and slow EMAs)
        signal_line: The signal line (EMA of MACD line)
        histogram: The MACD histogram (2 * (MACD line - signal line))
    """
    # Convert input to pandas Series if it isn't already
    close_prices = pd.Series(close_prices)
    
    # Calculate fast and slow EMAs
    ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
    ema_slow = close_prices.ewm(span=slow, adjust=False).mean()
    
    # Calculate MACD line
    macd_line = ema_fast - ema_slow
    
    # Calculate signal line
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    
    # Calculate histogram
    histogram = 2 * (macd_line - signal_line)
    return macd_line, signal_line, histogram
    #return dif, dea, macd

@lru_cache(maxsize=100)
def get_stock_data(symbol, timestamp):
    """Cache stock data with LRU cache decorator"""
    conn = get_db_connection()
    try:
        plot_data = {'daily': {}, 'weekly': {}}
        
        for timeframe in ['daily', 'weekly']:
            query = """
                SELECT date, open, high, low, close
                FROM stock_prices
                WHERE symbol = ?
                AND timeframe = ?
                AND strftime('%w', date) NOT IN ('0', '6')
                ORDER BY date DESC
                LIMIT ?
            """
            
            # Set different limits for daily and weekly data
            limit = 120 if timeframe == 'daily' else 104  # 52 weeks for weekly data
            
            cursor = conn.execute(query, (symbol, timeframe, limit))
            rows = cursor.fetchall()
            
            if rows:
                dates, opens, highs, lows, closes = zip(*rows)
                
                # Calculate MACD (on reversed data for correct sequence)
                closes_series = pd.Series(closes[::-1])
                print('calculate macd')
                dif, dea, macd = calculate_macd(closes_series)
                
                plot_data[timeframe] = {
                    'dates': list(reversed(dates)),
                    'open': list(reversed(opens)),
                    'high': list(reversed(highs)),
                    'low': list(reversed(lows)),
                    'close': list(reversed(closes)),
                    'macd': {
                        'dif': dif[::-1].tolist(),
                        'dea': dea[::-1].tolist(),
                        'macd': macd[::-1].tolist()
                    }
                }
            else:
                plot_data[timeframe] = {
                    'dates': [], 'open': [], 'high': [], 'low': [], 'close': [],
                    'macd': {'dif': [], 'dea': [], 'macd': []}
                }
        
        return plot_data
            
    finally:
        conn.close()

@lru_cache(maxsize=1)
def get_database_stats(timestamp):
    """Get cached database statistics"""
    conn = get_db_connection()
    try:
        # Use a single query to get both counts
        stats_query = """
        SELECT 
            (SELECT COUNT(*) FROM stock_prices) as total_records,
            (SELECT COUNT(DISTINCT symbol) FROM stock_prices) as total_stocks
        """
        
        cursor = conn.execute(stats_query)
        stats = cursor.fetchone()
        
        return {
            'total_records': stats[0],
            'total_stocks': stats[1],
            'database_size': get_database_size()
        }
    finally:
        conn.close()

def get_cache_timestamp():
    """Return a timestamp rounded to 5-minute intervals for cache key"""
    now = datetime.now()
    return now.replace(second=0, microsecond=0).timestamp() // CACHE_DURATION * CACHE_DURATION



def get_database_size():
    """Get the size of the SQLite database in GB"""
    try:
        size_in_bytes = os.path.getsize(DB_PATH)
        size_in_gb = size_in_bytes / (1024 * 1024 * 1024)  # Convert to GB
        return size_in_gb
    except Exception as e:
        print(f"Error getting database size: {str(e)}")
        return 0


def ensure_static_folder():
    """Ensure static folder exists"""
    if not os.path.exists('static'):
        os.makedirs('static')

def get_db_connection():
    """Get database connection"""
    ensure_static_folder()
    return sqlite3.connect(DB_PATH)

def initialize_database():
    """
    Initialize the database with all necessary columns
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drop existing table if it exists
    cursor.execute('DROP TABLE IF EXISTS stock_prices')
    
    # Create main table with all columns including Dividends and Stock Splits
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
    
    # Create indices for better query performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON stock_prices(symbol)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timeframe ON stock_prices(timeframe)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON stock_prices(date)')
    
    conn.commit()
    conn.close()

# Flask web application
app = Flask(__name__)




#@app.route('/stock/<symbol>')
def stock_data(symbol):
    """Show data for a specific stock"""
    conn = get_db_connection()
    
    # Get summary counts
    total_records = pd.read_sql_query(
        "SELECT COUNT(*) as count FROM stock_prices",
        conn
    ).iloc[0]['count']
    
    total_stocks = pd.read_sql_query(
        "SELECT COUNT(DISTINCT symbol) as count FROM stock_prices",
        conn
    ).iloc[0]['count']
    
    # Get data for specific stock
    daily_data = pd.read_sql_query(
        "SELECT * FROM stock_prices WHERE symbol=? AND timeframe='daily' ORDER BY date DESC LIMIT 100",
        conn,
        params=(symbol,)
    )
    
    weekly_data = pd.read_sql_query(
        "SELECT * FROM stock_prices WHERE symbol=? AND timeframe='weekly' ORDER BY date DESC LIMIT 52",
        conn,
        params=(symbol,)
    )
    
    conn.close()
    
    return render_template('stock_data.html',
                         symbol=symbol,
                         total_records=total_records,
                         total_stocks=total_stocks,
                         daily_data=daily_data.to_dict('records'),
                         weekly_data=weekly_data.to_dict('records'))

# New route for top-gainers.html links
@app.route('/stock/<symbol>')
def stock(symbol):
    """Handle stock links from top-gainers page"""
    return redirect(url_for('stock_detail', symbol=symbol))


def get_data_summary():
    conn = get_db_connection()
    counts = pd.read_sql_query('''
        SELECT 
            symbol,
            timeframe,
            COUNT(*) as count,
            MIN(date) as start_date,
            MAX(date) as end_date
        FROM stock_prices 
        GROUP BY symbol, timeframe
    ''', conn)
    conn.close()
    counts=counts.to_dict('records')
    return counts

@app.route('/summary')
def summary():
    # Your existing code to get the counts data
    counts = get_data_summary()  # Your function to get summary data
    return render_template('summary.html', counts=counts)

@app.route('/top-gainers')
def top_gainers():
    """Show top 20 stocks by percentage increase from last week with optimized performance"""
    try:
        # Get cached data using current timestamp
        cache_timestamp = get_cache_timestamp()
        result_dict = get_top_gainers_data(cache_timestamp)
        
        return render_template('top_gainers.html', top_stocks=result_dict)
    
    except Exception as e:
        current_app.logger.error(f"Error in top_gainers route: {str(e)}")
        return render_template('top_gainers.html', top_stocks=[])


@app.route('/volume-gainers')
def volume_gainers():
    """Show top 20 stocks by volume increase using optimized SQLite query"""
    conn = get_db_connection()
    print('start ...')
    try:
        # Get the latest date that's a Monday
        date_query = """
        SELECT MAX(date) 
        FROM stock_prices 
        WHERE timeframe = 'weekly' AND symbol='AAPL'
        """
        latest_date = pd.read_sql_query(date_query, conn).iloc[0, 0]
        print(f"Latest Monday: {latest_date}")
        
        # Get the previous week's Monday
        prev_date = pd.read_sql_query(
            """
            SELECT MAX(date) 
            FROM stock_prices 
            WHERE timeframe = 'weekly' AND symbol='AAPL'
            AND date < ?
            -- OR where strftime('%w', date) = '1'  -- If your dates are in YYYY-MM-DD format
            """,
            conn,
            params=(latest_date,)
        ).iloc[0, 0]
        print(f"Previous Monday: {prev_date}")

        # Direct comparison of two specific dates is much faster in SQLite
        volume_query = """
        WITH CurrentWeek AS (
            SELECT symbol, volume, open, close
            FROM stock_prices
            WHERE timeframe = 'weekly' 
            AND date = ?
        ),
        PrevWeek AS (
            SELECT symbol, volume as prev_volume
            FROM stock_prices
            WHERE timeframe = 'weekly' 
            AND date = ?
        )
        SELECT 
            c.symbol,
            c.open as current_open,
            c.close as current_close,
            c.volume as current_volume,
            p.prev_volume,
            ROUND(((c.volume - p.prev_volume) * 100.0 / p.prev_volume), 2) as volume_change
        FROM CurrentWeek c
        JOIN PrevWeek p ON c.symbol = p.symbol
        WHERE p.prev_volume > 0
        ORDER BY volume_change DESC
        LIMIT 20
        """
        
        # Execute with specific dates
        df = pd.read_sql_query(
            volume_query,
            conn,
            params=(latest_date, prev_date),
            coerce_float=True
        )
        print(df)
        
        # Ensure integer types for volumes
        df['current_volume'] = df['current_volume'].astype(int)
        df['prev_volume'] = df['prev_volume'].astype(int)

        print(df)
        
        return render_template(
            'volume_gainers.html',
            top_stocks=df.to_dict('records')
        )
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('volume_gainers.html', top_stocks=[])
    
    finally:
        conn.close()


@app.route('/stockdetail/<symbol>')
def stock_detail(symbol):
    try:
        cache_timestamp = get_cache_timestamp()
        plot_data = get_stock_data(symbol, cache_timestamp)
        return render_template(
            'stock_detail.html',
            symbol=symbol,
            plot=plot_data
        )
    except Exception as e:
        print(f"Error in stock_detail: {str(e)}")
        return jsonify({"error": str(e)}), 500


def create_indexes():
    conn = get_db_connection()
    with conn:
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_timeframe 
        ON stock_prices(symbol, timeframe, date DESC)
        """)
    conn.close()

def create_top_gainers_indexes():
    conn = get_db_connection()
    try:
        with conn:
            # Index for weekly data queries
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_weekly_date 
            ON stock_prices(timeframe, date, symbol)
            WHERE timeframe = 'weekly'
            """)
    finally:
        conn.close()

@app.route('/clear_cache')
def clear_cache():
    get_stock_data.cache_clear()
    return "Cache cleared"

def get_filtered_stocks():
    """
    Get filtered stocks based on user criteria with date ranges from database using weekly timeframe
    """
    # Get filter parameters from request
    limit = request.args.get('limit', 50, type=int)
    min_price = request.args.get('min_price', 0, type=float)
    min_volume = request.args.get('min_volume', 0, type=int)
    min_price_change = request.args.get('min_price_change', -100, type=float)  # Changed from min_volume_change
    sort_by = request.args.get('sort_by', 'volume_change')
    sort_order = request.args.get('sort_order', 'DESC')
    
    conn = get_db_connection()
    try:
        # Get the latest two weeks' dates from weekly timeframe data
        date_range_query = """
        SELECT 
            MAX(date) as last_week_end,
            MIN(date) as last_week_start,
            (SELECT date FROM stock_prices 
             WHERE symbol = 'AAPL' 
             AND timeframe = 'weekly'
             ORDER BY date DESC
             LIMIT 1 OFFSET 1) as prev_week
        FROM stock_prices
        WHERE symbol = 'AAPL'
        AND timeframe = 'weekly'
        ORDER BY date DESC
        LIMIT 1
        """
        
        cursor = conn.cursor()
        cursor.execute(date_range_query)
        dates = cursor.fetchone()
        
        last_week_end, last_week_start, prev_week = dates
        
        print(f"Date ranges from database:")
        print(f"Last week: {last_week_start} to {last_week_end}")
        print(f"Previous week: {prev_week}")
        
        # Main query using weekly timeframe
        query = """
        WITH LastWeekData AS (
            SELECT 
                symbol,
                open as week_open,
                close as week_close,
                volume as week_volume
            FROM stock_prices
            WHERE date = ?
            AND timeframe = 'weekly'
        ),
        PrevWeekData AS (
            SELECT 
                symbol,
                volume as prev_week_volume
            FROM stock_prices
            WHERE date = ?
            AND timeframe = 'weekly'
        ),
        CombinedData AS (
            SELECT 
                lw.symbol,
                lw.week_open,
                lw.week_close,
                lw.week_volume,
                CASE 
                    WHEN pw.prev_week_volume > 0 
                    THEN ROUND(((lw.week_volume - pw.prev_week_volume) * 100.0 / NULLIF(pw.prev_week_volume, 0)), 2)
                    ELSE 0 
                END as volume_change_pct,
                CASE 
                    WHEN lw.week_open > 0 
                    THEN ROUND(((lw.week_close - lw.week_open) * 100.0 / NULLIF(lw.week_open, 0)), 2)
                    ELSE 0 
                END as price_change_pct
            FROM LastWeekData lw
            JOIN PrevWeekData pw ON lw.symbol = pw.symbol
            WHERE lw.week_close >= ?
            AND lw.week_volume >= ?
        )
        SELECT 
            symbol,
            ROUND(week_open, 2) as week_open,
            ROUND(week_close, 2) as week_close,
            week_volume,
            COALESCE(volume_change_pct, 0) as volume_change_pct,
            COALESCE(price_change_pct, 0) as price_change_pct
        FROM CombinedData
        WHERE price_change_pct >= ?  -- Changed from volume_change_pct
        ORDER BY 
            CASE ? 
                WHEN 'volume' THEN week_volume
                WHEN 'price' THEN week_close
                WHEN 'volume_change' THEN volume_change_pct
                WHEN 'price_change' THEN price_change_pct
            END
        """ + f" {sort_order} " + """
        LIMIT ?
        """
        
        params = (
            last_week_end,    # For LastWeekData
            prev_week,        # For PrevWeekData
            min_price, min_volume,  # Filter conditions for price and volume
            min_price_change,      # Changed from min_volume_change
            sort_by,          # Sort column
            limit            # Result limit
        )
        
        cursor.execute(query, params)
        
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        

        
        return results
        
    finally:
        conn.close()

@app.route('/stock_filter')
def stock_filter():
    """Render stock filter page"""
    return render_template('stock_filter.html')

@app.route('/api/filtered_stocks')
def filtered_stocks():
    """API endpoint for filtered stocks"""
    try:
        results = get_filtered_stocks()
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/')
def index():
    """Show all available stock data"""
    try:
        # Get cached stats using current timestamp rounded to cache duration
        cache_timestamp = get_cache_timestamp()
        stats = get_database_stats(cache_timestamp)
        print('wil return the index')
        return render_template('index.html',
                             total_records=stats['total_records'],
                             total_stocks=stats['total_stocks'],
                             database_size=stats['database_size'])
    except Exception as e:
        print('Error,Happend')
        app.logger.error(f"Error in index route: {str(e)}")
        return render_template('error.html', error=str(e)), 500

if __name__ == '__main__':
    # Initialize database if it doesn't exist
    # create_indexes()
    # create_top_gainers_indexes()
    if not os.path.exists(DB_PATH):
        initialize_database()
    
    app.run(debug=True,host='0.0.0.0')