import os
import sys
import sqlite3
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf
import warnings
warnings.filterwarnings("ignore")

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
            results.append({
                'ticker': ticker,
                'market_cap': float(mcap),
                'rsi': metrics['rsi'],
                'today_volume': metrics['today_volume'],
                'today_price': metrics['today_price'],
                'today_trading_value': metrics['today_trading_value']
            })
    
    results_df = pd.DataFrame(results)
    filtered_df = results_df[(results_df['today_trading_value'] > 1000000) & (results_df['rsi'] > 0)]
    sorted_df = filtered_df.sort_values('rsi', ascending=True)
    
    print("\n\nTop 10 stocks with lowest RSI (6) and trading value > $1M:")
    print("Ticker | Market Cap ($B) | RSI | Today's Volume | Price ($) | Trading Value ($M)")
    print("-" * 85)
    
    for _, row in sorted_df.head(10).iterrows():
        print(f"{row['ticker']:<6} | {row['market_cap']/1e9:>13.2f} | "
              f"{row['rsi']:>8.2f} | {row['today_volume']:>13.0f} | "
              f"{row['today_price']:>9.2f} | {row['today_trading_value']/1e6:>15.2f}")
    
    # Print tickers in list format
    print("\nStock list format:")
    top_tickers = sorted_df.head(10)['ticker'].tolist()
    print('[' + '\n'.join(f"'{ticker}'," if i < len(top_tickers)-1 else f"'{ticker}'" 
                       for i, ticker in enumerate(top_tickers)) + ']')

if __name__ == "__main__":
    analyze_rsi()