import sqlite3
from datetime import datetime, timedelta
import pandas as pd

class Ticker:
    def __init__(self, symbol):
        self.symbol = symbol.upper()
        self.db_path = 'static/stock_data.db'
        
        # Verify that the symbol exists in the database
        if not self._symbol_exists():
            return None
            #raise ValueError(f"Symbol {self.symbol} not found in local database")
    
    def _symbol_exists(self):
        """Check if the symbol exists in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM stock_prices WHERE symbol = ?", 
            (self.symbol,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def _get_date_range(self, period):
        """Convert period string to start and end dates"""
        end_date = datetime.now()
        
        period_map = {
            "1d": timedelta(days=1),
            "5d": timedelta(days=5),
            "1mo": timedelta(days=30),
            "3mo": timedelta(days=90),
            "6mo": timedelta(days=180),
            "1y": timedelta(days=365),
            "2y": timedelta(days=730),
            "5y": timedelta(days=1825),
            "ytd": timedelta(days=(end_date - datetime(end_date.year, 1, 1)).days),
            "max": timedelta(days=36500)  # 100 years should cover all historical data
        }
        
        if period not in period_map:
            raise ValueError(f"Invalid period: {period}. Valid periods are: {', '.join(period_map.keys())}")
            
        start_date = end_date - period_map[period]
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    
    def history(self, period="1mo", interval="1d", start=None, end=None):
        """
        Fetch historical data from local database
        
        Parameters:
        - period: time period to download (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max)
        - interval: data interval (only '1d' supported in this version)
        - start: start date string 'YYYY-MM-DD' (optional)
        - end: end date string 'YYYY-MM-DD' (optional)
        
        Returns:
        - pandas DataFrame with historical data
        """
        if interval not in ["1d", "1wk"]:
            raise ValueError("Only daily interval ('1d') is supported in this version")
            
        conn = sqlite3.connect(self.db_path)
        
        # Use provided dates or calculate from period
        if start is None or end is None:
            start_date, end_date = self._get_date_range(period)
        else:
            start_date, end_date = start, end

        # Map interval to timeframe
        timeframe = 'daily' if interval == '1d' else 'weekly'
            
        query = """
        SELECT date, open, high, low, close, volume, dividends, stock_splits
        FROM stock_prices
        WHERE symbol = ?
        AND date BETWEEN ? AND ?
        AND timeframe = ?
        ORDER BY date ASC
        """
        
        df = pd.read_sql_query(
            query, 
            conn, 
            params=(self.symbol, start_date, end_date, timeframe),
            parse_dates=['date']
        )
        conn.close()
        
        if df.empty:
            return []
            #raise ValueError(f"No data found for {self.symbol} in specified date range")
            
        # Set date as index to match yfinance format
        df.set_index('date', inplace=True)
        
        # Ensure column names match yfinance format
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
        
        return df

# Function to mimic yfinance's download functionality
def download(tickers, period="1mo", interval="1d", start=None, end=None):
    """
    Download data for multiple tickers
    
    Parameters:
    - tickers: string or list of strings
    - period: time period to download
    - interval: data interval (only '1d' supported)
    - start: start date string 'YYYY-MM-DD' (optional)
    - end: end date string 'YYYY-MM-DD' (optional)
    
    Returns:
    - pandas DataFrame with MultiIndex (ticker, field)
    """
    if isinstance(tickers, str):
        tickers = tickers.split()
        
    all_data = {}
    for ticker in tickers:
        try:
            stock = Ticker(ticker)
            all_data[ticker] = stock.history(period=period, interval=interval, 
                                          start=start, end=end)
        except ValueError as e:
            print(f"Error fetching {ticker}: {str(e)}")
            continue
    
    if not all_data:
        raise ValueError("No data fetched for any tickers")
        
    if len(tickers) == 1:
        return list(all_data.values())[0]
        
    # Combine all DataFrames into a single DataFrame with MultiIndex
    combined_data = pd.concat(all_data, axis=1, keys=all_data.keys())
    return combined_data