import os,sys
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Set the backend to non-interactive 'Agg'
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from scipy.optimize import curve_fit
import pytz
# Set timezone to EDT
import warnings
import sqlite3
# Ignore all warnings
warnings.filterwarnings("ignore")
# add edt
edt = pytz.timezone("America/New_York")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf
#import yfinance as yf


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


from datetime import datetime, timedelta

def get_business_days_difference(date1, date2):
    """
    Calculate the number of business days between two dates, excluding weekends.
    
    Parameters:
    date1 (datetime): First date
    date2 (datetime): Second date
    
    Returns:
    int: Number of business days between the dates
    """
    if date1 > date2:
        date1, date2 = date2, date1
    
    # Calculate number of complete weeks and remaining days
    days = (date2 - date1).days
    business_days = (days // 7) * 5
    
    # Handle remaining days
    remaining_days = days % 7
    
    # Get starting weekday (0 = Monday, 6 = Sunday)
    start_weekday = date1.weekday()
    
    for i in range(remaining_days + 1):
        if (start_weekday + i) % 7 < 5:  # If it's a weekday
            business_days += 1
    
    # Subtract 1 to not count the start date if it's a business day
    if start_weekday < 5:
        business_days -= 1
        
    return business_days

# Example usage for your case:
def calculate_future_business_days(real_today_str, today_str):
    """
    Calculate business days between real today and a specified date
    
    Parameters:
    real_today_str (str): Current date string in 'YYYYMMDD' format
    today_str (str): Target date string in 'YYYYMMDD' format
    
    Returns:
    int: Number of business days between the dates
    """
    realtoday = datetime.strptime(real_today_str, '%Y%m%d')
    today_date = datetime.strptime(today_str, '%Y%m%d')
    
    return get_business_days_difference(today_date, realtoday)



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

# Function to fit a line and estimate days to positive
def fit_line_and_predict(macd_hist_values):
    x = np.array([1, 2, 3])
    y = macd_hist_values[-3:]
    p = np.polyfit(x, y, 1)
    days_to_positive = -p[1] / p[0]
    return p, days_to_positive

# Modified plot_candlestick function to use continuous trading day indices
def plot_candlestick(ax, data):
    for idx in range(len(data)):
        open_price = data['Open'].iloc[idx]
        close_price = data['Close'].iloc[idx]
        high_price = data['High'].iloc[idx]
        low_price = data['Low'].iloc[idx]
        
        is_green = close_price >= open_price
        color = 'green' if is_green else 'red'
        
        # Plot the high-low line (wick)
        ax.plot([idx, idx], [low_price, high_price], 
                color=color,
                linewidth=2,
                zorder=1)
        
        # Create the candlestick body
        rect = plt.Rectangle((idx - 0.3, min(open_price, close_price)),
                           0.6,
                           abs(close_price - open_price),
                           facecolor='white' if is_green else 'red',  # White fill for green candles
                           edgecolor=color,  # Green border for green candles
                           linewidth=1 if is_green else 0,  # Add border for green candles
                           alpha=1.0,
                           zorder=2)
        ax.add_patch(rect)

# Function to create custom date formatter for x-axis
def format_date(x, p, trading_dates):
    if x >= 0 and x < len(trading_dates):
        return trading_dates[int(x)].strftime('%Y-%m-%d')
    return ''

# Function to fit line for EMA and calculate slope and error
def fit_ema_line(data, start_idx, end_idx):
    y = data['EMA_3'].iloc[start_idx:end_idx + 1].values
    x = np.arange(len(y))
    p = np.polyfit(x, y, 1)
    slope, intercept = p
    fit_values = np.polyval(p, x)
    mse = np.mean((y - fit_values) ** 2)
    return slope, mse, fit_values


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

def update_png(today,filename,mode): #mode=0 means daily, 1 means only one file
    #future_days = 0  # Adjust as needed
    realtoday = datetime.today()
    today_date = datetime.strptime(today, '%Y%m%d')
    realtodaystr = realtoday.strftime('%Y%m%d')

    #future_days = (realtoday-today_date).days
    future_days = calculate_future_business_days(realtodaystr, today)
    if mode==0:
        os.makedirs(f"./static/images/{today}/", exist_ok=True)

    stockticker = filename[:-4].split('_')[1]

    stock = yf.Ticker(stockticker)
    data = stock.history(period="6mo")

    wkdata = stock.history(period="2y",interval="1wk")
    if wkdata.empty:
        wkdata = stock.history(period="max",interval="1wk")

    # Get the info dictionary, which sometimes contains the 'country' key
    market_cap = 0
    try:
        info = stock.info
        market_cap = info.get('marketCap')
    except:
        market_cap = 0
    if market_cap is None: market_cap=0

    try:
        data.index = data.index.tz_localize(None)
    except:
        pass
    # Filter data to only include up to `today`
    if future_days ==0 :
        data_for_check = data.copy()
    else:
        data_for_check = data[data.index < today_date].copy()

    # Store trading dates for x-axis formatting
    trading_dates = data.index.tolist()
    # Append future dates for plotting
    future_dates = pd.date_range(start=trading_dates[-1], periods=2 + 1)[1:]
    extended_dates = trading_dates + list(future_dates)

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

    # Proceed with your conditions and analysis logic here as before
    # Calculate crossover days
    last_crossover_idx, crossover_sign = calculate_crossover_days(data_for_check['MACD_hist'].values)
    if last_crossover_idx is not None:
        crossover_days = len(data_for_check) - last_crossover_idx
    else:
        crossover_days = 'N/A'

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
    print(stockticker,'BP:',min_buy,'SP:',min_sell)

    market_cap = get_market_cap(stockticker)

    # Create the main figure
    fig = plt.figure(figsize=(19, 10))
    # Top group with shared x-axis (ax1, ax2, ax3)
    gs_top = fig.add_gridspec(3, 1, 
        height_ratios=[2, 0.5, 0.5], 
        hspace=0.00,            # Vertical space between subplots in top group
        bottom=0.45,            # Bottom position of the top group
        top=0.95,               # Top position (added to reduce top margin)
        left=0.05,               # Left margin
        right=0.95              # Right margin
        )
    ax1 = fig.add_subplot(gs_top[0])
    ax2 = fig.add_subplot(gs_top[1], sharex=ax1)
    ax3 = fig.add_subplot(gs_top[2], sharex=ax1)

    # Bottom group with separate shared x-axis (ax4, ax5)
    gs_bottom = fig.add_gridspec(2, 1, 
        height_ratios=[2, 1], 
        hspace=0.00,         # Vertical space between subplots in bottom group
        bottom=0.05,          # Bottom position of the bottom group
        top=0.42,             # Top position of the bottom group
        left=0.05,            # Left margin
        right=0.95           # Right margin
        )
    ax4 = fig.add_subplot(gs_bottom[0])
    ax5 = fig.add_subplot(gs_bottom[1], sharex=ax4)

    # Optionally, hide x-axis labels for upper plots in each group
    ax1.tick_params(labelbottom=False)
    ax2.tick_params(labelbottom=False)
    ax4.tick_params(labelbottom=False)

    # Plot candlestick data
    plot_candlestick(ax1, data)
    # Plot EMAs
    for window in range(3, 26, 2):
        ax1.plot(range(len(data)), data[f'EMA_{window}'], 
                label=f'EMA_{window}', 
                alpha=0.5 if window != 3 else 1,
                linewidth=2 if window == 3 else 1, color='green',zorder=1)
    for window in range(27, 52, 2):
        ax1.plot(range(len(data)), data[f'EMA_{window}'], 
                label=f'EMA_{window}', 
                alpha=0.5 if window != 3 else 1,
                linewidth=2 if window == 3 else 1, color='red',zorder=1)


    # MACD and Fitted Line Plot
    x_range = range(len(data))
    ax2.plot(x_range, data['MACD'], label='MACD', color='blue')
    ax2.plot(x_range, data['MACD_signal'], label='Signal', color='orange')

    # Plot MACD Histogram with Color Conditions
    color_condition = np.where(data['Close'].diff() > 0, 'green', 'red')
    ax2.bar(x_range, data['MACD_hist'], color=color_condition)
    ax2.axhline(0, color='black', linewidth=1, linestyle='-')
    
    ax1.axvline(x=len(data) - 0.5- future_days, linestyle='-', color='blue', label='Today')
    ax2.axvline(x=len(data) - 0.5- future_days, linestyle='-', color='blue', label='Today')
    ax3.axvline(x=len(data) - 0.5- future_days, linestyle='-', color='blue', label='Today')

    # Extend x-axis with future dates and set custom format
    ax2.set_xlim([0, len(extended_dates) - 1])
    ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format_date(x, p, trading_dates)))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=0, ha='right')

    # Show tick markers every `n_ticks` intervals
    n_ticks = 10
    tick_locations = np.linspace(0, len(data)-1 -future_days, n_ticks, dtype=int)
    ax2.set_xticks(tick_locations)
    ax2.set_xticklabels([extended_dates[i].strftime('%Y-%m-%d') for i in tick_locations], rotation=0, ha='right')


    # New subplot for RSI, WR, and Volume
    #ax3 = fig.add_subplot(3, 1, 3)  # Create a new subplot below ax2

    # Plot mean
    ax3.plot(x_range, 100-meantrend, label='RSI 6', color='blue', linestyle='-',linewidth=0.8,marker='.',markersize=3)
    #ax3.plot(x_range, 100-data['WR_6'], label='WR 6', color='purple', linestyle='-', linewidth=0.8,marker='.',markersize=3)
    #ax3.plot(x_range, data['kdj_k'], label='kdj k', color='red', linestyle='-', linewidth=0.8,marker='.',markersize=3)
    ax3_right = ax3.twinx() 
    #ax3_right.plot(x_range, data['Close'], label='RSI 6', color='orange', linestyle='-',linewidth=0.8,marker='.',markersize=3)

    #ax3.plot(x_range, data['RSI_12'], label='RSI 12', color='orange', linestyle='-',linewidth=0.8,marker='.',markersize=3)
    #ax3.plot(x_range, data['RSI_24'], label='RSI 24', color='green', linestyle='-', linewidth=0.8,marker='.',markersize=3)


    # Plot Volume
    #ax6 = ax1.twinx()  # Create a twin y-axis for volume
    ax3_right.bar(x_range, data['Volume'], alpha=0.3, color=color_condition, label='Volume', width=0.75)

    # Formatting ax3
    ax3.axhline(30, color='red', linestyle='--', linewidth=0.8)  # Overbought level for RSI
    ax3.axhline(70, color='red', linestyle='--', linewidth=0.8)  # Overbought level for RSI
    ax3.axhline(50, color='green', linestyle='--', linewidth=0.8)  # Oversold level for RSI
    ax3.set_ylabel('WR', color='black')
    ax1.set_ylabel('Daily', color='black')
    ax2.set_ylabel('MACD', color='black')
    ax5.set_ylabel('MACD', color='black')
    ax4.set_ylabel('Weekly', color='black')


    # Set minor grid for additional lines every two data points
    for ax in [ax1,ax2, ax3, ax4, ax5]:
        ax.grid(True, alpha=1)
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(2))  # Set minor grid every 2 data points
        ax.grid(True, which='minor', alpha=0.5)  # Enable minor grid with desired transparency

    
    for bp in buy_points:
        ax1.axvline(x=bp, color='green', linestyle='--', label='Buy Point' if 'Buy Point' not in plt.gca().get_legend_handles_labels()[1] else "")
        ax2.axvline(x=bp, color='green', linestyle='--', label='Buy Point' if 'Buy Point' not in plt.gca().get_legend_handles_labels()[1] else "")
        #ax3.axvline(x=bp, color='green', linestyle='--', label='Buy Point' if 'Buy Point' not in plt.gca().get_legend_handles_labels()[1] else "")
        #ax4.axvline(x=bp, color='green', linestyle='--', label='Buy Point' if 'Buy Point' not in plt.gca().get_legend_handles_labels()[1] else "")
    for sp in sell_points:
        ax1.axvline(x=sp, color='red', linestyle='--', label='Sell Point' if 'Sell Point' not in plt.gca().get_legend_handles_labels()[1] else "")
        ax2.axvline(x=sp, color='red', linestyle='--', label='Sell Point' if 'Sell Point' not in plt.gca().get_legend_handles_labels()[1] else "")
        #ax3.axvline(x=sp, color='red', linestyle='--', label='Sell Point' if 'Sell Point' not in plt.gca().get_legend_handles_labels()[1] else "")
        #ax4.axvline(x=sp, color='red', linestyle='--', label='Sell Point' if 'Sell Point' not in plt.gca().get_legend_handles_labels()[1] else "")
    for bp in buy_points7:
        ax3.axvline(x=bp, color='green', linestyle='-', label='Buy Point' if 'Buy Point' not in plt.gca().get_legend_handles_labels()[1] else "")
    for sp in sell_points7:
        ax3.axvline(x=sp, color='red', linestyle='-', label='Sell Point' if 'Sell Point' not in plt.gca().get_legend_handles_labels()[1] else "")

    #for wkdata:
    wkdata['MACD'], wkdata['MACD_signal'], wkdata['MACD_hist'] = calculate_macd(wkdata['Close'])
    plot_candlestick(ax4, wkdata)
    
    # MACD and Fitted Line Plot
    wk_x_range = range(len(wkdata))
    ax4.set_xlim([-1, len(wk_x_range)])

    ax5.plot(wk_x_range, wkdata['MACD'], label='MACD', color='blue')
    ax5.plot(wk_x_range, wkdata['MACD_signal'], label='Signal', color='orange')
    wk_color_condition = np.where(wkdata['Close'].diff() > 0, 'green', 'red')
    ax5.bar(wk_x_range, wkdata['MACD_hist'], color=wk_color_condition)
    ax5.axhline(0, color='black', linewidth=1, linestyle='-')

    # Save plot
    ax1.set_title(f'{filename}|{market_cap:.1f}B|')
    plt.tight_layout()
    if mode ==0:
        plt.savefig(f'./static/images/{today}/{filename}')
    else:
        plt.savefig(f'./static/images/generated_view.png')
    plt.close()
def process_stock_tickers(tickers):
    """
    Process a list of stock tickers and generate candlestick charts for each one.
    
    Args:
        tickers (list): List of stock ticker symbols
    """
    # Get today's date in YYYYMMDD format
    today = datetime.now().strftime('%Y%m%d')
    
    # Create the base directory if it doesn't exist
    base_dir = f'./static/images/{today}'
    os.makedirs(base_dir, exist_ok=True)
    
    # Process each ticker
    for ticker in tickers:
        try:
            # Create filename in required format
            filename = f'candle_{ticker}.png'
            
            # Call update_png function with daily mode (mode=0)
            update_png(today, filename, 0)
            
            print(f"Successfully processed {ticker}")
            
        except Exception as e:
            print(f"Error processing {ticker}: {str(e)}")
            continue

if __name__ == "__main__":
    # Example stock ticker list - replace with your desired tickers
    tickerlist = ['GILD',     
        'PAYX',
        'WTW',
        'J',
        'JBL',
        'CYTK',
        'RYTM',
        'PRAX',
        'CRGX',
        'DOCS']
    
    # Process all tickers
    process_stock_tickers(tickerlist)