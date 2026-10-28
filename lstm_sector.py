import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

# ✅ Sector Dictionary (same as your project)
sectors = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"]
}

# ✅ Function to prepare data
def prepare_data(series, time_step=60):
    X, y = [], []
    for i in range(len(series) - time_step):
        X.append(series[i:i+time_step])
        y.append(series[i+time_step])
    return np.array(X), np.array(y)

# ✅ Loop through sectors
for sector, stocks in sectors.items():
    print(f"\nProcessing {sector} sector...")

    for stock in stocks:
        filename = f"data/{sector}_{stock}.csv"

        if not os.path.exists(filename):
            print(f"Skipping {stock} (file not found)")
            continue

        df = pd.read_csv(filename)

        if 'Close' not in df.columns:
            print(f"Skipping {stock} (no Close column)")
            continue

        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df = df.dropna(subset=['Close'])

        if len(df) < 100:
            print(f"Skipping {stock} (not enough data)")
            continue

        # ✅ Scaling
        scaler = MinMaxScaler(feature_range=(0,1))
        scaled_data = scaler.fit_transform(df[['Close']])

        # ✅ Prepare dataset
        time_step = 60
        X, y = prepare_data(scaled_data, time_step)

        # Reshape for LSTM
        X = X.reshape(X.shape[0], X.shape[1], 1)

        # ✅ Split
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        # ✅ Build Model
        model = Sequential()
        model.add(LSTM(50, return_sequences=True, input_shape=(time_step, 1)))
        model.add(LSTM(50))
        model.add(Dense(1))

        model.compile(optimizer='adam', loss='mean_squared_error')

        # ✅ Train
        print(f"Training {stock}...")
        model.fit(X_train, y_train, epochs=5, batch_size=32, verbose=0)

        # ✅ Predict
        predictions = model.predict(X_test)

        # Convert back to original scale
        predictions = scaler.inverse_transform(predictions)
        y_test_actual = scaler.inverse_transform(y_test.reshape(-1,1))

        # ✅ Plot
        plt.figure(figsize=(8,4))
        plt.plot(y_test_actual, label="Actual")
        plt.plot(predictions, label="Predicted")
        plt.title(f"{stock} Prediction")
        plt.legend()
        plt.show()

        # ✅ Future Prediction (next 30 days)
        future_input = scaled_data[-time_step:]
        future_input = future_input.reshape(1, time_step, 1)

        future_predictions = []

        for _ in range(30):
            pred = model.predict(future_input)
            future_predictions.append(pred[0][0])

            future_input = np.append(
               future_input[:, 1:, :],
               pred.reshape(1, 1, 1),
               axis=1
)

        future_predictions = scaler.inverse_transform(
            np.array(future_predictions).reshape(-1,1)
        )

        # Plot future
        plt.figure(figsize=(8,4))
        plt.plot(future_predictions, label="Future 30 Days")
        plt.title(f"{stock} Future Prediction")
        plt.legend()
        image_path = "static/sector.png"
        plt.savefig(image_path)
        plt.close()

print("\nAll sectors processed successfully!")