import yfinance as yf_cloud

# Example usage
def get_latest_turnover_rate(ticker_symbol):
    """
    Get only the latest turnover rate for a stock
    
    Parameters:
    ticker_symbol (str): Stock ticker symbol
    
    Returns:
    float: Latest turnover rate
    dict: Additional information including volume and share count used
    """
    try:
        # Get stock data
        stock = yf_cloud.Ticker(ticker_symbol)
        
        # Get latest day's data
        today_data = stock.history(period='5d')
        if today_data.empty:
            raise ValueError("No data available for today")
            
        # Get latest volume
        latest_volume = today_data['Volume'].iloc[-1]
        
        # Try to get float shares first, fall back to shares outstanding
        float_shares = stock.info.get('floatShares')
        shares_outstanding = stock.info.get('sharesOutstanding')
        
        # Use float shares if available, otherwise use shares outstanding
        share_count = float_shares if float_shares else shares_outstanding
        share_type = "Float Shares" if float_shares else "Shares Outstanding"
        
        if not share_count:
            raise ValueError(f"Could not get share count for {ticker_symbol}")
            
        # Calculate turnover rate
        turnover_rate = (latest_volume / share_count) * 100
        
        # Return both the rate and additional info
        return {
            'turnover_rate': round(turnover_rate, 2),
            'volume': latest_volume,
            'share_count': share_count,
            'share_type': share_type,
            'date': today_data.index[-1].strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        print(f"Error getting latest turnover rate: {str(e)}")
        return None

if __name__ == "__main__":
    # Calculate daily turnover rates for Apple stock
    ticker = "GTI"
    

    # Get latest turnover rate
    latest = get_latest_turnover_rate(ticker)
    if latest is not None:
        print("\nLatest Turnover Rate:")
        print(f"Date: {latest['date']}")
        print(f"Turnover Rate: {latest['turnover_rate']}%")
        print(f"Volume: {latest['volume']:,}")
        print(f"Share Count ({latest['share_type']}): {latest['share_count']:,}")