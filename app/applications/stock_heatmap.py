import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from concurrent.futures import ThreadPoolExecutor

def get_sp500_symbols():
    """
    Get S&P 500 symbols and their sectors using Wikipedia
    """
    try:
        # Read S&P 500 table from Wikipedia
        tables = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        
        df = tables[0]
        print('df',df)
        # Create dictionary of symbol to sector mapping
        return dict(zip(df['Symbol'], df['GICS Sector']))
    except Exception as e:
        print(f"Error fetching S&P 500 data: {e}")
        return {}

def get_stock_info(ticker):
    """
    Fetch individual stock data
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period='1d')
        
        if not hist.empty:
            return {
                'symbol': ticker,
                'market_cap': info.get('marketCap', 0),
                'price': hist['Close'].iloc[-1],
                'pct_change': ((hist['Close'].iloc[-1] - hist['Open'].iloc[0]) / 
                             hist['Open'].iloc[0] * 100)
            }
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
    return None

def get_top_100_stocks():
    """
    Get data for top 100 stocks by market cap
    """
    # Get S&P 500 symbols and their sectors
    sector_mapping = get_sp500_symbols()
    
    # Fetch data for all stocks in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(get_stock_info, sector_mapping.keys()))
    
    # Filter out None results and sort by market cap
    results = [r for r in results if r is not None]
    results = sorted(results, key=lambda x: x['market_cap'], reverse=True)[:100]
    
    # Add sector information
    for stock in results:
        stock['sector'] = sector_mapping.get(stock['symbol'], 'Other')
    
    return results

def create_market_heatmap(stock_data):
    """
    Create a treemap visualization for the top 100 stocks
    """
    # Organize data by sector
    sector_data = {}
    for stock in stock_data:
        sector = stock['sector']
        if sector not in sector_data:
            sector_data[sector] = []
        sector_data[sector].append(stock)
    
    # Prepare data for treemap
    labels = []
    parents = []
    values = []
    colors = []
    hovertexts = []
    
    for sector, stocks in sector_data.items():
        # Add sector
        sector_market_cap = sum(stock['market_cap'] for stock in stocks)
        labels.append(sector)
        parents.append("")
        values.append(sector_market_cap)
        colors.append(0)
        hovertexts.append(f"{sector}<br>Total Market Cap: ${sector_market_cap/1e9:.1f}B")
        
        # Add stocks
        for stock in stocks:
            labels.append(stock['symbol'])
            parents.append(sector)
            values.append(stock['market_cap'])
            colors.append(stock['pct_change'])
            hovertexts.append(
                f"{stock['symbol']}<br>" +
                f"Market Cap: ${stock['market_cap']/1e9:.1f}B<br>" +
                f"Price: ${stock['price']:.2f}<br>" +
                f"Change: {stock['pct_change']:.2f}%"
            )

    # Create color scale
    colorscale = [
        [0, 'rgb(165,0,38)'],      # Dark red for negative
        [0.5, 'rgb(255,255,255)'], # White for neutral
        [1, 'rgb(0,104,55)']       # Dark green for positive
    ]

    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        customdata=np.round(colors, 2),
        text=[f"{label}<br>{value:,.2f}%" if parent != "" else "" 
              for label, parent, value in zip(labels, parents, colors)],
        hovertext=hovertexts,
        hoverinfo="text",
        marker=dict(
            colors=colors,
            colorscale=colorscale,
            cmid=0,
            showscale=True,
            colorbar=dict(
                title="% Change",
                thickness=20,
                len=0.7
            )
        ),
        textposition="middle center",
        pathbar=dict(visible=False)
    ))

    fig.update_layout(
        title={
            'text': "Top 100 Stocks by Market Cap",
            'y':0.95,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        width=1600,
        height=900,
        margin=dict(t=50, l=10, r=10, b=10)
    )
    
    return fig

def main():
    print("Fetching top 100 stocks data...")
    stock_data = get_top_100_stocks()
    
    print("Creating visualization...")
    fig = create_market_heatmap(stock_data)
    
    print("Displaying heatmap...")
    fig.show()

if __name__ == "__main__":
    main()