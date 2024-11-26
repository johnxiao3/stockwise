import yfinance as yf

# Get EQNR stock data with weekly candles
ticker = yf.Ticker("EQNR")
df = ticker.history(period="1mo", interval="1wk")  # Get 1 month of weekly data

# Print the most recent weekly candle data
latest_week = df.iloc[-1]  # Get the last row (most recent week)
print(f"EQNR Weekly Candle Data for week ending {df.index[-1].date()}:")
print(f"Open:  ${latest_week['Open']:.2f}")
print(f"Close: ${latest_week['Close']:.2f}")
print(f"High:  ${latest_week['High']:.2f}")
print(f"Low:   ${latest_week['Low']:.2f}")

latest_week = df.iloc[-2]  # Get the last row (most recent week)
print(f"EQNR Weekly Candle Data for week ending {df.index[-1].date()}:")
print(f"Open:  ${latest_week['Open']:.2f}")
print(f"Close: ${latest_week['Close']:.2f}")
print(f"High:  ${latest_week['High']:.2f}")
print(f"Low:   ${latest_week['Low']:.2f}")

