import pandas as pd


# Analysis functions
def calculate_macd(close_prices, slow=26, fast=12, signal=9):
    """Calculate MACD (Moving Average Convergence Divergence)"""
    close_prices = pd.Series(close_prices)
    ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
    ema_slow = close_prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = 2 * (macd_line - signal_line)
    return macd_line, signal_line, histogram
