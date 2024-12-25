import pandas as pd
import os,sys
import sqlite3
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf
#import yfinance as yf

def get_weekly_performance(ticker, num_weeks):
    """
    Get daily stock performance organized by weeks for a given ticker
    
    Parameters:
    ticker (str): Stock ticker symbol
    num_weeks (int): Number of past weeks to analyze
    
    Returns:
    pandas.DataFrame: Weekly performance table with days as columns
    """
    # Calculate start date
    end_date = datetime.now()
    start_date = end_date - timedelta(weeks=num_weeks + 1)  # Extra week to ensure we have full weeks
    
    # Download stock data
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date)
    
    # Calculate daily percentage changes
    df['daily_change'] = ((df['Close'] - df['Open']) / df['Open'] * 100).round(2)
    
    # Add date information
    df['Week'] = df.index.isocalendar().week
    df['Weekday'] = df.index.strftime('%A')
    
    # Create pivot table
    pivot_df = df.pivot(index='Week', columns='Weekday', values='daily_change')
    
    # Reorder columns to Monday-Friday
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    pivot_df = pivot_df[weekday_order]
    
    # Sort weeks in descending order and get last n weeks
    pivot_df = pivot_df.sort_index(ascending=False).head(num_weeks)
    
    # Rename index to show relative weeks
    week_labels = [f'Week -{i}' for i in range(num_weeks)]
    pivot_df.index = week_labels
    
    return pivot_df

def analyze_day_performance(weekly_performance_df, day_of_week):
    """
    Analyze the performance of a specific day across the weeks.
    
    Parameters:
    weekly_performance_df (pandas.DataFrame): Output from get_weekly_performance function
    day_of_week (str): Day to analyze ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')
    
    Returns:
    tuple: (number of positive days, average percentage change)
    """
    # Get the column for the specified day
    day_data = weekly_performance_df[day_of_week]
    
    # Count positive days (excluding NaN values)
    positive_days = (day_data > 0).sum()
    
    # Calculate average change (excluding NaN values)
    average_change = day_data.mean()
    
    return positive_days, round(average_change, 2)

def get_stock_symbols(db_path='./static/stock_data.db', table_name='nasdaq_screener'):
    """
    Retrieve all stock symbols from the specified database table.
    
    Parameters:
    db_path (str): Path to SQLite database
    table_name (str): Name of the table to query
    
    Returns:
    list: List of stock symbols
    """
    try:
        # Create SQLite connection
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query to get all symbols
        cursor.execute(f"SELECT Symbol FROM {table_name}")
        
        # Fetch all symbols and convert to list
        symbols = [row[0] for row in cursor.fetchall()]
        
        # Close connection
        conn.close()
        
        print(f"Successfully retrieved {len(symbols)} symbols")
        return symbols
        
    except Exception as e:
        print(f"Error retrieving symbols: {str(e)}")
        return []

def week_screen():
    stockids = get_stock_symbols()
    weeks = 10        # Last 4 weeks
    print(len(stockids))
    for ticker in stockids:
        try:
            weekly_data = get_weekly_performance(ticker, weeks)
        except:
            continue
        # Analyze a specific day (e.g., Monday)
        day_to_analyze = "Monday"
        pos_days, avg_change = analyze_day_performance(weekly_data, day_to_analyze)
        if pos_days >=8 and avg_change>1:
            print(f"{ticker}: + {day_to_analyze}s: {pos_days}, Avg Change: {avg_change}%")

def disp_one(ticker):
    weeks = 10        # Last 4 weeks
    #day_to_analyze = "Monday"
    weekly_data = get_weekly_performance(ticker, weeks)
    print(f"\nWeekly performance for {ticker} (values in %):")
    print(weekly_data)  

def print_list():
    list = ['SHCO',
            'SKYT',
            'HUMA',
            'PSNL',
            'TRIP',
            'QRVO',
            'JBL',
            'MITK',
            'NVRI',
            'EDR'
            ]
    
    list = ['GILD',
        'PAYX',
        'WTW',
        'J',
        'JBL',
        'CYTK',
        'RYTM',
        'PRAX',
        'CRGX']
    for ticker in list:
         disp_one(ticker)

def get_max_available_weeks(ticker):
    """
    Determine the maximum number of weeks available for analysis for a given ticker.
    
    Parameters:
    ticker (str): Stock ticker symbol
    
    Returns:
    int: Maximum number of available weeks
    """
    try:
        # Get all available data
        stock = yf.Ticker(ticker)
        df = stock.history(period="max")
        
        if df.empty:
            return 52  # Default if no data available
        
        # Calculate the date range
        start_date = df.index.min()
        end_date = df.index.max()
        
        # Calculate the number of weeks
        weeks = ((end_date - start_date).days // 7)
        return max(weeks, 2)  # Ensure at least 2 weeks
        
    except Exception as e:
        print(f"Error determining max weeks for {ticker}: {str(e)}")
        return 52  # Default to 52 weeks on error

def get_weekly_performance(ticker, num_weeks):
    """
    Get daily stock performance organized by weeks for a given ticker
    
    Parameters:
    ticker (str): Stock ticker symbol
    num_weeks (int): Number of past weeks to analyze
    
    Returns:
    pandas.DataFrame: Weekly performance table with days as columns
    """
    # Calculate start date
    end_date = datetime.now()
    start_date = end_date - timedelta(weeks=num_weeks + 1)  # Extra week to ensure we have full weeks
    
    # Download stock data
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date)
    
    if df.empty:
        raise ValueError(f"No data available for {ticker}")
    
    # Calculate daily percentage changes
    df['daily_change'] = ((df['Close'] - df['Open']) / df['Open'] * 100).round(2)
    
    # Create a unique week identifier using ISO year and week
    df['ISOYear'] = df.index.isocalendar().year
    df['ISOWeek'] = df.index.isocalendar().week
    df['YearWeek'] = df['ISOYear'].astype(str) + '-' + df['ISOWeek'].astype(str).str.zfill(2)
    df['Weekday'] = df.index.strftime('%A')
    
    # Sort by date in descending order
    df = df.sort_index(ascending=False)
    
    # Get unique YearWeeks, sorted in descending order
    unique_yearweeks = df['YearWeek'].unique()[:num_weeks]
    
    # Filter data for the requested number of weeks
    df = df[df['YearWeek'].isin(unique_yearweeks)]
    
    # Create pivot table using YearWeek as index
    pivot_df = df.pivot_table(index='YearWeek', 
                            columns='Weekday', 
                            values='daily_change',
                            aggfunc='first')  # Use first value if multiple exist
    
    # Reorder columns to Monday-Friday
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    pivot_df = pivot_df[weekday_order]
    
    # Sort by YearWeek in descending order
    pivot_df = pivot_df.sort_index(ascending=False)
    
    # Rename index to show relative weeks
    week_labels = [f'Week -{i}' for i in range(len(pivot_df))]
    pivot_df.index = week_labels
    
    return pivot_df

def analyze_weekly_averages(ticker):
    """
    Analyze average daily performance for different week ranges.
    
    Parameters:
    ticker (str): Stock ticker symbol
    
    Returns:
    dict: Dictionary containing average performance for each day across different week ranges
    """
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    results = {day: [] for day in weekday_order}
    week_numbers = []
    
    # Get maximum available weeks
    max_weeks = get_max_available_weeks(ticker)
    if max_weeks > 200:
        max_weeks = 200
    
    # Analyze from week 2 to max_weeks
    for num_weeks in range(2, max_weeks + 1):
        try:
            # Get weekly performance data using existing function
            weekly_data = get_weekly_performance(ticker, num_weeks)
            
            # Calculate averages for each day
            for day in weekday_order:
                avg_change = weekly_data[day].mean()
                results[day].append(round(avg_change, 2))
            
            week_numbers.append(num_weeks)
            
            # Print progress on single line
            print(f"\rProcessing {ticker}: {num_weeks}/{max_weeks} weeks", end="")
            
        except Exception as e:
            print(f"\nError processing {num_weeks} weeks: {str(e)}")
            break
    
    print()  # Add newline at the end
    return results, week_numbers

def plot_weekly_averages(ticker, results, week_numbers):
    """
    Plot average daily performance with maximized plot area and consistent margins.
    """
    import matplotlib.pyplot as plt
    from datetime import datetime
    import os
    
    # Create date folder structure
    today = datetime.now().strftime('%Y%m%d')
    base_path = './static/images'
    date_folder = os.path.join(base_path, today)
    
    # Create directories if they don't exist
    os.makedirs(date_folder, exist_ok=True)
    
    # Create figure with specific margins
    plt.figure(figsize=(12, 6))
    
    # Set margins (left, bottom, right, top) values between 0 and 1
    plt.subplots_adjust(left=0.06, right=0.98, top=0.95, bottom=0.1)
    
    # Define distinct styles for each day with hollow/non-solid markers
    styles = {
        'Monday': {'linestyle': '-', 'marker': '', 'fillstyle': 'none', 'color': 'blue'},
        'Tuesday': {'linestyle': '--', 'marker': 'x', 'fillstyle': 'none', 'color': 'red'},
        'Wednesday': {'linestyle': ':', 'marker': '', 'fillstyle': 'none', 'color': 'green'},
        'Thursday': {'linestyle': '-.', 'marker': '', 'fillstyle': 'none', 'color': 'purple'},
        'Friday': {'linestyle': '--', 'marker': '', 'fillstyle': 'none', 'color': 'orange'}
    }
    all_values = []
    for averages in results.values():
        all_values.extend(averages)
    y_min = min(all_values)
    y_max = max(all_values)
    # Plot line for each day
    for day, averages in results.items():
        plt.plot(week_numbers, averages,
                label=day,
                linestyle=styles[day]['linestyle'],
                marker=styles[day]['marker'],
                fillstyle=styles[day]['fillstyle'],
                markersize=1.5,
                linewidth=1,
                color=styles[day]['color'])
        # Set x-axis to start from 0
    plt.xlim(0, max(week_numbers))
    plt.ylim(y_min, y_max)
    plt.xlabel('Number of Weeks Analyzed')
    plt.ylabel('Average Daily Change (%)')
    plt.title(f'Average Daily Performance by Week Range - {ticker}')
    plt.legend(loc='upper right')
    plt.grid(True)
    
    # Save the plot in the date folder
    save_path = os.path.join(date_folder, f'weekly_avg_{ticker}.png')
    plt.savefig(save_path, bbox_inches=None)
    plt.close()

def analyze_and_plot_stock(ticker):
    """
    Analyze and plot stock performance for different week ranges.
    
    Parameters:
    ticker (str): Stock ticker symbol
    """
    print(f"\nAnalyzing {ticker}...")
    
    # Get the averages for different week ranges
    results, week_numbers = analyze_weekly_averages(ticker)
    
    # Plot the results if we have any data
    if week_numbers:
        plot_weekly_averages(ticker, results, week_numbers)
        print(f"\nAnalysis complete. Plot saved as './static/images/weekly_avg_{ticker}.png'")
    else:
        print(f"\nNo data available to plot for {ticker}")
        
def analyze_and_plot_stock_list(tickerlist):
    for ticker in tickerlist:
        analyze_and_plot_stock(ticker)
# Example usage
if __name__ == "__main__":
    analyze_and_plot_stock_list(tickerlist = ['GILD',     
        'PAYX',
        'WTW',
        'J',
        'JBL',
        'CYTK',
        'RYTM',
        'PRAX',
        'CRGX',
        'DOCS'])
    #analyze_and_plot_stock('DOCS') 
    #print_list()
    #disp_one('HUMA')
    #week_screen()