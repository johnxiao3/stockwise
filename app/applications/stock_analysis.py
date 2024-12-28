import os
import sys
from datetime import datetime, timedelta
import pandas as pd

# Add the parent directory to system path for local yfinance import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf

def calculate_price_changes(symbols):
    """
    Calculate close to open and close to previous close price changes for given symbols
    """
    results = []
    
    for symbol in symbols:
        try:
            # Get today's and yesterday's data
            stock = yf.Ticker(symbol)
            hist = stock.history(period="5d")
            
            if len(hist) < 2:
                print(f"Not enough data for {symbol}")
                continue
                
            # Today's data
            today_open = hist['Open'].iloc[-1]
            today_close = hist['Close'].iloc[-1]
            
            # Previous day's close
            prev_close = hist['Close'].iloc[-2]
            
            # Calculate percentage changes
            close_to_open_change = ((today_close - today_open) / today_open) * 100
            close_to_prev_close_change = ((today_close - prev_close) / prev_close) * 100
            
            results.append({
                'Symbol': symbol,
                'Close-Open %': close_to_open_change,
                'Close-PrevClose %': close_to_prev_close_change,
                'Open': today_open,
                'Close': today_close,
                'Prev Close': prev_close
            })
            
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")
            
    return results

def main():
    # List of stock symbols
    symbols = ['GEVO', 'VNET', 'ULS', 'SDHC', 'GGB', 'MLR', 'TM', 'KC', 'TGNA', 'KNSA']
    
    # Calculate price changes
    results = calculate_price_changes(symbols)
    
    # Convert results to DataFrame
    df = pd.DataFrame(results)
    
    # Format the numeric columns
    df['Close-Open %'] = df['Close-Open %'].map('{:,.2f}%'.format)
    df['Close-PrevClose %'] = df['Close-PrevClose %'].map('{:,.2f}%'.format)
    df['Open'] = df['Open'].map('${:,.2f}'.format)
    df['Close'] = df['Close'].map('${:,.2f}'.format)
    df['Prev Close'] = df['Prev Close'].map('${:,.2f}'.format)
    
    # Print current date
    print(f"\nPrice Changes for {datetime.now().strftime('%Y-%m-%d')}\n")
    
    # Print formatted DataFrame
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()