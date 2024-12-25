import yfinance as yf
import pandas as pd

def get_stock_chips(ticker_symbol):
    """
    Get LCHIP, PCHIP, and FCHIP percentages for a given stock
    """
    try:
        # Get stock info
        stock = yf.Ticker(ticker_symbol)
        
        # Get the stock info dictionary
        info = stock.info
        
        # Get ownership percentages
        insider_percent = info.get('heldPercentInsiders', 0) * 100 if info.get('heldPercentInsiders') is not None else 0
        institution_percent = info.get('heldPercentInstitutions', 0) * 100 if info.get('heldPercentInstitutions') is not None else 0
        
        # Calculate CHIPS
        PCHIP = insider_percent  # Promoter holdings
        LCHIP = institution_percent  # Locked-in holdings
        FCHIP = max(0, 100 - PCHIP - LCHIP)  # Free float
        
        return {
            'PCHIP': round(PCHIP, 2),
            'LCHIP': round(LCHIP, 2),
            'FCHIP': round(FCHIP, 2),
            'Details': {
                'Insider Ownership': f"{round(insider_percent, 2)}%",
                'Institutional Ownership': f"{round(institution_percent, 2)}%",
                'Free Float': f"{round(FCHIP, 2)}%"
            }
        }
        
    except Exception as e:
        print(f"Error getting data for {ticker_symbol}: {str(e)}")
        return None

def print_chips_analysis(ticker_symbol):
    """
    Print a formatted analysis of stock chips
    """
    results = get_stock_chips(ticker_symbol)
    if results:
        print(f"\nChips Analysis for {ticker_symbol.upper()}")
        print("-" * 40)
        print(f"PCHIP (Promoter Holdings): {results['PCHIP']}%")
        print(f"LCHIP (Locked-in Holdings): {results['LCHIP']}%")
        print(f"FCHIP (Free Float): {results['FCHIP']}%")
        print("\nDetailed Breakdown:")
        for key, value in results['Details'].items():
            print(f"{key}: {value}")
    else:
        print(f"Could not retrieve data for {ticker_symbol}")

# Example usage
if __name__ == "__main__":
    # Example with multiple stocks
    tickers = ["AAPL", "MSFT", "GOOGL"]
    for ticker in tickers:
        print_chips_analysis(ticker)