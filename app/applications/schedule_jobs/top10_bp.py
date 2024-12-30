import os,sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf
from services.calculate_turnover_rate import get_latest_turnover_rate
import pandas as pd
import sqlite3
import numpy as np
from datetime import datetime
import pytz
#from post_filtered import run_post_process
import warnings
# Ignore all warnings
warnings.filterwarnings("ignore")
# add edt
edt = pytz.timezone("America/New_York")

def create_html_table_buypoint(df, title, filename):
    """Create HTML table for buy point data with additional columns."""
    html = f'''
    <html>
    <head>
    <style>
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .stock-link {{
            color: #0066cc;
            text-decoration: none;
        }}
    </style>
    </head>
    <body>
    <h2>{title}</h2>
    <table>
        <tr>
            <th>Ticker</th>
            <th>Close Price</th>
            <th>Market Cap ($B)</th>
            <th>Volume(M)</th>
            <th>Turnover Rate (%)</th>
            <th>RSI(6)</th>
            <th>BP</th>
        </tr>
    '''
    
    for _, row in df.iterrows():
        html += f'''
        <tr>
            <td><a href="https://www.tianshen.store/stock/{row['ticker']}" class="stock-link">{row['ticker']}</a></td>
            <td>{row['close_price']:.2f}</td>
            <td>{row['market_cap']:.2f}</td>
            <td>{row['volume']/1000000:.2f}</td>
            <td>{row['turnover_rate']:.2f}</td>
            <td>{row['rsi_6']:.2f}</td>
            <td>{row['BP']:.2f}</td>
        </tr>
        '''
    
    html += '''
    </table>
    </body>
    </html>
    '''
    return html

def get_market_cap(ticker):
    try:
        # Connect to the database
        conn = sqlite3.connect('./static/stock_data.db')
        cursor = conn.cursor()

         # Get column names
        #cursor.execute("PRAGMA table_info(nasdaq_screener)")
        #columns = cursor.fetchall()
        #print("Column structure:", columns)
        
        # Query to get market cap for the specific ticker
        query = """
        SELECT Market_Cap
        FROM nasdaq_screener 
        WHERE Symbol = ?
        """
        
        cursor.execute(query, (ticker,))
        result = cursor.fetchone()
        
        # Close the connection
        conn.close()
        
        # Return the market cap if found, otherwise return None
        return float(result[0]) if result else None
        
    except Exception as e:
        print(f"Error reading market cap for {ticker}: {str(e)}")
        return None


# Function to calculate EMA
def ema(data, window):
    return data.ewm(span=window, adjust=False).mean()

# Function to calculate MACD
def calculate_macd(data, slow=26, fast=12, signal=9):
    ema_fast = data.ewm(span=fast, adjust=False).mean()
    ema_slow = data.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = 2*(macd - macd_signal)
    return macd, macd_signal, macd_hist

# Function to calculate the nearest MACD histogram crossover
def calculate_crossover_days(macd_hist):
    for i in range(len(macd_hist)-1, 0, -1):
        if macd_hist[i] < 0 and macd_hist[i-1] >= 0:  # Positive to negative crossover
            return i, '-'
        elif macd_hist[i] > 0 and macd_hist[i-1] <= 0:
            return i,'+'
    return None, ''


def calculate_rsi(data, window):
    """Calculate the Relative Strength Index (RSI) for a given window."""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_wr(data, window):
    """Calculate the Williams %R for a given window."""
    highest_high = data['High'].rolling(window=window).max()
    lowest_low = data['Low'].rolling(window=window).min()
    wr = (highest_high - data['Close']) / (highest_high - lowest_low) * 100
    return wr

def calculate_kdj(data, period=9):
    """Calculate kdj_k, kdj_d, and kdj_j for the KDJ indicator."""
    # Calculate the lowest low and highest high over the specified period
    low_min = data['Low'].rolling(window=period, min_periods=1).min()
    high_max = data['High'].rolling(window=period, min_periods=1).max()

    # Calculate K% (fast stochastic) and rename it to kdj_k
    data['kdj_k'] = 100 * ((data['Close'] - low_min) / (high_max - low_min))

    # Smooth kdj_k to get kdj_d by applying a moving average
    data['kdj_d'] = data['kdj_k'].rolling(window=3, min_periods=1).mean()

    # Calculate kdj_j as 3 * kdj_k - 2 * kdj_d
    data['kdj_j'] = 3 * data['kdj_k'] - 2 * data['kdj_d']

    return data[['kdj_k', 'kdj_d', 'kdj_j']]

def add_technical_indicators(data):
    """Calculate and add RSI and WR to the DataFrame."""
    # Calculate RSI for 6, 12, and 24 periods
    data['RSI_6'] = calculate_rsi(data, 6)
    data['RSI_12'] = calculate_rsi(data, 12)
    data['RSI_24'] = calculate_rsi(data, 24)

    # Calculate Williams %R for 6 and 10 periods
    data['WR_6'] = calculate_wr(data, 6)
    data['WR_10'] = calculate_wr(data, 10)

    # Ensure you have the volume data in your DataFrame
    if 'Volume' not in data.columns:
        raise ValueError("The DataFrame must contain a 'Volume' column.")
    # Ensure the DataFrame contains volume data
    # Calculate KDJ and merge with the main data
    kdj_data = calculate_kdj(data)
    data = pd.concat([data, kdj_data], axis=1)
    return data

def find_buy_sell_points(x_valid,y_valid,hist_valid):
    # Initialize lists to hold the buy and sell points
    buy_points = []
    sell_points = []

    # Loop through y_valid to find buy and sell points
    i = 1
    sellbuy = 0
    while i < len(y_valid) - 2:
        # Check for buy point
        if sellbuy ==0 :
            if (y_valid[i + 2] < 50 and
                y_valid[i+1]>y_valid[i+2] and
                y_valid[i]>y_valid[i+2] and
                (y_valid[i]>50 or y_valid[i-1]>50) and
                hist_valid[i+2]>hist_valid[i+1] and
                (hist_valid[i]<0 or hist_valid[i]<hist_valid[i+1])):
                buy_points.append(x_valid[i + 2])   # The second point is the buy point
                i += 2  # Move to the point after the buy point
                sellbuy = 1
                continue
        
        # Check for sell point
        if sellbuy == 1:
            if (y_valid[i+2] > 50 and
                y_valid[i+1]<y_valid[i+2] and
                y_valid[i]<y_valid[i+2] and
                hist_valid[i+2]<hist_valid[i+1]):
                sell_points.append(x_valid[i + 2])  # The second point is the sell point
                i += 2  # Move to the point after the sell point
                sellbuy = 0
                continue
        
        i += 1  # Move to the next point
    return buy_points,sell_points

def find_buy_sell_points7(x_valid,y_valid,hist_valid):
    # Initialize lists to hold the buy and sell points
    buy_points = []
    sell_points = []

    y_valid=100-y_valid
    # Loop through y_valid to find buy and sell points
    i = 1
    sellbuy = 0
    while i < len(y_valid) - 2:
        # Check for buy point
        if sellbuy ==0 :
            if (y_valid[i + 2] < 50 and
                y_valid[i+1]>y_valid[i+2] and
                (y_valid[i]>50 or y_valid[i-1]>50) and
                hist_valid[i+2]>hist_valid[i+1] and
                (hist_valid[i]<0 or hist_valid[i]<hist_valid[i+1])):
                buy_points.append(x_valid[i + 2])   # The second point is the buy point
                #i += 2  # Move to the point after the buy point
                sellbuy = 1
                continue
        
        # Check for sell point
        if sellbuy == 1:
            #print(y_valid[i+2],y_valid[i+1],y_valid[i])
            if (y_valid[i+2] > 50 and
                y_valid[i+1]<y_valid[i+2] and
                (y_valid[i]<50 or y_valid[i-1]<50) and
                hist_valid[i+2]<hist_valid[i+1]):
                sell_points.append(x_valid[i + 2])  # The second point is the sell point
                #i += 2  # Move to the point after the sell point
                sellbuy = 0
                continue
        
        i += 1  # Move to the next point
    return buy_points,sell_points
def analyze_stocks(df):
    """
    Create two sorted lists:
    1. Sort by BP first, then turnover rate (descending)
    2. Sort by BP first, then RSI6 (ascending)
    Returns both lists of tickers
    """
    try:
        # First sorting: BP and turnover_rate
        sorted_by_turnover = df.sort_values(['BP', 'turnover_rate'], ascending=[True, False])
        top_10_turnover = sorted_by_turnover.head(10)
        
        # Second sorting: BP and RSI6
        sorted_by_rsi = df.sort_values(['BP', 'market_cap'], ascending=[True, False])
        top_10_rsi = sorted_by_rsi.head(10)
        
        # Create and save first table (BP and Turnover Rate)
        html_turnover = f'''
        <html><head><style>
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .stock-link {{ color: #0066cc; text-decoration: none; }}
        </style></head>
        <body>
        <h2>Top 10 Stocks Sorted by BP and Turnover Rate</h2>
        <table>
            <tr>
                <th>Ticker</th>
                <th>Close Price</th>
                <th>Market Cap ($B)</th>
                <th>Volume(M)</th>
                <th>Turnover Rate (%)</th>
                <th>RSI(6)</th>
                <th>BP</th>
            </tr>'''
        
        for _, row in top_10_turnover.iterrows():
            html_turnover += f'''
            <tr>
                <td><a href="https://www.tianshen.store/stock/{row['ticker']}" class="stock-link">{row['ticker']}</a></td>
                <td>{row['close_price']:.2f}</td>
                <td>{row['market_cap']:.2f}</td>
                <td>{row['volume']/1000000:.2f}M</td>
                <td>{row['turnover_rate']:.2f}</td>
                <td>{row['rsi_6']:.2f}</td>
                <td>{row['BP']:.2f}</td>
            </tr>'''
        
        html_turnover += '</table></body></html>'
        
        # Create and save second table (BP and RSI6)
        html_rsi = f'''
        <html><head><style>
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .stock-link {{ color: #0066cc; text-decoration: none; }}
        </style></head>
        <body>
        <h2>Top 10 Stocks Sorted by BP and MCap</h2>
        <table>
            <tr>
                <th>Ticker</th>
                <th>Close Price</th>
                <th>Market Cap ($B)</th>
                <th>Volume(M)</th>
                <th>Turnover Rate (%)</th>
                <th>RSI(6)</th>
                <th>BP</th>
            </tr>'''
        
        for _, row in top_10_rsi.iterrows():
            html_rsi += f'''
            <tr>
                <td><a href="https://www.tianshen.store/stock/{row['ticker']}" class="stock-link">{row['ticker']}</a></td>
                <td>{row['close_price']:.2f}</td>
                <td>{row['market_cap']:.2f}</td>
                <td>{row['volume']/1000000:.2f}M</td>
                <td>{row['turnover_rate']:.2f}</td>
                <td>{row['rsi_6']:.2f}</td>
                <td>{row['BP']:.2f}</td>
            </tr>'''
        
        html_rsi += '</table></body></html>'
        
        # Save both HTML tables
        with open('./static/daily_email_buypoint_turnover.txt', 'w') as f:
            f.write(html_turnover)
        with open('./static/daily_email_buypoint_mcap.txt', 'w') as f:
            f.write(html_rsi)
        
        # Print first table (BP and Turnover Rate)
        print("\nTop 10 Stocks Sorted by BP and Turnover Rate:")
        print("-" * 70)
        print(f"{'Ticker':<8} {'Close':<8} {'MCap($B)':<10} {'Volume(M)':<12} {'Turnover%':<10} {'RSI(6)':<8} {'BP':<6}")
        print("-" * 70)
        for _, row in top_10_turnover.iterrows():
            print(f"{row['ticker']:<8} {row['close_price']:<8.2f} {row['market_cap']:<10.2f} "
                  f"{row['volume']/1000000:<12.2f} {row['turnover_rate']:<10.2f} "
                  f"{row['rsi_6']:<8.2f} {row['BP']:<6.2f}")
        print("-" * 70)
        
        # Print second table (BP and MCap)
        print("\nTop 10 Stocks Sorted by BP and MCap:")
        print("-" * 70)
        print(f"{'Ticker':<8} {'Close':<8} {'MCap($B)':<10} {'Volume(M)':<12} {'Turnover%':<10} {'RSI(6)':<8} {'BP':<6}")
        print("-" * 70)
        for _, row in top_10_rsi.iterrows():
            print(f"{row['ticker']:<8} {row['close_price']:<8.2f} {row['market_cap']:<10.2f} "
                  f"{row['volume']/1000000:<12.2f} {row['turnover_rate']:<10.2f} "
                  f"{row['rsi_6']:<8.2f} {row['BP']:<6.2f}")
        print("-" * 70)
        
        # Get and print ticker lists
        turnover_tickers = top_10_turnover['ticker'].tolist()
        rsi_tickers = top_10_rsi['ticker'].tolist()
        
        print("\nTickers sorted by BP and Turnover Rate:")
        print('[' + '\n'.join(f"'{ticker}'," if i < len(turnover_tickers)-1 else f"'{ticker}'" 
                             for i, ticker in enumerate(turnover_tickers)) + ']')
        
        print("\nTickers sorted by BP and RSI(6):")
        print('[' + '\n'.join(f"'{ticker}'," if i < len(rsi_tickers)-1 else f"'{ticker}'" 
                             for i, ticker in enumerate(rsi_tickers)) + ']')
        
        # Return both lists of tickers
        return turnover_tickers, rsi_tickers
        
    except Exception as e:
        print(f"Error in analyze_stocks: {str(e)}")
        return [], []  # Return empty lists in case of error

def analyze_and_plot_stocks(today, future_days=0):
    # Define the number of future days to plot after today
    #future_days = 0  # Adjust as needed
    realtoday = datetime.today()
    today_date = datetime.strptime(today, '%Y%m%d')

    time_delta = (realtoday-today_date).days
    future_days = time_delta
    os.makedirs(f"./static/images/{today}", exist_ok=True)


    screener = pd.read_csv("./nasdaq_screener.csv")
    tickers = screener['Symbol']
    print(f"Loaded {len(tickers)} tickers from CSV file")

    total_stocks = len(tickers)
    tot_filtered = 0
    sel_idx=0
    # Create an empty DataFrame before the loop
    stock_data = pd.DataFrame(columns=['ticker', 
                                       'close_price',
                                       'market_cap', 
                                       'volume',
                                       'turnover_rate',
                                       'rsi_6',
                                       'BP'])
    for idx, stockticker in enumerate(tickers, start=1):
        #if idx<415:
        #    continue
        print(f'{idx}/{len(tickers)}       \r',end='')
        note = ''
        stock = yf.Ticker(stockticker)
        data = stock.history(period="6mo")
        if len(data)==0: continue

        # Get the info dictionary, which sometimes contains the 'country' key
        market_cap = 0
        try:
            info = stock.info
            market_cap = info.get('marketCap')
            country = info.get("country", "Country information not available")
            if country=='China':continue
        except:
            pass

        try:
            data.index = data.index.tz_localize(None)
        except:
            continue
        # Filter data to only include up to `today`
        if future_days ==0 :
            data_for_check = data.copy()
        else:
            data_for_check = data[data.index < today_date].copy()
        try:
            today_close_price = data_for_check['Close'].iloc[-1]
        except:
            continue


        # Calculate EMAs and MACD
        for window in range(3, 26, 2):
            data_for_check[f'EMA_{window}'] = ema(data_for_check['Close'], window)
        for window in range(27, 52, 2):
            data_for_check[f'EMA_{window}'] = ema(data_for_check['Close'], window)
        data_for_check['MACD'], data_for_check['MACD_signal'], data_for_check['MACD_hist'] = calculate_macd(data_for_check['Close'])

        # Calculate EMAs and MACD
        for window in range(3, 26, 2):
            data[f'EMA_{window}'] = ema(data['Close'], window)
        for window in range(27, 52, 2):
            data[f'EMA_{window}'] = ema(data['Close'], window)
        data['MACD'], data['MACD_signal'], data['MACD_hist'] = calculate_macd(data['Close'])
        
        # Calculate the daily percentage change
        data['Pct_Change'] = data['Close'].pct_change() * 100  # Convert to percentage

        # Count the days with a decrease in the close price
        decrease_days = (data['Pct_Change'] <= 0).sum()

        # Calculate the total number of trading days
        total_days = data['Pct_Change'].count()  # Ignore NaN from pct_change()

        # Calculate the percentage of decrease days
        decrease_percentage = (decrease_days / total_days) * 100
        if decrease_percentage > 70: continue

        # Proceed with your conditions and analysis logic here as before
        # Calculate crossover days
        last_crossover_idx, crossover_sign = calculate_crossover_days(data_for_check['MACD_hist'].values)
        if last_crossover_idx is not None:
            crossover_days = len(data_for_check) - last_crossover_idx
        else:
            crossover_days = 'N/A'

        try:
            MACD_hist_slope = (data_for_check['MACD_hist'].values[-1] - data_for_check['MACD_hist'].values[-3])/2
        except:
            continue
        # Skip if not meeting criteria
        if (crossover_sign != '-' or crossover_days == 'N/A' or
            data_for_check['MACD_hist'].values[-3:][0] > 0 or 
            data_for_check['MACD_hist'].values[-3:][-1] > 0 or
            not all(np.diff(data_for_check['MACD_hist'].values[-3:]) > 0)):
            continue

        # Check EMA conditions
        current_day_idx = -1
        green_ema = data_for_check['EMA_3'].values[current_day_idx]
        all_other_ema_values = [data_for_check[f'EMA_{window}'].values[current_day_idx] for window in range(5, 51, 2)]

        if all(green_ema < ema_value for ema_value in all_other_ema_values):
            note = 'GreenLow'
            continue
        ema_3_last_3 = data_for_check['EMA_3'].values[-3:]
        if ema_3_last_3[-1] < ema_3_last_3[-2]:
            continue
        #if MACD_hist_slope <0.02:continue
        if MACD_hist_slope <0.15:continue
        if crossover_days>22:continue

        add_technical_indicators(data)
        meantrend = (data['RSI_6']+100-data['WR_6']+data['kdj_k'])/3
        x_range = np.arange(len(data))
        # Mask NaN values in 'WR_6' to get valid data points
        meanWR = (data['WR_6']+data['WR_10'])/2
        valid_mask = ~np.isnan(meanWR)
        x_valid = x_range[valid_mask]           # Filtered x-values without NaNs
        y_valid = meanWR[valid_mask]      # Filtered WR_6 values without NaNs
        hist_valid = data['MACD_hist'][valid_mask]
        buy_points,sell_points = find_buy_sell_points(x_valid,y_valid,hist_valid)
        buy_points7,sell_points7 = find_buy_sell_points7(x_valid,meantrend[valid_mask],hist_valid)
        nearest_buy = x_valid[-1]-buy_points[-1]
        nearest_buy7 = x_valid[-1]-buy_points7[-1]
        nearest_sell = x_valid[-1]-sell_points[-1]
        nearest_sell7 = x_valid[-1]-sell_points7[-1]
        min_buy = min(nearest_buy,nearest_buy7)
        min_sell = min(nearest_sell,nearest_sell7)

        if min_buy >4: continue
        sel_idx+=1
        tot_filtered += 1
        try:
            market_cap = get_market_cap(stockticker)
            if market_cap is None:
                market_cap = 0  # or handle the error case as needed
            print(f'|{sel_idx:>4}/{total_stocks}|{stockticker:<5}|f:{tot_filtered:<2}|{market_cap/1000000000:<3.1f}B|BP:{min_buy}')
            # Inside your main filtering loop, update the stock_data DataFrame creation:
            stock_data.loc[len(stock_data)] = {
                'ticker': stockticker,
                'close_price': today_close_price,
                'market_cap': market_cap/1000000000,  # Converting to billions
                'volume': data['Volume'].iloc[-1],
                'turnover_rate': get_latest_turnover_rate(stockticker)['turnover_rate'],
                'rsi_6': data['RSI_6'].iloc[-1],
                'BP': min_buy
            }
        except:
            pass
    
    analyze_stocks(stock_data)


def filter_stock(deploy_mode, manual_date=None):
    edt = pytz.timezone('America/New_York')
    if deploy_mode == 1:  # auto deploy mode
        today = datetime.now(edt).strftime('%Y%m%d')
        print('today (auto mode):', today)
    elif deploy_mode == 2:  # manual deploy mode
        if manual_date is None:
            raise ValueError("Manual deploy mode (2) requires a date parameter in YYYYMMDD format")
        today = manual_date
        print('today (manual mode):', today)
    else:  # develop mode (0)
        #today = '20241129'
        today = datetime.now(edt).strftime('%Y%m%d')
        print('today (develop mode):', today)
    
    # Run first function
    analyze_and_plot_stocks(today, future_days=0)
    


if __name__ == "__main__":
    if len(sys.argv) > 1:
        mode = int(sys.argv[1])
        if mode == 2:
            if len(sys.argv) != 3:
                print("Error: Manual mode requires a date parameter in YYYYMMDD format")
                print("Usage: script.py 2 YYYYMMDD")
                sys.exit(1)
            manual_date = sys.argv[2]
            # Basic date format validation
            if not (len(manual_date) == 8 and manual_date.isdigit()):
                print("Error: Date must be in YYYYMMDD format")
                sys.exit(1)
            filter_stock(2, manual_date)
        elif mode == 1:
            filter_stock(1)
        elif mode == 0:
            filter_stock(0)
        else:
            print("Error: Invalid mode. Use 0 (develop), 1 (auto deploy), or 2 (manual deploy)")
            sys.exit(1)
    else:
        filter_stock(0)