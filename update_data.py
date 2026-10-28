import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os

# ✅ Step 1: Setup
today = datetime.today().strftime('%Y-%m-%d')
print("Today's Date:", today)

os.makedirs("data", exist_ok=True)

# ✅ Step 2: Sector Dictionary
sectors = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"]
}

# ✅ Step 3: Download Fresh Data (NO UPDATE LOGIC)
for sector, stocks in sectors.items():
    print(f"\nDownloading {sector} sector...")

    for stock in stocks:
        filename = f"data/{sector}_{stock}.csv"

        try:
            data = yf.download(stock, start="2015-01-01", end=today)

            # Convert index to column
            data.reset_index(inplace=True)

            # Save clean data
            data.to_csv(filename, index=False)

            print(f"{stock} saved in {sector}")

        except Exception as e:
            print(f"Error with {stock}: {e}")

# ✅ Step 4: Load Data
sector_data = {}

for sector, stocks in sectors.items():
    sector_data[sector] = []

    for stock in stocks:
        filename = f"data/{sector}_{stock}.csv"

        try:
            df = pd.read_csv(filename)

            # Ensure Close column is numeric
            if 'Close' in df.columns:
                df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                df = df.dropna(subset=['Close'])   # ⭐ FIX

            sector_data[sector].append(df)

        except Exception as e:
            print(f"Error loading {stock}: {e}")

print("Data loaded successfully!")

# ✅ Step 5: Plot Sector
sector = "IT"

plt.figure(figsize=(10, 5))

for i, stock in enumerate(sectors[sector]):
    df = sector_data[sector][i]

    if df.empty:
        print(f"Skipping {stock} (Empty data)")
        continue

    plt.plot(df['Close'].values, label=stock)

plt.title(f"{sector} Sector Comparison")
plt.xlabel("Time")
plt.ylabel("Stock Price")
plt.legend()
plt.show()