import pandas as pd

# Read the CSV file
df = pd.read_csv('nasdaq_screener.csv')

colunm_name = 'Industry'

# Get unique values count from the 'Sector' column
unique_sectors = df[colunm_name].nunique()

# Print the count
print(f"Number of unique sectors: {unique_sectors}")

# To see what those unique sectors are:
print("\nUnique sectors:")
print(df[colunm_name].unique())