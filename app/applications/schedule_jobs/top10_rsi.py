import os
import sys
import sqlite3
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf
from applications.schedule_jobs.url_configure import *
from services.calculate_turnover_rate import get_latest_turnover_rate
import warnings
warnings.filterwarnings("ignore")

def create_html_table_rsi(df):
    """Create HTML table with hyperlinks for RSI data."""
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
    <h2>Top 10 Stocks with Lowest RSI (6)</h2>
    <table>
        <tr>
            <th>Ticker</th>
            <th>Close Price</th>
            <th>Market Cap ($B)</th>
            <th>Volume(M)</th>
            <th>Turnover Rate (%)</th>
            <th>RSI(6)</th>
            <th>Value($M)</th>
        </tr>
    '''
    
    for _, row in df.iterrows():
        trading_value = row['today_price'] * row['today_volume']
        html += f'''
        <tr>
            <td><a href="http://{BASE_URL}/stock/{row['ticker']}" class="stock-link">{row['ticker']}</a></td>
            <td>{row['today_price']:.2f}</td>
            <td>{row['market_cap']/1e9:.2f}</td>
            <td>{row['today_volume']/1e6:.2f}</td>
            <td>{row['turnover_rate']:.2f}</td>
            <td>{row['rsi']:.2f}</td>
            <td>{trading_value/1e6:.2f}</td>
        </tr>
        '''
    
    html += '''
    </table>
    </body>
    </html>
    '''
    return html

def get_tickers_and_mcap():
    conn = sqlite3.connect('./static/stock_data.db')
    query = "SELECT Symbol, Market_Cap FROM nasdaq_screener"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def calculate_rsi(data, window):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    
    # Handle division by zero
    rs = gain.copy()
    rs[loss != 0] = gain[loss != 0] / loss[loss != 0]
    rs[loss == 0] = 100  # When loss is 0, RSI should be 100
    
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_metrics(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="3mo")  # More data for reliable RSI
        if len(data) < 7:  # Need enough data for RSI calculation
            return None
            
        data['RSI'] = calculate_rsi(data, window=6)
        
        today_volume = data['Volume'].iloc[-1]
        today_price = data['Close'].iloc[-1]
        today_trading_value = today_price * today_volume
        current_rsi = data['RSI'].iloc[-1]
        
        return {
            'rsi': current_rsi,
            'today_volume': today_volume,
            'today_price': today_price,
            'today_trading_value': today_trading_value
        }
        
    except Exception as e:
        print(f"Error processing {ticker}: {str(e)}")
        return None

def analyze_rsi():
    print("Fetching tickers from database...")
    stocks_df = get_tickers_and_mcap()
    results = []
    
    total_stocks = len(stocks_df)
    for idx, (ticker, mcap) in enumerate(zip(stocks_df['Symbol'], stocks_df['Market_Cap']), 1):
        print(f'Processing {idx}/{total_stocks}: {ticker}\r', end='')
        
        metrics = calculate_metrics(ticker)
        if metrics:
            # Calculate trading value
            trading_value = metrics['today_price'] * metrics['today_volume']
            
            # Only include if trading value > 1M
            if trading_value > 1000000:
                results.append({
                    'ticker': ticker,
                    'market_cap': float(mcap),
                    'rsi': metrics['rsi'],
                    'today_volume': metrics['today_volume'],
                    'today_price': metrics['today_price'],
                    'trading_value': trading_value
                })
    
    results_df = pd.DataFrame(results)
    filtered_df = results_df[results_df['rsi'] > 0]  # Only filter for positive RSI
    sorted_df = filtered_df.sort_values('rsi', ascending=True)
    top_10_df = sorted_df.head(10)
    
    # Now get turnover rates only for top 10 stocks
    print("\nGetting turnover rates for top 10 stocks...")
    turnover_rates = []
    for ticker in top_10_df['ticker']:
        turnover_info = get_latest_turnover_rate(ticker)
        turnover_rates.append(turnover_info['turnover_rate'] if turnover_info else 0)
    
    # Add turnover rates to top 10 dataframe
    top_10_df['turnover_rate'] = turnover_rates
    
    # Generate HTML table and save
    html_content = create_html_table_rsi(top_10_df)
    with open('./static/daily_email_rsi.txt', 'w') as f:
        f.write(html_content)
        
    # Print table with consistent format
    print("\nTop 10 Stocks with Lowest RSI (6):")
    print("-" * 70)
    print(f"{'Ticker':<8} {'Close':<8} {'MCap($B)':<10} {'Volume(M)':<12} {'Turnover%':<10} {'RSI(6)':<8} {'Value($M)':<10}")
    print("-" * 70)
    
    for _, row in top_10_df.iterrows():
        trading_value = row['today_price'] * row['today_volume']
        print(f"{row['ticker']:<8} {row['today_price']:<8.2f} {row['market_cap']/1e9:<10.2f} "
              f"{row['today_volume']/1e6:<12.2f} {row['turnover_rate']:<10.2f} "
              f"{row['rsi']:<8.2f} {trading_value/1e6:<10.2f}")
    print("-" * 70)
    
    # Print tickers list format
    print("\nStock list format:")
    top_tickers = top_10_df['ticker'].tolist()
    print('[' + '\n'.join(f"'{ticker}'," if i < len(top_tickers)-1 else f"'{ticker}'" 
                       for i, ticker in enumerate(top_tickers)) + ']')
    
    return top_tickers

if __name__ == "__main__":
    analyze_rsi()