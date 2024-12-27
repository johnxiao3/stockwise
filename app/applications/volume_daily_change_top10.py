import os
import sys
import sqlite3
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf
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

def calculate_volume_metrics(ticker):
    """Calculate volume change and trading value metrics for a given ticker."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="5d")
        if len(data) < 2:
            return None
        
        today_volume = data['Volume'].iloc[-1]
        prev_volume = data['Volume'].iloc[-2]
        today_price = data['Close'].iloc[-1]
        prev_price = data['Close'].iloc[-2]
        
        if prev_volume == 0:
            return None
            
        volume_change_pct = ((today_volume - prev_volume) / prev_volume) * 100
        prev_trading_value = prev_price * prev_volume
        
        return {
            'volume_change_pct': volume_change_pct,
            'prev_volume': prev_volume,
            'prev_trading_value': prev_trading_value,
            'prev_price': prev_price
        }
    except Exception as e:
        print(f"Error processing {ticker}: {str(e)}")
        return None

def create_html_table(df):
    """Create HTML table with hyperlinks for stock tickers."""
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
    <h2>Top 10 Stocks by Volume Increase</h2>
    <table>
        <tr>
            <th>Ticker</th>
            <th>Market Cap ($B)</th>
            <th>Volume Change (%)</th>
            <th>Prev Volume</th>
            <th>Prev Price ($)</th>
            <th>Trading Value ($M)</th>
        </tr>
    '''
    
    for _, row in df.iterrows():
        html += f'''
        <tr>
            <td><a href="https://www.tianshen.store/stock/{row['ticker']}" class="stock-link">{row['ticker']}</a></td>
            <td>{row['market_cap']/1e9:.2f}</td>
            <td>{row['volume_change_pct']:.2f}</td>
            <td>{row['prev_volume']:.0f}</td>
            <td>{row['prev_price']:.2f}</td>
            <td>{row['prev_trading_value']/1e6:.2f}</td>
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
        metrics = calculate_volume_metrics(ticker)
        if metrics:
            results.append({
                'ticker': ticker,
                'market_cap': float(mcap),
                'volume_change_pct': metrics['volume_change_pct'],
                'prev_volume': metrics['prev_volume'],
                'prev_trading_value': metrics['prev_trading_value'],
                'prev_price': metrics['prev_price']
            })
    
    results_df = pd.DataFrame(results)
    filtered_df = results_df[results_df['prev_trading_value'] > 1000000]
    sorted_df = filtered_df.sort_values('volume_change_pct', ascending=False)
    
    # Generate HTML table
    html_content = create_html_table(sorted_df.head(10))
    
    # Save to file
    with open('./static/daily_email_volume.txt', 'w') as f:
        f.write(html_content)
    
    # Print tickers list format
    print("\nStock list format:")
    top_tickers = sorted_df.head(10)['ticker'].tolist()
    print('[' + '\n'.join(f"'{ticker}'," if i < len(top_tickers)-1 else f"'{ticker}'"
          for i, ticker in enumerate(top_tickers)) + ']')

if __name__ == "__main__":
    analyze_volume()