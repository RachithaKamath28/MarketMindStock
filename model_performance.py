"""
Model Performance & Accuracy Module
====================================
Independent, additive module powering the "Model Performance" sidebar feature.

Design intent (per project constraints): this module does NOT import from,
call, or modify app.py, sector_analysis.py, sector_prediction.py,
lstm_sector.py, advanced_risk_analysis.py, or multi_stock_analysis.py, and it
does not touch any existing route, template, or CSV write path. It only
*reads* the same CSV files already used by the Sector Analysis module, so it
stays perfectly in sync with the rest of the app without altering it.

What it does
------------
The dashboard's forecasting engine (the momentum/drift model that powers the
"Future Prediction" and "Stock Price Prediction" pages) is evaluated with a
walk-forward backtest: for every historical month in the evaluation window,
the model is given only the data available *before* that month, asked to
forecast that month's closing price, and then checked against what actually
happened. This mirrors how the production forecaster works, but replays it
against known history so genuine accuracy metrics can be computed -- nothing
here is simulated or invented after the fact.

Public functions consumed by app.py:
    - list_symbols_with_ranges()
    - evaluate_model_performance(symbol, start_date=None, end_date=None)
"""

import os
import numpy as np
import pandas as pd

def _month_end_rule():
    """Pandas renamed the month-end resampling alias from M to ME in 2.2."""
    try:
        version = tuple(int(part) for part in pd.__version__.split(".")[:2])
    except Exception:
        version = (2, 2)
    return "ME" if version >= (2, 2) else "M"

# ---------------------------------------------------------------------------
# Same fixed stock universe used across the application (kept in sync with
# app.py / multi_stock_analysis.py). Duplicated intentionally to keep this
# module fully independent -- see module docstring.
# ---------------------------------------------------------------------------
SECTORS = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"],
}

# Identical drift-blend weights and sideways band used by the production
# forecaster in app.py (build_stock_prediction), so the backtest evaluates
# the *actual* model logic rather than a stand-in.
DRIFT_WEIGHTS = {"recent": 0.5, "mid": 0.3, "long_term": 0.2}

# Minimum number of trailing monthly observations required before the model
# is allowed to produce its first backtested forecast (keeps early, noisy
# single-digit-sample forecasts out of the evaluation).
MIN_TRAIN_MONTHS = 6

# Composite Model Performance Score weighting. Documented and tunable here
# rather than hard-coded inline. Weights sum to 1.0.
SCORE_WEIGHTS = {
    "direction_accuracy": 0.40,   # did the model call up/down correctly
    "mape": 0.30,                  # how large the average percentage error was
    "r2": 0.30,                    # how well predictions track actual variance
}

SCORE_CATEGORIES = [
    (85, "Excellent"),
    (70, "Good"),
    (50, "Average"),
    (0, "Poor"),
]


def _data_path(sector, stock):
    return f"data/{sector}_{stock}.csv"


def _load_raw_dataframe(sector, stock):
    filename = _data_path(sector, stock)
    if not os.path.exists(filename):
        return None
    try:
        df = pd.read_csv(filename)
        if df.empty or "Close" not in df.columns or "Date" not in df.columns:
            return None
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
        if len(df) < 2:
            return None
        return df[["Date", "Close"]].reset_index(drop=True)
    except Exception:
        return None


def _find_symbol(symbol):
    """Resolve a bare symbol (e.g. 'TCS') to (sector, ticker-with-suffix)."""
    if not symbol:
        return None, None
    symbol = symbol.upper().strip()
    for sector, stocks in SECTORS.items():
        for stock in stocks:
            if stock.replace(".NS", "") == symbol:
                return sector, stock
    return None, None


def list_symbols_with_ranges():
    """Symbol universe grouped by sector, with each stock's available data
    date range, for populating the frontend selector."""
    result = {}
    for sector, stocks in SECTORS.items():
        entries = []
        for stock in stocks:
            df = _load_raw_dataframe(sector, stock)
            if df is None:
                continue
            entries.append({
                "symbol": stock.replace(".NS", ""),
                "sector": sector,
                "data_start": df["Date"].min().strftime("%Y-%m-%d"),
                "data_end": df["Date"].max().strftime("%Y-%m-%d"),
            })
        if entries:
            result[sector] = entries
    return result


def _monthly_series(df):
    monthly = df.set_index("Date").resample(_month_end_rule()).last().dropna(subset=["Close"])
    return monthly["Close"]


def _blended_drift(returns):
    """Reproduces the momentum-aware drift blend from app.py's
    build_stock_prediction, using only returns available at forecast time."""
    long_term_avg = float(returns.mean())
    recent_avg = float(returns.tail(min(3, len(returns))).mean())
    mid_avg = float(returns.tail(min(6, len(returns))).mean())
    return (
        recent_avg * DRIFT_WEIGHTS["recent"]
        + mid_avg * DRIFT_WEIGHTS["mid"]
        + long_term_avg * DRIFT_WEIGHTS["long_term"]
    )


def _one_step_forecast(train_series):
    """Given monthly closes up to (not including) the target month, produce
    the model's deterministic point forecast for the next month -- the same
    drift + moving-average-confirmation backbone the production forecaster
    uses for its trend/label classification."""
    returns = train_series.pct_change().dropna()
    if returns.empty:
        return None

    avg_monthly_return = _blended_drift(returns)

    ma_short = float(train_series.tail(min(3, len(train_series))).mean())
    ma_long = float(train_series.tail(min(6, len(train_series))).mean())
    if ma_long:
        signals_agree = (avg_monthly_return >= 0) == (ma_short >= ma_long)
        avg_monthly_return *= 1.15 if signals_agree else 0.65

    latest_price = float(train_series.iloc[-1])
    forecast = latest_price * float(np.exp(avg_monthly_return))
    return max(forecast, 0.0)


def _walk_forward_backtest(monthly_series, start_date=None, end_date=None):
    """Rolling one-month-ahead backtest. For every eligible month, train on
    everything strictly before it and forecast it, then compare to what the
    price actually did. Returns parallel lists: dates, actual, predicted,
    prev_actual (the anchor price the forecast was made from)."""
    dates, actual, predicted, prev_actual = [], [], [], []

    start_ts = pd.to_datetime(start_date) if start_date else None
    end_ts = pd.to_datetime(end_date) if end_date else None

    for i in range(MIN_TRAIN_MONTHS, len(monthly_series)):
        target_date = monthly_series.index[i]
        if start_ts is not None and target_date < start_ts:
            continue
        if end_ts is not None and target_date > end_ts:
            continue

        train_slice = monthly_series.iloc[:i]
        forecast = _one_step_forecast(train_slice)
        if forecast is None:
            continue

        dates.append(target_date.strftime("%Y-%m-%d"))
        actual.append(float(monthly_series.iloc[i]))
        predicted.append(float(round(forecast, 4)))
        prev_actual.append(float(train_slice.iloc[-1]))

    return dates, actual, predicted, prev_actual


def _regression_metrics(actual, predicted):
    a = np.array(actual, dtype=np.float64)
    p = np.array(predicted, dtype=np.float64)

    errors = a - p
    abs_errors = np.abs(errors)

    mae = float(np.mean(abs_errors))
    mse = float(np.mean(errors ** 2))
    rmse = float(np.sqrt(mse))

    nonzero_mask = a != 0
    mape = float(np.mean(abs_errors[nonzero_mask] / np.abs(a[nonzero_mask])) * 100) if nonzero_mask.any() else 0.0

    ss_res = float(np.sum(errors ** 2))
    ss_tot = float(np.sum((a - np.mean(a)) ** 2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0

    return {
        "mae": round(mae, 4),
        "mse": round(mse, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 2),
        "r2": round(r2, 4),
    }


def _direction_confusion_matrix(actual, predicted, prev_actual):
    """Positive class = 'Up'. Direction is measured relative to the last
    actually-known price the forecast was anchored to, so both the actual
    and predicted directions describe the same real starting point."""
    tp = fp = fn = tn = 0
    for a, p, prev in zip(actual, predicted, prev_actual):
        actual_up = a >= prev
        predicted_up = p >= prev
        if actual_up and predicted_up:
            tp += 1
        elif (not actual_up) and predicted_up:
            fp += 1
        elif actual_up and (not predicted_up):
            fn += 1
        else:
            tn += 1

    total = tp + fp + fn + tn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "total": total,
        "accuracy": round(accuracy * 100, 2),
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1": round(f1 * 100, 2),
    }


def _error_distribution(residuals, bin_count=8):
    if not residuals:
        return {"labels": [], "counts": []}
    r = np.array(residuals, dtype=np.float64)
    counts, edges = np.histogram(r, bins=min(bin_count, max(3, len(r))))
    labels = [f"{edges[i]:.1f} to {edges[i + 1]:.1f}" for i in range(len(edges) - 1)]
    return {"labels": labels, "counts": [int(c) for c in counts]}


def _performance_score(metrics, confusion):
    r2_component = max(0.0, min(1.0, metrics["r2"])) * 100
    mape_component = max(0.0, 100 - metrics["mape"])
    direction_component = confusion["accuracy"]

    score = (
        direction_component * SCORE_WEIGHTS["direction_accuracy"]
        + mape_component * SCORE_WEIGHTS["mape"]
        + r2_component * SCORE_WEIGHTS["r2"]
    )
    score = round(max(0.0, min(100.0, score)), 1)

    category = "Poor"
    for threshold, label in SCORE_CATEGORIES:
        if score >= threshold:
            category = label
            break

    return {
        "score": score,
        "category": category,
        "components": {
            "direction_accuracy_contribution": round(direction_component * SCORE_WEIGHTS["direction_accuracy"], 1),
            "mape_contribution": round(mape_component * SCORE_WEIGHTS["mape"], 1),
            "r2_contribution": round(r2_component * SCORE_WEIGHTS["r2"], 1),
        },
        "weights": SCORE_WEIGHTS,
    }


def _interpretation_text(symbol, metrics, confusion, score_info, n_points):
    category = score_info["category"]
    lead = {
        "Excellent": f"The model is performing excellently on {symbol} over this window.",
        "Good": f"The model is performing well on {symbol} over this window.",
        "Average": f"The model is performing adequately on {symbol}, with room to improve.",
        "Poor": f"The model is struggling to track {symbol} reliably over this window.",
    }[category]

    direction_sentence = (
        f"It correctly called the up/down direction {confusion['accuracy']:.1f}% of the time "
        f"across {n_points} tested months."
    )
    error_sentence = (
        f"On average, predicted closing prices were off by {metrics['mape']:.1f}% "
        f"(about ₹{metrics['mae']:.2f} per share, MAE)."
    )
    fit_sentence = (
        f"Its R² of {metrics['r2']:.2f} indicates "
        + ("a strong fit to actual price movement." if metrics["r2"] >= 0.6
           else "a moderate fit to actual price movement." if metrics["r2"] >= 0.3
           else "a weak fit -- treat point forecasts with caution.")
    )

    return " ".join([lead, direction_sentence, error_sentence, fit_sentence])


def evaluate_model_performance(symbol, start_date=None, end_date=None):
    sector, stock = _find_symbol(symbol)
    if not sector:
        return {"error": f"Stock '{symbol}' not found in the available universe."}

    df = _load_raw_dataframe(sector, stock)
    if df is None:
        return {"error": f"No data available for {symbol}."}

    monthly_series = _monthly_series(df)
    if len(monthly_series) < MIN_TRAIN_MONTHS + 3:
        return {"error": f"Not enough history for {symbol} to run a reliable backtest."}

    dates, actual, predicted, prev_actual = _walk_forward_backtest(monthly_series, start_date, end_date)

    if len(actual) < 3:
        return {
            "error": (
                "Not enough evaluation points in the selected date range. "
                "Try widening the date range."
            )
        }

    metrics = _regression_metrics(actual, predicted)
    residuals = [round(a - p, 4) for a, p in zip(actual, predicted)]
    confusion = _direction_confusion_matrix(actual, predicted, prev_actual)
    error_dist = _error_distribution(residuals)
    score_info = _performance_score(metrics, confusion)
    interpretation = _interpretation_text(symbol.upper(), metrics, confusion, score_info, len(actual))

    return {
        "symbol": symbol.upper(),
        "sector": sector,
        "start_date": start_date,
        "end_date": end_date,
        "evaluation_points": len(actual),
        "metrics": metrics,
        "actual_vs_predicted": {
            "dates": dates,
            "actual": [round(v, 2) for v in actual],
            "predicted": [round(v, 2) for v in predicted],
        },
        "residuals": {
            "dates": dates,
            "predicted": [round(v, 2) for v in predicted],
            "residual": residuals,
        },
        "error_distribution": error_dist,
        "confusion_matrix": confusion,
        "performance_score": score_info,
        "interpretation": interpretation,
    }
