import os
import sys
import sqlite3
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf
from services.calculate_turnover_rate import get_latest_turnover_rate
from datetime import datetime
import pytz
import warnings
warnings.filterwarnings("ignore")

def get_tickers_and_mcap():
    """Get all stock tickers and market caps from database."""
    conn = sqlite3.connect('./static/stock_data.db')
    query = "SELECT Symbol, Market_Cap FROM nasdaq_screener"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def calculate_rsi(data, window):
    """Calculate RSI for the given data and window."""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    rs = gain.copy()
    rs[loss != 0] = gain[loss != 0] / loss[loss != 0]
    rs[loss == 0] = 100
    
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_metrics(ticker):
    """Calculate all required metrics for a given ticker."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="3mo")
        if len(data) < 7:  # Need enough data for calculations
            return None
            
        # Calculate RSI
        data['RSI'] = calculate_rsi(data, window=6)
        
        # Get latest metrics
        today_volume = data['Volume'].iloc[-1]
        today_price = data['Close'].iloc[-1]
        prev_volume = data['Volume'].iloc[-2]
        
        # Calculate volume change
        volume_change = ((today_volume - prev_volume) / prev_volume) * 100 if prev_volume > 0 else 0
        
        # Calculate trading value
        trading_value = today_price * today_volume
        
        return {
            'today_price': today_price,
            'today_volume': today_volume,
            'rsi': data['RSI'].iloc[-1],
            'trading_value': trading_value,
            'volume_change': volume_change
        }
        
    except Exception as e:
        print(f"Error processing {ticker}: {str(e)}")
        return None

def create_html_table(df):
    """Create HTML table with the specified columns."""
    html = '''
    <html>
    <head>
    <style>
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .stock-link {
            color: #0066cc;
            text-decoration: none;
        }
    </style>
    </head>
    <body>
    <h2>Top 10 Stocks by Volume Change</h2>
    <table>
        <tr>
            <th>Ticker</th>
            <th>Close Price</th>
            <th>Market Cap ($B)</th>
            <th>Volume(M)</th>
            <th>Turnover Rate (%)</th>
            <th>RSI(6)</th>
            <th>Value($M)</th>
            <th>Vol Chg(%)</th>
        </tr>
    '''
    
    for _, row in df.iterrows():
        html += f'''
        <tr>
            <td><a href="https://www.tianshen.store/stock/{row['ticker']}" class="stock-link">{row['ticker']}</a></td>
            <td>{row['today_price']:.2f}</td>
            <td>{row['market_cap']/1e9:.2f}</td>
            <td>{row['today_volume']/1e6:.2f}</td>
            <td>{row['turnover_rate']:.2f}</td>
            <td>{row['rsi']:.2f}</td>
            <td>{row['trading_value']/1e6:.2f}</td>
            <td>{row['volume_change_pct']:.2f}</td>
        </tr>
        '''
    
    html += '''
    </table>
    </body>
    </html>
    '''
    return html

def analyze_volume():
    print("Fetching tickers from database...")
    stocks_df = get_tickers_and_mcap()
    results = []
    
    total_stocks = len(stocks_df)
    for idx, (ticker, mcap) in enumerate(zip(stocks_df['Symbol'], stocks_df['Market_Cap']), 1):
        print(f'Processing {idx}/{total_stocks}: {ticker}\r', end='')
        
        metrics = calculate_metrics(ticker)
        
        if metrics and metrics['trading_value'] > 1000000:  # Filter by trading value > 1M
            # Make sure all keys match the column names we'll use later
            results.append({
                'ticker': ticker,
                'market_cap': float(mcap),
                'today_price': metrics['today_price'],
                'today_volume': metrics['today_volume'],
                'rsi': metrics['rsi'],
                'trading_value': metrics['trading_value'],
                'volume_change_pct': metrics['volume_change']  # Changed to match calculate_metrics
            })
    
    results_df = pd.DataFrame(results)
    # Update sort column name to match
    sorted_df = results_df.sort_values('volume_change_pct', ascending=False)
    top_10_df = sorted_df.head(10)
    
    # Get turnover rates for top 10 stocks only
    print("\nGetting turnover rates for top 10 stocks...")
    turnover_rates = []
    for ticker in top_10_df['ticker']:
        turnover_info = get_latest_turnover_rate(ticker)
        turnover_rates.append(turnover_info['turnover_rate'] if turnover_info else 0)
    
    # Add turnover rates to top 10 dataframe
    top_10_df['turnover_rate'] = turnover_rates
    
    # Generate HTML table and save
    html_content = create_html_table(top_10_df)
    with open('./static/daily_email_volume.txt', 'w') as f:
        f.write(html_content)
    
    # Print table with consistent format
    print("\nTop 10 Stocks by Volume Change:")
    print("-" * 70)
    print(f"{'Ticker':<8} {'Close':<8} {'MCap($B)':<10} {'Volume(M)':<12} {'Turnover%':<10} {'RSI(6)':<8} {'Value($M)':<10} {'Vol Chg(%)':<10}")
    print("-" * 70)
    
    for _, row in top_10_df.iterrows():
        print(f"{row['ticker']:<8} {row['today_price']:<8.2f} {row['market_cap']/1e9:<10.2f} "
              f"{row['today_volume']/1e6:<12.2f} {row['turnover_rate']:<10.2f} "
              f"{row['rsi']:<8.2f} {row['trading_value']/1e6:<10.2f} {row['volume_change_pct']:<10.2f}")
    print("-" * 70)
    
    # Print tickers list format
    print("\nStock list format:")
    top_tickers = top_10_df['ticker'].tolist()
    print('[' + '\n'.join(f"'{ticker}'," if i < len(top_tickers)-1 else f"'{ticker}'" 
                       for i, ticker in enumerate(top_tickers)) + ']')
    
    return top_tickers

if __name__ == "__main__":
    analyze_volume()