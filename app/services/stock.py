from typing import List, Dict, Optional
import pandas as pd

from ..database import get_db_connection, get_database_size
from .analysis import calculate_macd

from .cache import database_stats_cache, stock_data_cache, top_gainers_cache


def create_indexes():
    """Create necessary database indexes"""
    conn = get_db_connection()
    with conn:
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_timeframe 
        ON stock_prices(symbol, timeframe, date DESC)
        """)
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_weekly_date 
        ON stock_prices(timeframe, date, symbol)
        WHERE timeframe = 'weekly'
        """)
    conn.close()


def create_top_gainers_indexes():
    """Create indexes for top gainers queries"""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_weekly_date 
            ON stock_prices(timeframe, date, symbol)
            WHERE timeframe = 'weekly'
            """)
    finally:
        conn.close()

@database_stats_cache
def get_database_stats(timestamp):
    """Get cached database statistics"""
    conn = get_db_connection()
    try:
        # For SQLite, using COUNT(*) on rowid is faster than COUNT(*)
        stats_query = """
        SELECT
            (SELECT MAX(_ROWID_) FROM stock_prices) as total_records,
            (SELECT COUNT(DISTINCT symbol)
             FROM stock_prices
             WHERE timeframe = 'weekly') as total_stocks
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

@top_gainers_cache
def get_top_gainers_data(timestamp):
    """Cache top gainers data with optimized queries"""
    conn = get_db_connection()
    try:
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
        
        current_week_data = pd.read_sql_query(top_stocks_query, conn)
        
        if current_week_data.empty:
            return []
            
        symbols_list = "', '".join(current_week_data['symbol'].tolist())
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
        
        volume_data = pd.read_sql_query(volume_query, conn)
        volume_pivot = volume_data.pivot(index='symbol', columns='week_num', values='volume')
        final_data = current_week_data.copy()
        
        for i in range(1, 5):
            if i+1 in volume_pivot.columns:
                week_current = volume_pivot[i]
                week_prev = volume_pivot[i+1]
                mask = (week_prev != 0) & week_prev.notnull() & week_current.notnull()
                pct_change = pd.Series(index=week_current.index, data=0.0)
                pct_change[mask] = ((week_current[mask] - week_prev[mask]) / week_prev[mask] * 100).round(2)
                final_data[f'vol_change_week{i}'] = final_data['symbol'].map(pct_change)
        
        final_data['percentage_change'] = pd.to_numeric(final_data['percentage_change'], errors='coerce')
        final_data = final_data.sort_values('percentage_change', ascending=False)
        
        return final_data.to_dict('records')
    except Exception as e:
        print(f"Error in get_top_gainers_data: {str(e)}")
        return []
    finally:
        conn.close()

 # @stock_data_cache
def get_stock_data(symbol: str, timestamp: int):
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
            
            limit = 120 if timeframe == 'daily' else 104
            cursor = conn.execute(query, (symbol, timeframe, limit))
            rows = cursor.fetchall()
            
            if rows:
                dates, opens, highs, lows, closes = zip(*rows)
                closes_series = pd.Series(closes[::-1])
                dif, dea, macd = calculate_macd(closes_series)
                plot_data[timeframe] = {
                    'dates': list(reversed(dates)),
                    'open': list(reversed(opens)),
                    'high': list(reversed(highs)),
                    'low': list(reversed(lows)),
                    'close': list(reversed(closes)),
                    'macd': {
                        'dif': dif.tolist(),
                        'dea': dea.tolist(),
                        'macd': macd.tolist()
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

def get_data_summary():
    """Get summary of data in database"""
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
    return counts.to_dict('records')

def get_filtered_stocks(
    limit: int,
    min_price: float,
    min_volume: int,
    min_price_change: float,
    sort_by: str,
    sort_order: str
) -> List[Dict]:
    """Get filtered stocks based on criteria"""
    conn = get_db_connection()
    try:
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
        last_week_end, last_week_start, prev_week = cursor.fetchone()
        
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
        WHERE price_change_pct >= ?
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
        cursor.execute(query, (
            last_week_end,
            prev_week,
            min_price,
            min_volume,
            min_price_change,
            sort_by,
            limit
        ))
        
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    finally:
        conn.close()

