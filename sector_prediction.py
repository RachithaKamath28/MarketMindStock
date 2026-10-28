import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# ✅ Sector Dictionary
sectors = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"]
}

def prepare_data(series, time_step=60):
    X, y = [], []
    for i in range(len(series) - time_step):
        X.append(series[i:i+time_step])
        y.append(series[i+time_step])
    return np.array(X), np.array(y)

# 🔁 Loop sectors
for sector, stocks in sectors.items():
    print(f"\nProcessing {sector} sector...")

    combined = pd.DataFrame()

    # ✅ Combine all stocks in sector
    for stock in stocks:
        filename = f"data/{sector}_{stock}.csv"

        if not os.path.exists(filename):
            continue

        df = pd.read_csv(filename)

        if 'Close' not in df.columns:
            continue

        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df = df.dropna(subset=['Close'])

        # Normalize
        df['Normalized'] = df['Close'] / df['Close'].iloc[0]

        combined[stock] = df['Normalized']

    if combined.empty:
        print(f"Skipping {sector} (no data)")
        continue

    # ✅ Sector average
    sector_series = combined.mean(axis=1).values.reshape(-1,1)

    # ✅ Scaling
    scaler = MinMaxScaler(feature_range=(0,1))
    scaled_data = scaler.fit_transform(sector_series)

    # ✅ Prepare data
    time_step = 60
    X, y = prepare_data(scaled_data, time_step)
    X = X.reshape(X.shape[0], X.shape[1], 1)

    # Split
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # ✅ Model
    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=(time_step, 1)))
    model.add(LSTM(50))
    model.add(Dense(1))

    model.compile(optimizer='adam', loss='mean_squared_error')

    print(f"Training {sector} model...")
    model.fit(X_train, y_train, epochs=5, batch_size=32, verbose=0)

    # ✅ Future Prediction
    future_input = scaled_data[-time_step:]
    future_input = future_input.reshape(1, time_step, 1)

    future_predictions = []

    for _ in range(30):
        pred = model.predict(future_input, verbose=0)

        future_predictions.append(pred[0][0])

        # FIXED SHAPE
        future_input = np.append(
            future_input[:,1:,:],
            pred.reshape(1,1,1),
            axis=1
        )

    future_predictions = scaler.inverse_transform(
        np.array(future_predictions).reshape(-1,1)
    )

    # ✅ Plot
    plt.figure(figsize=(8,4))
    plt.plot(future_predictions, label="Future Trend")
    plt.title(f"{sector} Sector Future Prediction")
    plt.xlabel("Next 30 Days")
    plt.ylabel("Growth")
    plt.legend()
    image_path = "static/prediction.png"
    plt.savefig(image_path)
    plt.close()

print("\nAll sector predictions completed!")