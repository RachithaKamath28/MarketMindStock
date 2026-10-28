import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import sys
import json
import numpy as np

sectors = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"]
}

def analyze_sector(sector):
    if sector not in sectors:
        return {"error": "Invalid sector"}
    
    stocks = sectors[sector]
    plt.figure(figsize=(10,5))
    
    sector_data = {}
    performances = []
    volatilities = []
    
    for stock in stocks:
        filename = f"data/{sector}_{stock}.csv"
        
        if not os.path.exists(filename):
            continue
        
        df = pd.read_csv(filename)
        
        if 'Close' not in df.columns or 'Date' not in df.columns:
            continue
        
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df = df.dropna(subset=['Date', 'Close'])
        df = df.sort_values('Date')
        
        if df.empty or len(df) < 2:
            continue
        
        # Normalize for fair comparison
        df['Normalized'] = df['Close'] / df['Close'].iloc[0]
        
        plt.plot(df['Normalized'].values, label=stock.replace('.NS', ''))
        
        # Calculate performance
        current_price = df['Close'].iloc[-1]
        initial_price = df['Close'].iloc[0]
        performance = ((current_price - initial_price) / initial_price) * 100
        performances.append(performance)
        
        # Calculate volatility (annualized)
        daily_returns = df['Close'].pct_change().dropna()
        volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 0 else 0
        volatilities.append(volatility)
        
        sector_data[stock.replace('.NS', '')] = {
            "performance": round(performance, 2),
            "current_price": round(current_price, 2),
            "volatility": round(volatility, 4)
        }
    
    plt.title(f"{sector} Sector Comparison")
    plt.xlabel("Time")
    plt.ylabel("Normalized Price")
    plt.legend()
    image_path = "static/analysis.png"
    plt.savefig(image_path)
    plt.close()
    
    avg_performance = np.mean(performances) if performances else 0
    avg_volatility = np.mean(volatilities) if volatilities else 0

    # Risk level based only on the selected sector's volatility data
    risk_level = "Low" if avg_volatility < 0.18 else "Medium" if avg_volatility < 0.32 else "High"
    ai_insight = f"{sector} sector is expected to {'grow' if avg_performance > 0 else 'decline'} by {abs(avg_performance):.1f}% based on current trends."

    return {
        "sector": sector,
        "stocks": sector_data,
        "avg_performance": round(avg_performance, 2),
        "avg_volatility": round(avg_volatility, 4),
        "risk_level": risk_level,
        "ai_insight": ai_insight,
        "chart": "/static/analysis.png"
    }

if __name__ == "__main__":
    sector = sys.argv[1] if len(sys.argv) > 1 else "IT"
    result = analyze_sector(sector)
    print(json.dumps(result))