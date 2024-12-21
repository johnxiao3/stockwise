import sqlite3
from collections import defaultdict
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os,sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import yfiance_local as yf

# Function to calculate EMA
def ema(data, window):
    return data.ewm(span=window, adjust=False).mean()

def stock_9classes(stockticker,plot): 
    today_date = datetime.today()
    #today_date_str = datetime.strptime(today_date, '%Y%m%d')

    stock = yf.Ticker(stockticker)
    data = stock.history(period="6mo")

    # Calculate EMAs
    selections = [5,13,21,34,55,89,144,233]
    try:
        for window in selections:
            data[f'EMA_{window}'] = ema(data['Close'], window)
    except:
        return 0


    last_close = data['Close'].iloc[-1]
    ema_values = [data[f'EMA_{window}'].iloc[-1] for window in selections]
    all_values = [last_close] + ema_values
    sorted_values = sorted(set(all_values))  # Using set to handle any potential duplicate values
    class_value = sorted_values.index(last_close) + 1
    

    
    #------plot below------
    if plot == 1:
        fig = plt.figure(figsize=(10, 10))
        # Top group with shared x-axis (ax1, ax2, ax3)
        gs_top = fig.add_gridspec(1, 1, 
            hspace=0.00,            # Vertical space between subplots in top group
            left=0.05,               # Left margin
            right=0.95              # Right margin
            )
        ax1 = fig.add_subplot(gs_top[0])

        # Plot closing price in black with higher zorder to appear on top
        ax1.plot(range(len(data)), data['Close'], 
                label='Close Price',
                color='black',
                linewidth=2,
                zorder=2)  # Higher zorder makes it appear on top

        for window in selections:
            ax1.plot(range(len(data)), data[f'EMA_{window}'], 
                    label=f'EMA_{window}', 
                    alpha=0.5 if window != 3 else 1,
                    linewidth=2 if window == 3 else 1, color='green',zorder=1)

        ax1.set_title(f'{stockticker} class: {class_value}')
        plt.savefig(f'./static/test')
    return class_value


def get_stocks_by_industry():
    # Connect to the SQLite database
    conn = sqlite3.connect('./static/stock_data.db')
    cursor = conn.cursor()
    
    try:
        # Query to get all symbols and industries
        cursor.execute("SELECT Symbol, Industry FROM nasdaq_screener WHERE Industry IS NOT NULL")
        results = cursor.fetchall()
        
        # Group stocks by industry using defaultdict
        industry_stocks = defaultdict(list)
        for symbol, industry in results:
            industry_stocks[industry].append(symbol)
        
        # Calculate totals
        total_industries = len(industry_stocks)
        total_stocks = sum(len(stocks) for stocks in industry_stocks.values())
        industry_averages = []
        # Print stocks grouped by industry with counts and percentages
        for i, (industry, symbols) in enumerate(sorted(industry_stocks.items()), 1):
            #if i>=5:break
            stock_count = len(symbols)
            industry_percent = (stock_count / total_stocks) * 100
            
            #print(f"\nIndustry {i}/{total_industries}: {industry}")
            #print(f"Stocks: {stock_count} ({industry_percent:.2f}% of total stocks)")
            #print("Symbols:", ", ".join(sorted(symbols)))
            stocksname = "Symbols:", " | ".join(sorted(symbols))
            classes = []
            for symbol in symbols:
                class_value = stock_9classes(symbol,plot=0)
                if class_value != 0 :
                    classes.append(class_value)
                #print(f'{symbol}:{class_value}')
            avg_class = np.mean(classes)
            print(f'{industry}:{avg_class:0.1f}')

            # Store the results
            industry_averages.append({
                'Industry': industry,
                'Average_Class': round(avg_class, 1),
                'Stock_Count': stock_count,
                'Percent_of_Total': round(industry_percent, 2),
                'Stocks':stocksname
            })
            #break
        # Create DataFrame and save to CSV
        df = pd.DataFrame(industry_averages)
        df = df.sort_values('Average_Class', ascending=False)  # Sort by average class
        df.to_csv('./static/section9class.csv', index=False)
        
        print(f"\nResults saved to ./static/section9class.csv")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        conn.close()
    


if __name__ == "__main__":
    class_value = stock_9classes("TSLA",plot=1)

    #get_stocks_by_industry()