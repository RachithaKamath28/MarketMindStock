"""
Multi-Stock Analysis Module
============================
Independent module powering the "Multi-Stock Analysis" sidebar feature.

This module is intentionally self-contained: it does not import from or modify
sector_analysis.py, sector_prediction.py, lstm_sector.py, or advanced_risk_analysis.py,
and it does not touch the CSV data files used by Sector Analysis. All data used here
is fetched live from Yahoo Finance via yfinance, per the feature requirements.

The 15-stock universe below is intentionally identical (same tickers, same
sector groupings) to the one defined in sector_analysis.py, sector_prediction.py,
lstm_sector.py, advanced_risk_analysis.py, and app.py, so that every module in
the application -- Dashboard, Sector Analysis, Risk Analysis, Portfolio
Optimization, Stock Prediction, and Multi-Stock Analysis -- reasons about the
exact same set of companies. Only this module fetches that data live via
yfinance rather than from the CSV files; the *set of stocks* is shared.

Public functions consumed by app.py:
    - get_stock_list_with_quotes()
    - build_comparison_payload(symbols, start_date, end_date, chart_type)
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Fixed 15-stock universe: 4 IT + 4 Banking + 3 Pharma + 4 FMCG (NSE tickers).
# This must stay in sync with the identical `sectors` dictionary defined in
# sector_analysis.py, sector_prediction.py, lstm_sector.py,
# advanced_risk_analysis.py, and app.py so the whole application refers to one
# consistent stock dataset.
# ---------------------------------------------------------------------------
MULTI_STOCK_UNIVERSE = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"],
}

# Weighted-evaluation configuration used to determine the "Best Performer" summary
# card. Weights are an engineering-configurable decision (not specified by product
# requirements) and are documented here so they can be tuned without touching the
# scoring logic itself. Weights must sum to 1.0.
SCORE_WEIGHTS = {
    "return": 0.45,       # higher total return over the selected period is better
    "risk": 0.30,          # lower annualized volatility is better
    "volume": 0.15,        # higher average traded volume (liquidity) is better
    "consistency": 0.10,   # higher return-to-volatility ratio is better
}

# Benchmark index used to compute Beta for every stock (NIFTY 50). Fetched live
# via yfinance, exactly like the individual stock histories, so Beta is derived
# from the same real, date-range-scoped data as every other metric.
BENCHMARK_SYMBOL = "^NSEI"

# Annualized risk-free rate assumption used for the Sharpe Ratio calculation.
# Approximated from prevailing Indian 10-year G-Sec yields. This is a documented
# engineering assumption, not a live-fetched figure, and is surfaced in the API
# response (see `risk_free_rate_used`) for transparency.
RISK_FREE_RATE_ANNUAL = 0.065

# How many trading days of forward price are projected for the "Predicted Price"
# figure. The projection is a simple linear trend fit (numpy.polyfit) over the
# selected date range's closing prices -- a transparent statistical estimate,
# not a black-box model -- and is always labeled as an estimate/recommendation
# in the payload rather than asserted as fact.
PREDICTION_HORIZON_DAYS = 10


def get_stock_universe():
    """Return the fixed 15-stock universe grouped by sector."""
    return MULTI_STOCK_UNIVERSE


def _symbol_to_sector(full_symbol):
    for sector, symbols in MULTI_STOCK_UNIVERSE.items():
        if full_symbol in symbols:
            return sector
    return None


def fetch_live_quote(full_symbol):
    """Fetch current price and day change (%) for a single symbol via yfinance."""
    try:
        ticker = yf.Ticker(full_symbol)
        hist = ticker.history(period="5d", interval="1d")
        if hist is None or hist.empty or "Close" not in hist.columns:
            return None
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            return None
        latest_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else latest_close
        change_pct = ((latest_close - prev_close) / prev_close) * 100 if prev_close else 0.0
        return {"price": round(latest_close, 2), "change_pct": round(change_pct, 2)}
    except Exception:
        return None


def get_stock_list_with_quotes():
    """Return the 15-stock universe enriched with live price/day-change for the
    stock-selection table (all 15 stocks are always listed; there is no
    search or sector filter)."""
    rows = []
    for sector, symbols in MULTI_STOCK_UNIVERSE.items():
        for full_symbol in symbols:
            quote = fetch_live_quote(full_symbol)
            rows.append({
                "symbol": full_symbol.replace(".NS", ""),
                "full_symbol": full_symbol,
                "sector": sector,
                "price": quote["price"] if quote else None,
                "change_pct": quote["change_pct"] if quote else None,
                "status": "ok" if quote else "unavailable",
            })
    return rows


def fetch_history(full_symbol, start_date=None, end_date=None):
    """Fetch daily OHLCV history for a symbol from Yahoo Finance for a date range.

    NOTE: yfinance/yf.download treats `end` as EXCLUSIVE -- a request with
    end="2026-01-15" will NOT include the 2026-01-15 trading day itself. Left
    as-is, this silently drops the user-selected "To" date's own close price
    and shifts every date-range-scoped figure (Price, Day Change %, Return,
    CAGR, Volatility, Beta, ...) back by one trading day. To keep the fetched
    window aligned with what the user actually selected, we request one extra
    day past `end_date` and then clamp the result back down to `end_date`
    (inclusive) below, so the last row in the returned frame is always the
    closing price for the selected "To" date, or -- if that date is a
    weekend/holiday/future date with no trading -- the nearest prior trading
    day. This does not change the *start* of the range or any other behavior.
    """
    try:
        end = end_date or datetime.today().strftime("%Y-%m-%d")
        start = start_date or (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d")

        end_inclusive = pd.to_datetime(end)
        end_exclusive_for_fetch = (end_inclusive + timedelta(days=1)).strftime("%Y-%m-%d")

        df = yf.download(full_symbol, start=start, end=end_exclusive_for_fetch,
                          progress=False, auto_adjust=False)
        if df is None or df.empty:
            return None

        # Newer yfinance versions return MultiIndex columns even for a single ticker
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        if "Date" not in df.columns:
            return None
        df["Date"] = pd.to_datetime(df["Date"])

        required_cols = {"Open", "High", "Low", "Close", "Volume"}
        if not required_cols.issubset(set(df.columns)):
            return None

        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        df = df.dropna(subset=["Close"]).sort_values("Date")

        # Defensive clamp: guarantee no row beyond the selected "To" date ever
        # leaks in (e.g. due to timezone edge cases in the +1-day widened
        # fetch above). The last remaining row is therefore always the
        # selected "To" date's own close, or the nearest earlier trading day.
        df = df[df["Date"] <= end_inclusive]

        if df.empty:
            return None
        return df
    except Exception:
        return None


def fetch_benchmark_returns(start_date=None, end_date=None):
    """Fetch the NIFTY 50 benchmark history for the same date range used for the
    stock comparison and return its daily pct-change return series (used for
    Beta). Returns an empty Series (not None) on failure so callers can safely
    skip Beta rather than crash the whole comparison."""
    df = fetch_history(BENCHMARK_SYMBOL, start_date, end_date)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    returns = df.set_index("Date")["Close"].pct_change().dropna()
    return returns


def compute_beta(stock_returns, benchmark_returns):
    """Beta = Cov(stock, benchmark) / Var(benchmark), aligned by date. Returns
    None when there isn't enough overlapping data to compute a meaningful value."""
    if stock_returns is None or benchmark_returns is None:
        return None
    if stock_returns.empty or benchmark_returns.empty:
        return None

    aligned = pd.concat([stock_returns, benchmark_returns], axis=1, join="inner").dropna()
    if len(aligned) < 5:
        return None

    stock_col, bench_col = aligned.iloc[:, 0], aligned.iloc[:, 1]
    variance = bench_col.var()
    if variance == 0 or np.isnan(variance):
        return None

    covariance = stock_col.cov(bench_col)
    return round(float(covariance / variance), 3)


def compute_sharpe_ratio(returns, risk_free_annual=RISK_FREE_RATE_ANNUAL):
    """Sharpe Ratio = (annualized mean return - risk-free rate) / annualized
    volatility, computed from the same daily return series used for volatility
    elsewhere in this module (consistent methodology across all metrics)."""
    if returns is None or returns.empty:
        return None

    annualized_return = returns.mean() * 252
    annualized_vol = returns.std() * np.sqrt(252)
    if annualized_vol == 0 or np.isnan(annualized_vol):
        return None

    sharpe = (annualized_return - risk_free_annual) / annualized_vol
    return round(float(sharpe), 3)


def compute_cagr(df):
    """Compound Annual Growth Rate (%) over the exact selected date range,
    representing the annualized 'growth' of the stock across the period."""
    if df is None or df.empty or len(df) < 2:
        return None

    start_price = float(df["Close"].iloc[0])
    end_price = float(df["Close"].iloc[-1])
    days = (df["Date"].iloc[-1] - df["Date"].iloc[0]).days
    if start_price <= 0 or days <= 0:
        return None

    years = days / 365.0
    cagr = ((end_price / start_price) ** (1 / years) - 1) * 100
    return round(float(cagr), 2)


def predict_next_price(df, horizon_days=PREDICTION_HORIZON_DAYS):
    """Lightweight, transparent trend projection: fits a linear regression
    (numpy.polyfit, degree 1) over the selected date range's closing prices and
    extrapolates `horizon_days` of trading days forward. This is a statistical
    estimate derived directly from the real fetched history -- surfaced to the
    user as a recommendation/estimate, not a guaranteed forecast."""
    if df is None or df.empty or len(df) < 5:
        return None

    closes = df["Close"].values.astype(float)
    x = np.arange(len(closes))

    try:
        slope, intercept = np.polyfit(x, closes, 1)
    except Exception:
        return None

    future_x = len(closes) - 1 + horizon_days
    predicted_price = float(slope * future_x + intercept)
    if predicted_price <= 0:
        return None

    last_close = float(closes[-1])
    predicted_change_pct = ((predicted_price - last_close) / last_close) * 100 if last_close else 0.0

    return {
        "predicted_price": round(predicted_price, 2),
        "predicted_change_pct": round(predicted_change_pct, 2),
        "horizon_days": horizon_days,
    }


def compute_day_change(df):
    """Day Change (%) for the "Price" column: the % change between the
    closing price on the selected "To" date (or the nearest earlier trading
    day, if "To" falls on a weekend/holiday/future date) and the previous
    trading day *within the filtered date-range dataset only* -- no data is
    fetched outside the user-selected range for this calculation. Returns
    None (rendered as "--" by the frontend) when the filtered range contains
    only a single trading day, since there is no in-range prior close to
    compare against."""
    if df is None or df.empty or len(df) < 2:
        return None

    closes = df["Close"]
    latest_close = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2])
    if prev_close == 0:
        return None
    return round(((latest_close - prev_close) / prev_close) * 100, 2)


def compute_metrics(df, benchmark_returns=None):
    """Compute return %, annualized volatility %, average volume, risk
    category, Beta, Sharpe Ratio, CAGR (growth), day-over-day change and a
    trend-based predicted price for a single stock's OHLCV history."""
    if df is None or df.empty or len(df) < 2:
        return None

    closes = df["Close"]
    returns = closes.pct_change().dropna()
    if returns.empty:
        return None

    total_return_pct = ((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]) * 100
    volatility_pct = returns.std() * np.sqrt(252) * 100
    avg_volume = float(df["Volume"].mean()) if "Volume" in df.columns else 0.0

    if volatility_pct < 20:
        risk_category = "Low"
    elif volatility_pct < 35:
        risk_category = "Medium"
    else:
        risk_category = "High"

    sharpe_like = (total_return_pct / volatility_pct) if volatility_pct > 0 else 0.0

    dated_returns = pd.Series(returns.values, index=df["Date"].iloc[1:].values)
    beta = compute_beta(dated_returns, benchmark_returns)
    sharpe_ratio = compute_sharpe_ratio(returns)
    cagr_pct = compute_cagr(df)
    prediction = predict_next_price(df)
    day_change_pct = compute_day_change(df)

    return {
        "return_pct": round(float(total_return_pct), 2),
        "volatility_pct": round(float(volatility_pct), 2),
        "avg_volume": round(avg_volume, 0),
        "risk_category": risk_category,
        "sharpe_like": round(float(sharpe_like), 3),
        # "latest_close" (the "Price" column) is closes.iloc[-1] of the
        # date-range-filtered df -- i.e. the close on the selected "To" date,
        # or the nearest earlier trading day. See fetch_history() for the
        # inclusive-end-date fix that makes this accurate.
        "latest_close": round(float(closes.iloc[-1]), 2),
        "day_change_pct": day_change_pct,
        "beta": beta,
        "sharpe_ratio": sharpe_ratio,
        "growth_pct": cagr_pct,
        "prediction": prediction,
    }


def _normalize(values, higher_is_better=True):
    """Min-max normalize a list of values to the 0-1 range. Returns 0.5 for every
    entry when there is no spread (avoids divide-by-zero and ties in a fair way)."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5 for _ in values]
    if higher_is_better:
        return [(v - lo) / (hi - lo) for v in values]
    return [(hi - v) / (hi - lo) for v in values]


def compute_weighted_scores(stock_entries):
    """Assign a weighted performance score (0-100) to each stock entry based on
    SCORE_WEIGHTS, normalized across the current selection. Mutates and returns
    the input list with a 'score' key added to each entry."""
    if not stock_entries:
        return stock_entries

    returns = [e["metrics"]["return_pct"] for e in stock_entries]
    vols = [e["metrics"]["volatility_pct"] for e in stock_entries]
    volumes = [e["metrics"]["avg_volume"] for e in stock_entries]
    sharpe = [e["metrics"]["sharpe_like"] for e in stock_entries]

    norm_return = _normalize(returns, higher_is_better=True)
    norm_risk = _normalize(vols, higher_is_better=False)
    norm_volume = _normalize(volumes, higher_is_better=True)
    norm_consistency = _normalize(sharpe, higher_is_better=True)

    for i, entry in enumerate(stock_entries):
        score = (
            norm_return[i] * SCORE_WEIGHTS["return"]
            + norm_risk[i] * SCORE_WEIGHTS["risk"]
            + norm_volume[i] * SCORE_WEIGHTS["volume"]
            + norm_consistency[i] * SCORE_WEIGHTS["consistency"]
        ) * 100
        entry["score"] = round(score, 2)

    return stock_entries


def assign_badges(stock_entries):
    """Assign performance badges within the current selection: Best Return,
    Lowest Risk, Highest Volume, Most Consistent. Ties are broken by first
    occurrence (stable max/min)."""
    if not stock_entries:
        return stock_entries

    for entry in stock_entries:
        entry["badges"] = []

    max(stock_entries, key=lambda e: e["metrics"]["return_pct"])["badges"].append("Best Return")
    min(stock_entries, key=lambda e: e["metrics"]["volatility_pct"])["badges"].append("Lowest Risk")
    max(stock_entries, key=lambda e: e["metrics"]["avg_volume"])["badges"].append("Highest Volume")
    if len(stock_entries) > 1:
        max(stock_entries, key=lambda e: e["metrics"]["sharpe_like"])["badges"].append("Most Consistent")

    return stock_entries


def build_comparison_payload(symbols, start_date=None, end_date=None, chart_type="line"):
    """Core orchestration for the Multi-Stock Analysis compare endpoint: fetches
    live history for each requested symbol, computes metrics/scores/badges, and
    shapes chart-ready + table-ready data for the frontend."""
    if not symbols:
        return {"error": "No stocks selected"}

    chart_type = chart_type if chart_type in ("line", "bar", "candlestick") else "line"
    stock_entries = []
    unavailable = []

    # Fetched once per request (not per stock) and reused for every stock's Beta
    # calculation -- same date range, same source, consistent with the rest of
    # the module's "real backend data" approach.
    benchmark_returns = fetch_benchmark_returns(start_date, end_date)

    for full_symbol in symbols:
        sector = _symbol_to_sector(full_symbol)
        df = fetch_history(full_symbol, start_date, end_date)
        metrics = compute_metrics(df, benchmark_returns)

        if df is None or metrics is None:
            unavailable.append(full_symbol.replace(".NS", ""))
            continue

        series = {
            "dates": df["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "open": [round(float(v), 2) for v in df["Open"].tolist()],
            "high": [round(float(v), 2) for v in df["High"].tolist()],
            "low": [round(float(v), 2) for v in df["Low"].tolist()],
            "close": [round(float(v), 2) for v in df["Close"].tolist()],
            "volume": [float(v) for v in df["Volume"].tolist()],
        }

        stock_entries.append({
            "symbol": full_symbol.replace(".NS", ""),
            "full_symbol": full_symbol,
            "sector": sector,
            "metrics": metrics,
            "series": series,
        })

    if not stock_entries:
        return {"error": "No data available for the selected stocks/date range", "unavailable": unavailable}

    stock_entries = compute_weighted_scores(stock_entries)
    stock_entries = assign_badges(stock_entries)
    best_performer = max(stock_entries, key=lambda e: e["score"])

    comparison_table = [
        {
            "symbol": e["symbol"],
            "sector": e["sector"],
            "latest_close": e["metrics"]["latest_close"],
            "day_change_pct": e["metrics"]["day_change_pct"],
            "return_pct": e["metrics"]["return_pct"],
            "volatility_pct": e["metrics"]["volatility_pct"],
            "risk_category": e["metrics"]["risk_category"],
            "avg_volume": e["metrics"]["avg_volume"],
            "beta": e["metrics"]["beta"],
            "sharpe_ratio": e["metrics"]["sharpe_ratio"],
            "growth_pct": e["metrics"]["growth_pct"],
            "prediction": e["metrics"]["prediction"],
            "score": e["score"],
            "badges": e["badges"],
        }
        for e in stock_entries
    ]

    charts = [
        {
            "symbol": e["symbol"],
            "sector": e["sector"],
            "dates": e["series"]["dates"],
            "open": e["series"]["open"],
            "high": e["series"]["high"],
            "low": e["series"]["low"],
            "close": e["series"]["close"],
            "volume": e["series"]["volume"],
        }
        for e in stock_entries
    ]

    explanation = _build_best_performer_explanation(best_performer, stock_entries)

    return {
        "chart_type": chart_type,
        "charts": charts,
        "comparison_table": comparison_table,
        "summary": {
            "best_performer": best_performer["symbol"],
            "sector": best_performer["sector"],
            "score": best_performer["score"],
            "return_pct": best_performer["metrics"]["return_pct"],
            "volatility_pct": best_performer["metrics"]["volatility_pct"],
            "risk_category": best_performer["metrics"]["risk_category"],
            "beta": best_performer["metrics"]["beta"],
            "sharpe_ratio": best_performer["metrics"]["sharpe_ratio"],
            "growth_pct": best_performer["metrics"]["growth_pct"],
            "prediction": best_performer["metrics"]["prediction"],
            "badges": best_performer["badges"],
            "explanation": explanation,
            "weights_used": SCORE_WEIGHTS,
            "risk_free_rate_used": RISK_FREE_RATE_ANNUAL,
        },
        "unavailable": unavailable,
    }


def _build_best_performer_explanation(best_performer, stock_entries):
    """Compose a short, data-grounded explanation of why a stock was flagged as
    the best performer, using only figures actually computed for it (and, where
    useful, a same-selection comparison). Entirely generated from the numbers
    already in `best_performer['metrics']` -- no hardcoded per-stock text."""
    m = best_performer["metrics"]
    symbol = best_performer["symbol"]

    others = [e for e in stock_entries if e["symbol"] != symbol]
    avg_return_others = (
        round(sum(o["metrics"]["return_pct"] for o in others) / len(others), 2) if others else None
    )
    avg_vol_others = (
        round(sum(o["metrics"]["volatility_pct"] for o in others) / len(others), 2) if others else None
    )

    parts = [
        f"{symbol} posted a {m['return_pct']:+.2f}% return over the selected period"
    ]

    if avg_return_others is not None:
        parts[-1] += f" (vs. an average of {avg_return_others:+.2f}% for the other selected stocks)"
    parts[-1] += f", with {m['risk_category'].lower()} risk ({m['volatility_pct']:.2f}% annualized volatility)"

    if avg_vol_others is not None:
        comparator = "lower than" if m["volatility_pct"] < avg_vol_others else "higher than"
        parts[-1] += f", which is {comparator} the {avg_vol_others:.2f}% average for the rest of the selection"
    parts[-1] += "."

    if m.get("growth_pct") is not None:
        parts.append(f"Its annualized growth (CAGR) over this window was {m['growth_pct']:+.2f}%.")

    if m.get("sharpe_ratio") is not None:
        parts.append(
            f"A Sharpe Ratio of {m['sharpe_ratio']:.2f} indicates its return "
            f"{'adequately compensates' if m['sharpe_ratio'] > 0 else 'has not compensated'} "
            f"for the risk taken, relative to a {RISK_FREE_RATE_ANNUAL*100:.1f}% risk-free benchmark."
        )

    if m.get("beta") is not None:
        if 0.9 <= m["beta"] <= 1.1:
            beta_desc = "moves roughly in line with"
        elif m["beta"] > 1.1:
            beta_desc = "amplifies moves relative to"
        else:
            beta_desc = "dampens moves relative to"
        parts.append(f"With a Beta of {m['beta']:.2f}, it {beta_desc} the broader NIFTY 50 market.")

    parts.append(
        f"Combined, these factors produced the highest weighted score ({best_performer['score']:.1f}/100) "
        "in this comparison -- weighing return, risk, liquidity and consistency together, not return alone."
    )

    return " ".join(parts)
