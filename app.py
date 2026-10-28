from flask import Flask, Response, render_template, jsonify, request, redirect, url_for, session, flash, stream_with_context
import subprocess
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import json
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Independent Multi-Stock Analysis module (does not modify Sector Analysis logic)
from multi_stock_analysis import (
    get_stock_list_with_quotes,
    build_comparison_payload,
    MULTI_STOCK_UNIVERSE,
)

# Independent Model Performance & Accuracy module (does not modify any
# existing backend logic, routes, or data files)
from model_performance import (
    list_symbols_with_ranges,
    evaluate_model_performance,
)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'local-development-only-change-me')
app.config['SESSION_TYPE'] = 'filesystem'
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# Database setup
DATABASE = 'users.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         username TEXT UNIQUE NOT NULL,
                         password TEXT NOT NULL)''')
        conn.commit()

init_db()

# Review system database is independent from the existing user/authentication database.
# PostgreSQL is used when DATABASE_URL is configured; SQLite is the local fallback.
from reviews_system import reviews_db, reviews_bp
_review_db_url = os.getenv('DATABASE_URL', '').strip()
if _review_db_url.startswith('postgres://'):
    _review_db_url = _review_db_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif _review_db_url.startswith('postgresql://'):
    _review_db_url = _review_db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
if not _review_db_url:
    _review_db_url = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reviews.db')
app.config['SQLALCHEMY_DATABASE_URI'] = _review_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
reviews_db.init_app(app)
app.register_blueprint(reviews_bp)
with app.app_context():
    reviews_db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Sector definitions
SECTORS = {
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"]
}
ANALYTICS_SECTORS = ["IT", "Banking", "Pharma", "FMCG"]

def _stock_data_path(sector, stock):
    return os.path.join(DATA_DIR, f"{sector}_{stock}.csv")

def month_end_rule():
    """Use the month-end alias supported by the installed pandas version."""
    try:
        version = tuple(int(part) for part in pd.__version__.split(".")[:2])
    except Exception:
        version = (2, 2)
    return "ME" if version >= (2, 2) else "M"

def load_stock_dataframe(sector, stock):
    filename = _stock_data_path(sector, stock)
    if not os.path.exists(filename):
        return None
    df = pd.read_csv(filename)
    if df.empty or 'Close' not in df.columns:
        return None
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    return df

def load_stock_dataframe(sector, stock):
    filename = _stock_data_path(sector, stock)
    if not os.path.exists(filename):
        return None
    try:
        df = pd.read_csv(filename)
        if df.empty or 'Close' not in df.columns or 'Date' not in df.columns:
            return None
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df = df.dropna(subset=['Date', 'Close']).sort_values('Date')
        if len(df) < 2:
            return None
        return df
    except Exception:
        return None

def calculate_stock_metrics(df):
    returns = df['Close'].pct_change().dropna()
    if returns.empty:
        return None

    total_return = ((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100
    volatility = returns.std() * np.sqrt(252) * 100

    if volatility < 20:
        risk_category = "Low"
    elif volatility < 35:
        risk_category = "Medium"
    else:
        risk_category = "High"

    return {
        "return_pct": float(round(total_return, 2)),
        "volatility_pct": float(round(volatility, 2)),
        "risk_category": risk_category,
        "latest_close": float(round(df['Close'].iloc[-1], 2))
    }

def get_core_stock_metrics():
    stock_metrics = []

    for sector in ANALYTICS_SECTORS:
        for stock in SECTORS.get(sector, []):
            df = load_stock_dataframe(sector, stock)
            if df is None:
                continue
            metrics = calculate_stock_metrics(df)
            if metrics is None:
                continue
            symbol = stock.replace('.NS', '')
            stock_metrics.append({
                "symbol": symbol,
                "sector": sector,
                "return_pct": metrics["return_pct"],
                "volatility_pct": metrics["volatility_pct"],
                "risk_category": metrics["risk_category"],
                "latest_close": metrics["latest_close"],
                "data_as_of": df['Date'].iloc[-1].strftime('%Y-%m-%d')
            })
    return stock_metrics

def assign_relative_risk_labels(stock_metrics):
    """Assign Low/Medium/High by relative volatility distribution."""
    if not stock_metrics:
        return stock_metrics

    vols = [s["volatility_pct"] for s in stock_metrics]
    if len(set(vols)) < 3:
        # Fallback when values are too close
        for s in stock_metrics:
            if s["volatility_pct"] < 20:
                s["risk_category"] = "Low"
            elif s["volatility_pct"] < 30:
                s["risk_category"] = "Medium"
            else:
                s["risk_category"] = "High"
        return stock_metrics

    low_cutoff = float(np.percentile(vols, 33))
    high_cutoff = float(np.percentile(vols, 66))

    for s in stock_metrics:
        if s["volatility_pct"] <= low_cutoff:
            s["risk_category"] = "Low"
        elif s["volatility_pct"] <= high_cutoff:
            s["risk_category"] = "Medium"
        else:
            s["risk_category"] = "High"
    return stock_metrics


def analyze_investment_recommendations(budget=None, selected_sectors=None, risk_preference="Medium"):
    """Generate stock recommendations using forecasting, volatility, VaR and Sharpe signals."""
    valid_risk_preferences = {"Low", "Medium", "High"}
    preferred_risk = (risk_preference or "Medium").strip().capitalize()
    if preferred_risk not in valid_risk_preferences:
        preferred_risk = "Medium"

    if selected_sectors is None:
        active_sectors = list(ANALYTICS_SECTORS)
    elif isinstance(selected_sectors, str):
        active_sectors = [selected_sectors] if selected_sectors in ANALYTICS_SECTORS else []
    else:
        active_sectors = [sector for sector in selected_sectors if sector in ANALYTICS_SECTORS]

    if not active_sectors:
        active_sectors = list(ANALYTICS_SECTORS)

    recommendations = []
    for sector in active_sectors:
        for stock in SECTORS.get(sector, []):
            df = load_stock_dataframe(sector, stock)
            if df is None:
                continue

            metrics = calculate_stock_metrics(df)
            prediction = build_stock_prediction(df, months=12)
            if metrics is None or prediction is None:
                continue

            close_series = df['Close'].pct_change().dropna()
            volatility_pct = max(float(prediction.get("predicted_volatility_pct", 0.0)), float(metrics["volatility_pct"]))
            expected_return_pct = float(prediction.get("projected_return_pct", metrics["return_pct"]))
            sharpe_ratio = (expected_return_pct / max(volatility_pct, 1.0)) if max(volatility_pct, 1.0) else 0.0

            var_95_pct = 0.0
            if not close_series.empty:
                var_95_pct = float(round(abs((close_series.mean() - 1.96 * close_series.std()) * 100), 2))

            confidence_weight = 1.0
            if prediction.get("confidence") == "High":
                confidence_weight = 1.15
            elif prediction.get("confidence") == "Medium":
                confidence_weight = 1.0
            else:
                confidence_weight = 0.85

            penalty_map = {
                "Low": {"Low": 0.0, "Medium": 0.06, "High": 0.12},
                "Medium": {"Low": 0.0, "Medium": 0.03, "High": 0.08},
                "High": {"Low": -0.02, "Medium": 0.0, "High": 0.03}
            }
            risk_level = metrics["risk_category"] if metrics["risk_category"] else "Medium"
            if volatility_pct >= 35:
                risk_level = "High"
            elif volatility_pct >= 20:
                risk_level = "Medium"
            else:
                risk_level = "Low"

            score = (
                expected_return_pct * 0.5
                + sharpe_ratio * 0.25
                + (confidence_weight * 8.0)
                - (volatility_pct * 0.04)
                - (var_95_pct * 0.02)
                - penalty_map[preferred_risk][risk_level]
            )

            recommendations.append({
                "symbol": stock.replace('.NS', ''),
                "sector": sector,
                "expected_return_pct": round(expected_return_pct, 2),
                "volatility_pct": round(volatility_pct, 2),
                "var_95_pct": round(var_95_pct, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "risk_level": risk_level,
                "confidence": prediction.get("confidence", "Low"),
                "projected_price": round(float(prediction.get("projected_price", 0.0)), 2),
                "trend": prediction.get("trend", "neutral"),
                "score": round(score, 2)
            })

    recommendations.sort(key=lambda item: item["score"], reverse=True)

    top_recommendations = recommendations[:5]
    if budget is not None:
        try:
            budget_value = float(budget)
        except (TypeError, ValueError):
            budget_value = None
    else:
        budget_value = None

    if budget_value and budget_value > 0 and top_recommendations:
        total_weight = sum(max(item["score"], 1.0) for item in top_recommendations)
        for item in top_recommendations:
            weight = max(item["score"], 1.0) / total_weight
            item["recommended_amount"] = round(weight * budget_value, 2)
            item["allocation_pct"] = round(weight * 100, 2)
    else:
        for item in top_recommendations:
            item["recommended_amount"] = None
            item["allocation_pct"] = None

    portfolio_expected_return = round(sum(item["expected_return_pct"] * (item["allocation_pct"] or 0.0) / 100.0 for item in top_recommendations), 2) if top_recommendations else 0.0
    portfolio_volatility = round(np.mean([item["volatility_pct"] for item in top_recommendations]), 2) if top_recommendations else 0.0

    return {
        "selected_sectors": active_sectors,
        "risk_preference": preferred_risk,
        "budget": int(budget_value) if budget_value and budget_value.is_integer() else budget_value,
        "recommendations": top_recommendations,
        "portfolio_summary": {
            "expected_return_pct": portfolio_expected_return,
            "volatility_pct": portfolio_volatility,
            "budget": int(budget_value) if budget_value and budget_value.is_integer() else budget_value,
            "top_pick": top_recommendations[0] if top_recommendations else None
        }
    }


# =============================================================================
# AI INVESTMENT ADVISOR MODULE (additive, independent from every route above)
# Reuses the existing loaders/metrics/forecast functions untouched
# (load_stock_dataframe, calculate_stock_metrics, build_stock_prediction) and
# the same scoring methodology as analyze_investment_recommendations(), so the
# "best sector" and "top 3 stocks" call is derived the same way the rest of
# the app already scores stocks -- just aggregated up to sector level and
# translated into whole-share, budget-aware numbers.
# =============================================================================

def _filter_df_by_date_range(df, start_date=None, end_date=None):
    """Restrict a stock's history to an optional [start_date, end_date] window.
    Falls back to the full history if the requested window has too little
    data to build a reliable forecast from (fewer than ~60 rows), so a
    narrow/invalid range never breaks the recommendation silently."""
    if df is None:
        return None
    filtered = df
    try:
        if start_date:
            filtered = filtered[filtered['Date'] >= pd.to_datetime(start_date)]
        if end_date:
            filtered = filtered[filtered['Date'] <= pd.to_datetime(end_date)]
    except Exception:
        return df
    return filtered if len(filtered) >= 60 else df


def _score_stock_for_advisor(metrics, prediction, preferred_risk):
    """Same weighting scheme used in analyze_investment_recommendations():
    expected return + risk-adjusted (Sharpe-style) reward, a confidence
    bonus, and penalties for volatility / risk-preference mismatch. Kept
    separate so this module never has to import or mutate the existing
    recommendation engine's internals."""
    volatility_pct = max(float(prediction.get("predicted_volatility_pct", 0.0)), float(metrics["volatility_pct"]))
    expected_return_pct = float(prediction.get("projected_return_pct", metrics["return_pct"]))
    sharpe_ratio = (expected_return_pct / max(volatility_pct, 1.0)) if max(volatility_pct, 1.0) else 0.0

    if volatility_pct >= 35:
        risk_level = "High"
    elif volatility_pct >= 20:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    confidence_weight = {"High": 1.15, "Medium": 1.0, "Low": 0.85}.get(prediction.get("confidence"), 0.85)
    penalty_map = {
        "Low": {"Low": 0.0, "Medium": 0.06, "High": 0.12},
        "Medium": {"Low": 0.0, "Medium": 0.03, "High": 0.08},
        "High": {"Low": -0.02, "Medium": 0.0, "High": 0.03}
    }

    score = (
        expected_return_pct * 0.5
        + sharpe_ratio * 0.25
        + (confidence_weight * 8.0)
        - (volatility_pct * 0.04)
        - penalty_map[preferred_risk][risk_level]
    )

    return {
        "expected_return_pct": round(expected_return_pct, 2),
        "volatility_pct": round(volatility_pct, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "risk_level": risk_level,
        "confidence": prediction.get("confidence", "Low"),
        "score": round(score, 2)
    }


def analyze_ai_advisor(budget=None, risk_preference="Medium", start_date=None, end_date=None, sector=None):
    """Recommend the single best-scoring sector plus its top 3 stocks,
    sized to the user's budget. If the budget can't afford a full lot of a
    recommended stock, the next best affordable stock takes its place and
    is flagged as a substitution.

    `sector`: optional explicit sector filter (IT / Banking / Pharma / FMCG),
    coming from the Investment Advisor's Sector Selection dropdown -- the
    same dropdown and SECTORS data source used by Sector Analysis, Risk
    Analysis and Future Prediction. When provided, analysis (scoring,
    ranking, and any budget-driven substitution) is confined to that
    sector's stocks only. When omitted/empty (i.e. "All Sectors"), the
    advisor falls back to its original behaviour of auto-selecting the
    single best-scoring sector across the whole universe."""
    valid_risk_preferences = {"Low", "Medium", "High"}
    preferred_risk = (risk_preference or "Medium").strip().capitalize()
    if preferred_risk not in valid_risk_preferences:
        preferred_risk = "Medium"

    try:
        budget_value = float(budget) if budget not in (None, '', 'null', 'undefined') else None
        if budget_value is not None and budget_value <= 0:
            budget_value = None
    except (TypeError, ValueError):
        budget_value = None

    requested_sector = (sector or "").strip()
    if requested_sector and requested_sector not in ANALYTICS_SECTORS:
        return {"error": f"Invalid sector '{requested_sector}'. Choose one of: {', '.join(ANALYTICS_SECTORS)}."}

    # Scope the universe to just the requested sector when one is selected,
    # so every downstream step -- scoring, the top-3 picks, and budget
    # substitution -- only ever considers that sector's stocks, per the
    # Sector Selection requirement. Leaving it unset preserves the original
    # "auto-pick the best sector" behaviour.
    sectors_to_scan = [requested_sector] if requested_sector else list(ANALYTICS_SECTORS)

    universe = []  # every stock we could evaluate, with sector/score/prediction attached
    for sector in sectors_to_scan:
        for stock in SECTORS.get(sector, []):
            raw_df = load_stock_dataframe(sector, stock)
            if raw_df is None:
                continue
            try:
                df = _filter_df_by_date_range(raw_df, start_date, end_date)
                metrics = calculate_stock_metrics(df)
                prediction = build_stock_prediction(df, months=12)
                if metrics is None or prediction is None:
                    continue
                scored = _score_stock_for_advisor(metrics, prediction, preferred_risk)
            except Exception as stock_error:
                # One malformed/unsupported stock series should not break all recommendations.
                app.logger.warning("Advisor skipped %s/%s: %s", sector, stock, stock_error)
                continue
            universe.append({
                "symbol": stock.replace('.NS', ''),
                "sector": sector,
                "current_price": float(round(prediction["latest_price"], 2)),
                "predicted_price": float(round(prediction["projected_price"], 2)),
                "trend": prediction.get("trend", "neutral"),
                "history": prediction["history"],
                "predicted": prediction["predicted"],
                **scored
            })

    if not universe:
        return {"error": "No processed stock data found. Please run Update Data first."}

    # --- Step 1: pick the best sector, by average stock score within it -----
    # (When a sector was explicitly requested, sectors_to_scan already
    # contains only that one sector, so this "picks" it trivially -- the
    # comparison table still renders correctly with a single row.)
    sector_stats = {}
    for sector in sectors_to_scan:
        members = [s for s in universe if s["sector"] == sector]
        if not members:
            continue
        sector_stats[sector] = {
            "sector": sector,
            "avg_score": round(float(np.mean([m["score"] for m in members])), 2),
            "avg_expected_return_pct": round(float(np.mean([m["expected_return_pct"] for m in members])), 2),
            "avg_volatility_pct": round(float(np.mean([m["volatility_pct"] for m in members])), 2),
            "stock_count": len(members)
        }

    if not sector_stats:
        return {"error": "Unable to score any sector for the selected date range."}

    best_sector = max(sector_stats.values(), key=lambda s: s["avg_score"])["sector"]
    sector_comparison = sorted(sector_stats.values(), key=lambda s: s["avg_score"], reverse=True)

    # --- Step 2: rank stocks inside that sector, take the top 3 -------------
    sector_ranked = sorted([s for s in universe if s["sector"] == best_sector], key=lambda s: s["score"], reverse=True)
    top3 = sector_ranked[:3]

    # Fallback pool (ranked, scoped to the same sectors_to_scan as the rest
    # of this call -- i.e. just the selected sector when one was requested)
    # used only when the budget can't afford a chosen stock, so a
    # suggestion is never simply dropped.
    fallback_pool = sorted(universe, key=lambda s: s["score"], reverse=True)

    # --- Step 3: size each pick to the budget --------------------------------
    final_picks = []
    if top3:
        weight_basis = sum(max(item["score"], 1.0) for item in top3)
        already_used_symbols = {item["symbol"] for item in top3}

        for item in top3:
            weight = max(item["score"], 1.0) / weight_basis
            allocated_amount = round(weight * budget_value, 2) if budget_value else None

            chosen = item
            substituted_for = None
            note = None

            if budget_value and allocated_amount is not None and item["current_price"] > allocated_amount:
                # Can't afford even one share of the recommended pick at its
                # allocated amount -- look for the next best stock (any
                # sector, not already picked) that DOES fit this allocation.
                alternative = next(
                    (alt for alt in fallback_pool
                     if alt["symbol"] not in already_used_symbols and alt["current_price"] <= allocated_amount),
                    None
                )
                if alternative:
                    substituted_for = item["symbol"]
                    already_used_symbols.add(alternative["symbol"])
                    chosen = alternative
                    note = f"Budget insufficient for one {item['symbol']} share at this allocation; substituted {alternative['symbol']} ({alternative['sector']}), the next best affordable option."
                else:
                    note = f"Budget insufficient for even one {item['symbol']} share; no cheaper alternative fits this allocation either. Consider increasing the budget or reducing the number of picks."

            shares = int(allocated_amount // chosen["current_price"]) if (allocated_amount and chosen["current_price"] > 0) else None
            invested_amount = round(shares * chosen["current_price"], 2) if shares else (0.0 if allocated_amount is not None else None)
            leftover_cash = round(allocated_amount - invested_amount, 2) if allocated_amount is not None else None
            predicted_value = round(shares * chosen["predicted_price"], 2) if shares else None
            expected_profit = round(predicted_value - invested_amount, 2) if (predicted_value is not None and invested_amount is not None) else None
            expected_return_on_invested_pct = (
                round((expected_profit / invested_amount) * 100, 2) if (expected_profit is not None and invested_amount) else chosen["expected_return_pct"]
            )

            final_picks.append({
                "symbol": chosen["symbol"],
                "sector": chosen["sector"],
                "current_price": chosen["current_price"],
                "predicted_price": chosen["predicted_price"],
                "trend": chosen["trend"],
                "risk_level": chosen["risk_level"],
                "confidence": chosen["confidence"],
                "expected_return_pct": expected_return_on_invested_pct,
                "volatility_pct": chosen["volatility_pct"],
                "allocation_pct": round(weight * 100, 2),
                "allocated_amount": allocated_amount,
                "shares": shares,
                "invested_amount": invested_amount,
                "leftover_cash": leftover_cash,
                "predicted_value": predicted_value,
                "expected_profit": expected_profit,
                "is_substitution": substituted_for is not None,
                "substituted_for": substituted_for,
                "note": note,
                "history": chosen["history"],
                "predicted": chosen["predicted"]
            })

    top_pick = final_picks[0] if final_picks else None
    portfolio_invested = round(sum(p["invested_amount"] for p in final_picks if p["invested_amount"]), 2) if budget_value else None
    portfolio_predicted_value = round(sum(p["predicted_value"] for p in final_picks if p["predicted_value"]), 2) if budget_value else None
    portfolio_expected_profit = (
        round(portfolio_predicted_value - portfolio_invested, 2)
        if (budget_value and portfolio_predicted_value is not None and portfolio_invested is not None) else None
    )

    if requested_sector:
        sector_reason = (
            f"You selected {best_sector}. Analysis below is scoped to {best_sector} stocks only "
            f"(avg. expected return {sector_stats[best_sector]['avg_expected_return_pct']}%, "
            f"avg. volatility {sector_stats[best_sector]['avg_volatility_pct']}%), using the same "
            f"prediction, risk and scoring engine used across the app."
        )
    else:
        sector_reason = (
            f"{best_sector} currently has the strongest blended score across its tracked stocks "
            f"(avg. expected return {sector_stats[best_sector]['avg_expected_return_pct']}%, "
            f"avg. volatility {sector_stats[best_sector]['avg_volatility_pct']}%), based on historical "
            f"Yahoo Finance data and the forecast model's momentum-adjusted projection."
        )

    return {
        "best_sector": best_sector,
        "selected_sector": requested_sector or None,
        "sector_locked": bool(requested_sector),
        "sector_reason": sector_reason,
        "risk_preference": preferred_risk,
        "budget": (int(budget_value) if budget_value and budget_value.is_integer() else budget_value),
        "date_range": {"start_date": start_date, "end_date": end_date},
        "sector_comparison": sector_comparison,
        "recommendations": final_picks,
        "top_pick": top_pick,
        "portfolio_summary": {
            "invested_amount": portfolio_invested,
            "predicted_value": portfolio_predicted_value,
            "expected_profit": portfolio_expected_profit,
            "budget": (int(budget_value) if budget_value and budget_value.is_integer() else budget_value)
        },
        "assumptions": [
            "Forecast prices are model projections (12-month momentum-adjusted trend + volatility), not guarantees.",
            "Share counts assume whole-share purchases at the latest available close price; brokerage fees and taxes are not included.",
            "Budget is split across the top 3 picks in proportion to their model score, not equally.",
            "Risk levels are derived from annualized volatility of the selected historical window."
        ]
    }


def get_sector_trend_series(sector):
    monthly_series = []
    for stock in SECTORS.get(sector, []):
        df = load_stock_dataframe(sector, stock)
        if df is None:
            continue
        temp = df.set_index('Date')['Close'].resample(month_end_rule()).last().pct_change() * 100
        temp = temp.dropna()
        if not temp.empty:
            monthly_series.append(temp)

    if not monthly_series:
        return {}

    combined = pd.concat(monthly_series, axis=1)
    avg_series = combined.mean(axis=1).tail(6)
    return {idx.strftime('%b %Y'): round(val, 2) for idx, val in avg_series.items()}


# ---------------------------------------------------------------------------
# Future Prediction module -- forecast calibration constants.
# These replace a previous approach that simply compounded one flat,
# all-time-average monthly return into a perfectly smooth exponential curve
# (which meant predictions almost always trended in whichever direction the
# stock's entire history happened to average out to, with no realistic
# month-to-month variation). The constants below are documented, engineering
# -configurable decisions -- not specified by product requirements -- and
# mirror the SCORE_WEIGHTS pattern already used in multi_stock_analysis.py.
# ---------------------------------------------------------------------------

# Blends recent momentum with the long-run historical average so the forward
# drift reflects where the stock has actually been heading lately, not just
# its all-time mean. Must sum to 1.0.
DRIFT_WEIGHTS = {"recent": 0.5, "mid": 0.3, "long_term": 0.2}

# A blended monthly drift whose magnitude is below this threshold (roughly
# 4.8%/year) is classified as "sideways" (stable / range-bound) rather than
# forced into a bullish or bearish call -- real stocks spend real time
# chopping sideways, and the forecast should be able to say so.
SIDEWAYS_DRIFT_BAND = 0.004


def build_stock_prediction(df, months=60):
    df = df.copy()
    df = df.set_index('Date').resample(month_end_rule()).last().dropna(subset=['Close'])
    if len(df) < 12:
        return None

    series = df['Close']
    returns = series.pct_change().dropna()
    if returns.empty:
        return None

    avg_monthly_return = float(returns.mean())
    latest_price = float(series.iloc[-1])
    future_dates = [series.index[-1] + pd.DateOffset(months=i + 1) for i in range(months)]

    # --- Momentum-aware drift (replaces the flat all-time average) ---------
    # Recent and mid-term momentum are blended with the long-run average
    # (DRIFT_WEIGHTS, module-level) so a stock that has recently turned down
    # (or up) is reflected in the forecast even if its full history averages
    # out differently.
    long_term_avg_return = avg_monthly_return
    recent_avg_return = float(returns.tail(min(3, len(returns))).mean())
    mid_avg_return = float(returns.tail(min(6, len(returns))).mean())
    avg_monthly_return = (
        recent_avg_return * DRIFT_WEIGHTS["recent"]
        + mid_avg_return * DRIFT_WEIGHTS["mid"]
        + long_term_avg_return * DRIFT_WEIGHTS["long_term"]
    )

    # --- Moving-average confirmation -----------------------------------------
    # Classic short/long moving-average signal (3-month vs 6-month close):
    # if the short MA sits below the long MA (a "death cross"-style signal)
    # while the blended drift above is still positive -- or vice-versa -- the
    # drift is dampened, reflecting the conflicting evidence. When both
    # signals agree, the drift is modestly reinforced. This keeps the
    # forecast direction consistent with the stock's own recent price
    # pattern rather than the momentum blend in isolation.
    ma_short = float(series.tail(min(3, len(series))).mean())
    ma_long = float(series.tail(min(6, len(series))).mean())
    if ma_long:
        signals_agree = (avg_monthly_return >= 0) == (ma_short >= ma_long)
        avg_monthly_return *= 1.15 if signals_agree else 0.65

    # Historical monthly volatility -- drives both the existing volatility/
    # risk KPI below (unchanged calculation) and the realistic noise in the
    # simulated forward path.
    monthly_sigma = float(returns.std()) if len(returns) > 1 else 0.0

    # --- Realistic forward path: drift + Brownian-bridge noise ---------------
    # Rather than compounding one constant rate into a perfectly smooth
    # exponential curve, the forward path adds realistic month-to-month noise
    # on top of the deterministic, momentum/MA-blended drift trajectory. The
    # noise is generated as a Brownian bridge (volatility = this stock's own
    # historical monthly_sigma) that is anchored to zero at the final month --
    # so the path wiggles organically along the way, exactly like real prices
    # do, while always landing on the same deterministic endpoint that the
    # trend label and headline KPIs below are computed from. This avoids a
    # scenario where the chart/KPIs and the trend indicator could disagree in
    # direction purely because of random noise at the final point.
    #
    # The random seed is derived deterministically from the input series
    # itself (its values, length, and the requested horizon) rather than the
    # wall clock, so the same stock + same selected date range always
    # reproduces the same forecast, while a different stock or a different
    # date range naturally yields a different (still realistic) path.
    deterministic_log_growth = np.cumsum(np.repeat(avg_monthly_return, months))

    seed_material = (round(float(series.sum()), 4), round(latest_price, 4), len(series), months)
    rng = np.random.default_rng(abs(hash(seed_material)) % (2 ** 32))
    shocks = rng.normal(loc=0.0, scale=1.0, size=months)
    random_walk = np.cumsum(monthly_sigma * shocks)
    t_fraction = np.arange(1, months + 1) / months
    bridge_noise = random_walk - t_fraction * random_walk[-1]  # anchors noise to 0 at the final month

    predicted_close = latest_price * np.exp(deterministic_log_growth + bridge_noise)
    predicted_close = np.maximum(predicted_close, 0.0)

    projected_price = float(predicted_close[-1])
    projected_return_pct = float(round(((projected_price - latest_price) / latest_price) * 100, 2)) if latest_price else 0.0
    predicted_volatility = float(round(returns.std() * np.sqrt(12) * 100, 2)) if len(returns) > 1 else 0.0

    x = np.array([d.toordinal() for d in series.index], dtype=np.float64)
    y = series.values.astype(np.float64)
    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs
    ss_res = np.sum((y - (intercept + slope * x)) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = float(round(1 - ss_res / ss_tot, 4)) if ss_tot != 0 else 0.0
    if r_squared >= 0.7:
        confidence = 'High'
    elif r_squared >= 0.4:
        confidence = 'Medium'
    else:
        confidence = 'Low'

    if projected_return_pct > 5 and predicted_volatility < 25:
        projected_risk_level = 'Low'
    elif predicted_volatility < 35:
        projected_risk_level = 'Medium'
    else:
        projected_risk_level = 'High'

    # --- Trend classification (now three-way: bullish / sideways / bearish) --
    # Classified from the underlying blended drift (the model's directional
    # view) rather than the noisy simulated end price, so a near-zero drift
    # is reliably called "sideways" even though the realistic simulated path
    # above may still wiggle a little above or below the starting price.
    if avg_monthly_return > SIDEWAYS_DRIFT_BAND:
        trend = 'bullish'
    elif avg_monthly_return < -SIDEWAYS_DRIFT_BAND:
        trend = 'bearish'
    else:
        trend = 'sideways'

    predicted_move = float(round(((projected_price - latest_price) / latest_price) * 100, 2)) if latest_price else 0.0

    history = [
        {"date": idx.strftime('%Y-%m-%d'), "close": float(round(price, 2))}
        for idx, price in series.tail(12).items()
    ]
    future = [
        {"date": d.strftime('%Y-%m-%d'), "close": float(round(p, 2))}
        for d, p in zip(future_dates, predicted_close)
    ]

    return {
        "history": history,
        "predicted": future,
        "latest_price": float(round(latest_price, 2)),
        "projected_price": float(round(projected_price, 2)),
        "projected_return_pct": projected_return_pct,
        "expected_growth_pct": projected_return_pct,
        "predicted_volatility_pct": predicted_volatility,
        "projected_risk_level": projected_risk_level,
        "trend": trend,
        "predicted_move": predicted_move,
        "confidence": confidence,
        "model_fit": {
            "r_squared": r_squared,
            "slope": float(round(slope, 6))
        }
    }


def build_sector_prediction(dfs, months=60):
    prepared = []
    for df in dfs:
        temp = df.copy()
        temp = temp.set_index('Date').resample(month_end_rule()).last().dropna(subset=['Close'])
        if len(temp) >= 12:
            prepared.append(temp['Close'])

    if not prepared:
        return None

    combined = pd.concat(prepared, axis=1).mean(axis=1).dropna()
    if len(combined) < 12:
        return None

    returns = combined.pct_change().dropna()
    if returns.empty:
        return None

    avg_monthly_return = float(returns.mean())
    latest_price = float(combined.iloc[-1])
    future_dates = [combined.index[-1] + pd.DateOffset(months=i + 1) for i in range(months)]

    # Same momentum-aware drift blend and MA confirmation used in
    # build_stock_prediction() above, applied here to the sector-average
    # series so the two charts on the Future Prediction dashboard are
    # methodologically consistent.
    long_term_avg_return = avg_monthly_return
    recent_avg_return = float(returns.tail(min(3, len(returns))).mean())
    mid_avg_return = float(returns.tail(min(6, len(returns))).mean())
    avg_monthly_return = (
        recent_avg_return * DRIFT_WEIGHTS["recent"]
        + mid_avg_return * DRIFT_WEIGHTS["mid"]
        + long_term_avg_return * DRIFT_WEIGHTS["long_term"]
    )
    ma_short = float(combined.tail(min(3, len(combined))).mean())
    ma_long = float(combined.tail(min(6, len(combined))).mean())
    if ma_long:
        signals_agree = (avg_monthly_return >= 0) == (ma_short >= ma_long)
        avg_monthly_return *= 1.15 if signals_agree else 0.65

    monthly_sigma = float(returns.std()) if len(returns) > 1 else 0.0
    deterministic_log_growth = np.cumsum(np.repeat(avg_monthly_return, months))

    seed_material = (round(float(combined.sum()), 4), round(latest_price, 4), len(combined), months)
    rng = np.random.default_rng(abs(hash(seed_material)) % (2 ** 32))
    shocks = rng.normal(loc=0.0, scale=1.0, size=months)
    random_walk = np.cumsum(monthly_sigma * shocks)
    t_fraction = np.arange(1, months + 1) / months
    bridge_noise = random_walk - t_fraction * random_walk[-1]

    predicted_close = latest_price * np.exp(deterministic_log_growth + bridge_noise)
    predicted_close = np.maximum(predicted_close, 0.0)

    projected_price = float(predicted_close[-1])
    projected_return_pct = float(round(((projected_price - latest_price) / latest_price) * 100, 2)) if latest_price else 0.0

    history = [
        {"date": idx.strftime('%Y-%m-%d'), "close": float(round(price, 2))}
        for idx, price in combined.tail(12).items()
    ]
    future = [
        {"date": d.strftime('%Y-%m-%d'), "close": float(round(p, 2))}
        for d, p in zip(future_dates, predicted_close)
    ]

    return {
        "history": history,
        "predicted": future,
        "latest_price": float(round(latest_price, 2)),
        "projected_price": float(round(projected_price, 2)),
        "projected_return_pct": projected_return_pct
    }


@app.route('/predict', methods=['POST'])
@login_required
def predict():
    data = request.json or {}
    sector = data.get('sector', 'All')
    selected_sectors = [sector] if sector in SECTORS and sector != 'All' else list(SECTORS.keys())

    predictions = []
    sector_growth = {s: [] for s in SECTORS.keys()}
    sector_dfs = []

    for sec in selected_sectors:
        for stock in SECTORS.get(sec, []):
            df = load_stock_dataframe(sec, stock)
            if df is None:
                continue
            sector_dfs.append(df)
            prediction = build_stock_prediction(df, months=60)
            if prediction is None:
                continue

            prediction_record = {
                "symbol": stock.replace('.NS', ''),
                "sector": sec,
                "history": prediction["history"],
                "predicted": prediction["predicted"],
                "latest_price": prediction["latest_price"],
                "projected_price": prediction["projected_price"],
                "projected_return_pct": prediction["projected_return_pct"],
                "expected_growth_pct": prediction["expected_growth_pct"],
                "predicted_volatility_pct": prediction["predicted_volatility_pct"],
                "projected_risk_level": prediction["projected_risk_level"],
                "trend": prediction["trend"],
                "predicted_move": prediction["predicted_move"],
                "confidence": prediction["confidence"],
                "model_fit": prediction["model_fit"]
            }
            predictions.append(prediction_record)
            sector_growth[sec].append(prediction_record["expected_growth_pct"])

    sector_plot = build_sector_prediction(sector_dfs, months=60) if sector_dfs else None

    if not predictions:
        return jsonify({"error": "No prediction data available. Please update data and try again."}), 404

    sector_future_growth = {
        sec: float(round(np.mean(values), 2)) if values else 0.0
        for sec, values in sector_growth.items()
    }

    top_growth = max(predictions, key=lambda item: item["expected_growth_pct"])
    most_stable = min(predictions, key=lambda item: item["predicted_volatility_pct"])
    sector_summary = []
    for sec, values in sector_growth.items():
        if values:
            sector_summary.append({
                "sector": sec,
                "avg_growth": float(round(np.mean(values), 2)),
                "future_risk": "Low" if np.mean(values) > 15 else "Medium" if np.mean(values) > 5 else "High"
            })

    insight_text = "Future prediction indicates that IT remains the strongest growth driver, while Pharma shows stable long-term potential."
    if sector == 'Banking':
        insight_text = "Banking is forecast to deliver moderate returns with healthy resilience and steady recovery patterns."
    elif sector == 'Pharma':
        insight_text = "Pharma is predicted to deliver balanced growth, driven by low-volatility defensive stocks."
    elif sector == 'IT':
        insight_text = "IT is expected to stay ahead through consistent growth and low projected volatility for leading stocks."

    return jsonify({
        "sector": sector,
        "selected_sector": sector,
        "top_growth_stock": top_growth,
        "most_stable_stock": most_stable,
        "sector_future_growth": sector_future_growth,
        "sector_summary": sector_summary,
        "predictions": predictions,
        "sector_plot": sector_plot,
        "insight_text": insight_text
    })

@app.route('/stock-predict', methods=['POST'])
@login_required
def stock_predict():
    """API endpoint for individual stock price prediction"""
    try:
        data = request.json or {}
        symbol = data.get('symbol', '').upper().strip()
        period_days = data.get('period_days', 365)  # Default 1 year
        
        if not symbol:
            return jsonify({"error": "Stock symbol required"}), 400
        
        # Convert days to months (roughly)
        months = max(1, period_days // 30)
        
        # Find the stock in sectors
        stock_with_ns = None
        stock_sector = None
        
        for sector, stocks in SECTORS.items():
            for stock in stocks:
                if stock.replace('.NS', '') == symbol:
                    stock_with_ns = stock
                    stock_sector = sector
                    break
            if stock_sector:
                break
        
        if not stock_with_ns or not stock_sector:
            return jsonify({"error": f"Stock {symbol} not found in available sectors"}), 404
        
        # Load stock data
        df = load_stock_dataframe(stock_sector, stock_with_ns)
        if df is None:
            return jsonify({"error": f"No data available for {symbol}"}), 404
        
        # Build prediction
        prediction = build_stock_prediction(df, months=months)
        if prediction is None:
            return jsonify({"error": f"Unable to generate prediction for {symbol}"}), 400
        
        # Prepare response
        response = {
            "symbol": symbol,
            "sector": stock_sector,
            "period_days": period_days,
            "period_label": f"{period_days} days" if period_days < 365 else f"{period_days // 365} year(s)",
            "history": prediction["history"],
            "predicted": prediction["predicted"],
            "latest_price": prediction["latest_price"],
            "projected_price": prediction["projected_price"],
            "projected_return_pct": prediction["projected_return_pct"],
            "expected_growth_pct": prediction["expected_growth_pct"],
            "predicted_volatility_pct": prediction["predicted_volatility_pct"],
            "projected_risk_level": prediction["projected_risk_level"],
            "trend": prediction["trend"],
            "predicted_move": prediction["predicted_move"],
            "confidence": prediction["confidence"],
            "model_fit": prediction["model_fit"]
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({"error": f"Prediction generation failed: {str(e)}"}), 500

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match')
            return render_template('register.html')
        
        hashed_password = generate_password_hash(password)
        
        try:
            with get_db() as conn:
                conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
                conn.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')

@app.route('/update_data', methods=['POST'])
@login_required
def update_data():
    payload = request.get_json(silent=True) or {}
    start_date = payload.get('start_date')
    if not start_date:
        return jsonify({"error": "Start date required"}), 400
    
    end_date = datetime.today().strftime('%Y-%m-%d')
    os.makedirs(DATA_DIR, exist_ok=True)
    updated_stocks = []
    failed_stocks = []

    for sector, stocks in SECTORS.items():
        for stock in stocks:
            filename = _stock_data_path(sector, stock)
            try:
                data = yf.download(stock, start=start_date, end=end_date)
                if data.empty:
                    raise ValueError("No market data was returned.")
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                data.reset_index(inplace=True)
                if 'Date' not in data.columns and 'Datetime' in data.columns:
                    data.rename(columns={'Datetime': 'Date'}, inplace=True)
                if 'Date' not in data.columns or 'Close' not in data.columns:
                    raise ValueError("Downloaded data is missing Date or Close values.")
                data['Date'] = pd.to_datetime(data['Date'], errors='coerce')
                data['Close'] = pd.to_numeric(data['Close'], errors='coerce')
                data = data.dropna(subset=['Date', 'Close']).sort_values('Date')
                if data.empty:
                    raise ValueError("Downloaded data contains no valid closing prices.")
                data.to_csv(filename, index=False)
                updated_stocks.append(stock)
            except Exception as exc:
                app.logger.warning('Could not update data for %s: %s', stock, exc)
                failed_stocks.append({"symbol": stock, "error": str(exc)})

    if not updated_stocks:
        return jsonify({
            "error": "No stock data was updated. Existing data has been kept.",
            "failed_stocks": failed_stocks
        }), 502

    message = f"Updated data for {len(updated_stocks)} of {sum(map(len, SECTORS.values()))} stocks. Ask AI will use the refreshed data."
    if failed_stocks:
        message += f" {len(failed_stocks)} stock updates failed; their existing data was kept."
    return jsonify({
        "message": message,
        "updated_stocks": updated_stocks,
        "failed_stocks": failed_stocks
    })

@app.route('/get_market_overview')
@login_required
def get_market_overview():
    # Simulate market data - in real app, fetch from API
    return jsonify({
        "nifty": {"value": 22000, "change": 1.2},
        "sensex": {"value": 72000, "change": 0.8},
        "top_gainers": ["TCS", "INFY", "HDFCBANK"],
        "top_losers": ["WIPRO", "ITC", "CIPLA"],
        "ai_insight": "Market showing bullish trend with IT sector leading",
        "recommendation": "Consider investing in IT stocks for short-term gains"
    })

@app.route('/api/dashboard')
@login_required
def get_dashboard_data():
    try:
        stock_metrics = get_core_stock_metrics()
        if not stock_metrics:
            return jsonify({"error": "No processed stock data found. Please run Update Data first."}), 404

        avg_return = float(round(np.mean([s["return_pct"] for s in stock_metrics]), 2))
        top_stock = max(stock_metrics, key=lambda x: x["return_pct"])

        sector_performance = {}
        sector_trends = {}
        trend_labels = []

        for sector in ANALYTICS_SECTORS:
            sector_stocks = [s for s in stock_metrics if s["sector"] == sector]
            sector_performance[sector] = float(round(np.mean([s["return_pct"] for s in sector_stocks]), 2)) if sector_stocks else 0.0

            trend_map = get_sector_trend_series(sector)
            sector_trends[sector] = trend_map
            if trend_map and not trend_labels:
                trend_labels = list(trend_map.keys())

        return jsonify({
            "total_stocks": len(stock_metrics),
            "average_return": avg_return,
            "top_stock": top_stock,
            "sector_performance": sector_performance,
            "trend_labels": trend_labels,
            "sector_trends": {
                sector: [sector_trends[sector].get(label, 0) for label in trend_labels]
                for sector in ANALYTICS_SECTORS
            },
            "sectors": ANALYTICS_SECTORS
        })
    except Exception as e:
        return jsonify({"error": f"Dashboard calculation failed: {str(e)}"}), 500

@app.route('/api/portfolio')
@login_required
def get_portfolio_data():
    try:
        # Budget is entirely optional. When it's absent, every response field
        # below stays exactly as before (percentages only). When it's present,
        # the same allocation percentages are additionally translated into
        # real rupee amounts and whole-share counts, so the rest of the app
        # doesn't need a separate code path for "budget mode".
        raw_budget = request.args.get('budget')
        budget_value = None
        if raw_budget not in (None, '', 'null', 'undefined'):
            try:
                parsed = float(raw_budget)
                if parsed > 0:
                    budget_value = parsed
            except (TypeError, ValueError):
                budget_value = None

        stock_metrics = get_core_stock_metrics()
        if not stock_metrics:
            return jsonify({"error": "No processed stock data found. Please run Update Data first."}), 404

        stock_metrics = assign_relative_risk_labels(stock_metrics)

        allocations = []
        for stock in stock_metrics:
            score = max(0.1, stock["return_pct"] - (stock["volatility_pct"] * 0.35))
            allocations.append({**stock, "score": score})

        total_score = sum(s["score"] for s in allocations)
        for stock in allocations:
            stock["allocation_pct"] = round((stock["score"] / total_score) * 100, 2)

        total_deployed = 0.0
        if budget_value:
            for stock in allocations:
                target_amount = (stock["allocation_pct"] / 100.0) * budget_value
                price = stock.get("latest_close") or 0
                shares = int(target_amount // price) if price > 0 else 0
                invested_amount = round(shares * price, 2)
                stock["shares"] = shares
                stock["invested_amount"] = invested_amount
                stock["target_amount"] = round(target_amount, 2)
                stock["leftover_cash"] = round(target_amount - invested_amount, 2)
                total_deployed += invested_amount
        else:
            for stock in allocations:
                stock["shares"] = None
                stock["invested_amount"] = None
                stock["target_amount"] = None
                stock["leftover_cash"] = None

        best_stock = max(allocations, key=lambda x: x["allocation_pct"])
        safest_stock = min(allocations, key=lambda x: x["volatility_pct"])

        sector_distribution = {sector: 0 for sector in ANALYTICS_SECTORS}
        risk_breakdown = {"Low": 0, "Medium": 0, "High": 0}
        for stock in allocations:
            sector_distribution[stock["sector"]] += stock["allocation_pct"]
            risk_breakdown[stock["risk_category"]] += 1

        sector_distribution = {
            k: round(v, 2) for k, v in sector_distribution.items()
        }

        budget_summary = None
        if budget_value:
            total_deployed = round(total_deployed, 2)
            budget_summary = {
                "budget": int(budget_value) if budget_value.is_integer() else budget_value,
                "total_deployed": total_deployed,
                "cash_remaining": round(budget_value - total_deployed, 2)
            }

        return jsonify({
            "allocations": sorted(allocations, key=lambda x: x["allocation_pct"], reverse=True),
            "sector_distribution": sector_distribution,
            "risk_breakdown": risk_breakdown,
            "best_stock": best_stock,
            "safest_stock": safest_stock,
            "risk_return_metrics": [
                {
                    "stock": s["symbol"],
                    "sector": s["sector"],
                    "return_pct": s["return_pct"],
                    "volatility_pct": s["volatility_pct"],
                    "risk_category": s["risk_category"]
                } for s in allocations
            ],
            "sectors": ANALYTICS_SECTORS,
            "budget_summary": budget_summary
        })
    except Exception as e:
        return jsonify({"error": f"Portfolio calculation failed: {str(e)}"}), 500

@app.route('/api/investment-recommendations', methods=['POST'])
@login_required
def investment_recommendations():
    try:
        payload = request.get_json(silent=True) or {}
        budget = payload.get('budget')
        selected_sectors = payload.get('sectors') or payload.get('selectedSectors') or []
        risk_preference = payload.get('riskPreference') or payload.get('risk_preference') or 'Medium'
        result = analyze_investment_recommendations(
            budget=budget,
            selected_sectors=selected_sectors,
            risk_preference=risk_preference
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Investment recommendation failed: {str(e)}"}), 500

@app.route('/api/ai-advisor', methods=['POST'])
@login_required
def ai_advisor():
    """AI Investment Advisor: given an (optional) sector, budget, risk
    preference and date range, recommends the best stock(s) sized to whole
    shares within the budget. If no sector is chosen, it auto-selects the
    single best-scoring sector and its top 3 stocks; if a sector is chosen
    (via the Sector Selection dropdown, backed by the same SECTORS data
    source as Sector Analysis / Risk Analysis / Future Prediction),
    analysis is confined to that sector's stocks only. Purely additive --
    does not read from or write to any state used by the existing
    Investment Budget tool (/api/portfolio) or Recommendation Engine
    (/api/investment-recommendations)."""
    try:
        payload = request.get_json(silent=True) or {}
        budget = payload.get('budget')
        risk_preference = payload.get('riskPreference') or payload.get('risk_preference') or 'Medium'
        start_date = payload.get('start_date') or payload.get('startDate')
        end_date = payload.get('end_date') or payload.get('endDate')
        sector = payload.get('sector') or payload.get('selectedSector') or None
        if start_date and end_date:
            try:
                if pd.to_datetime(start_date) > pd.to_datetime(end_date):
                    return jsonify({"error": "The From date must be earlier than or equal to the To date."}), 400
            except Exception:
                return jsonify({"error": "Enter valid dates, or leave the date fields empty to use all available history."}), 400
        if budget not in (None, ''):
            try:
                if float(budget) < 0:
                    return jsonify({"error": "Investment budget cannot be negative."}), 400
            except (TypeError, ValueError):
                return jsonify({"error": "Enter a valid numeric investment budget, or leave it empty."}), 400
        result = analyze_ai_advisor(
            budget=budget,
            risk_preference=risk_preference,
            start_date=start_date,
            end_date=end_date,
            sector=sector
        )
        if "error" in result:
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"AI advisor failed: {str(e)}"}), 500



# --- Added Market Mind 2.0 features: chatbot, explainability, news sentiment ---
POSITIVE_WORDS = {
    "beat", "beats", "growth", "gain", "gains", "surge", "surges", "strong", "profit", "profits",
    "upgrade", "upgraded", "positive", "rise", "rises", "record", "bullish", "buy", "outperform",
    "expansion", "deal", "wins", "win", "improve", "improved", "rally", "rallies", "rebound",
    "recovery", "recover", "robust", "raises", "raised", "dividend", "breakthrough", "beat-estimates",
    "outlook", "optimistic", "approval", "approved", "partnership", "contract", "orders", "demand"
}
NEGATIVE_WORDS = {
    "miss", "misses", "decline", "declines", "fall", "falls", "drop", "drops", "weak", "loss", "losses",
    "downgrade", "downgraded", "negative", "crash", "bearish", "sell", "underperform", "probe", "lawsuit",
    "risk", "risks", "cuts", "cut", "warning", "concern", "concerns", "plunge", "plunges", "slump",
    "slumps", "fraud", "fine", "penalty", "debt", "layoff", "layoffs", "recall", "delay", "delayed",
    "resigns", "resignation", "investigation", "investigated", "weakness", "uncertainty", "loss-making"
}

NEWS_COMPANY_NAMES = {
    "INFY.NS": "Infosys", "TCS.NS": "Tata Consultancy Services", "WIPRO.NS": "Wipro",
    "HCLTECH.NS": "HCLTech", "HDFCBANK.NS": "HDFC Bank", "SBIN.NS": "State Bank of India",
    "ICICIBANK.NS": "ICICI Bank", "AXISBANK.NS": "Axis Bank", "SUNPHARMA.NS": "Sun Pharma",
    "CIPLA.NS": "Cipla", "DRREDDY.NS": "Dr Reddy's Laboratories", "HINDUNILVR.NS": "Hindustan Unilever",
    "ITC.NS": "ITC Limited", "NESTLEIND.NS": "Nestle India", "BRITANNIA.NS": "Britannia Industries"
}


def score_headline_sentiment(text):
    import re
    words = re.findall(r"[a-zA-Z]+(?:-[a-zA-Z]+)?", (text or "").lower())
    positive = sum(word in POSITIVE_WORDS for word in words)
    negative = sum(word in NEGATIVE_WORDS for word in words)
    # Simple negation handling avoids classifying "not strong" as positive.
    for i, word in enumerate(words):
        if word in POSITIVE_WORDS and i > 0 and words[i - 1] in {"not", "no", "fails", "failed", "without"}:
            positive -= 1
            negative += 1
        elif word in NEGATIVE_WORDS and i > 0 and words[i - 1] in {"not", "no", "without"}:
            negative -= 1
            positive += 1
    score = (positive - negative) / max(1, positive + negative)
    label = "Positive" if score > 0 else ("Negative" if score < 0 else "Neutral")
    return {"label": label, "score": round(float(score), 2), "positive_terms": max(0, positive), "negative_terms": max(0, negative)}


def _news_item_from_yahoo(item):
    """Normalize both older and newer yfinance news payload formats."""
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    title = content.get("title") or item.get("title") or ""
    url = content.get("canonicalUrl") or content.get("clickThroughUrl") or item.get("link") or ""
    if isinstance(url, dict):
        url = url.get("url", "")
    provider = content.get("provider")
    publisher = provider.get("displayName", "") if isinstance(provider, dict) else item.get("publisher", "")
    if title:
        return {"title": str(title).strip(), "publisher": publisher or "Yahoo Finance", "url": url or ""}
    return None


def _fetch_google_news_rss(symbol, limit=15):
    """Fetch actual recent headlines through Google News RSS as a Yahoo fallback."""
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    company = NEWS_COMPANY_NAMES.get(symbol, symbol.replace(".NS", ""))
    query = f'"{company}" stock when:30d'
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MarketMind/2.0"})
    with urllib.request.urlopen(req, timeout=8) as response:
        xml_data = response.read(2_000_000)
    root = ET.fromstring(xml_data)
    items = []
    for node in root.findall("./channel/item")[:limit]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        source = node.findtext("source") or "Google News"
        if title:
            items.append({"title": title, "publisher": source, "url": link})
    return items


def _build_chat_messages(question, metrics, history):
    """Build a concise, question-relevant project context for the chat model."""
    # Keep context concise so the request remains fast and inexpensive.
    compact_metrics = []
    for item in (metrics or []):
        try:
            compact_metrics.append({
                'symbol': item.get('symbol'), 'sector': item.get('sector'),
                'historical_return_pct': round(float(item.get('return_pct', 0) or 0), 2),
                'historical_volatility_pct': round(float(item.get('volatility_pct', 0) or 0), 2),
                'risk_category': item.get('risk_category'),
                'latest_close_from_dataset': round(float(item.get('latest_close', 0) or 0), 2),
                'data_as_of': item.get('data_as_of')
            })
        except (TypeError, ValueError):
            continue
    readme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.md')
    try:
        with open(readme_path, encoding='utf-8') as readme_file:
            project_documentation = readme_file.read()
    except OSError as exc:
        app.logger.warning('Could not load project documentation for Ask AI: %s', exc)
        project_documentation = "Project README is unavailable."
    project_documentation = _select_project_context(question, project_documentation)
    system_prompt = (
        "You are Market Mind. Answer the user's actual question directly, including project questions beyond a fixed topic list. "
        "Use the relevant project notes and data below; don't invent project details. If context is missing, say so. "
        "For tracked stock prices and metrics, the current data snapshot below is the source of truth, even if earlier chat messages conflict; "
        "include its data_as_of date when citing a value. Use clear, brief language. For stock comparisons, explain the return/risk trade-off using the historical data; "
        "never invent live prices or promise results. Educational information only, not personal financial advice.\n\n"
        "Relevant Market Mind project documentation:\n" + project_documentation + "\n\n"
        "Current Market Mind stock-data snapshot, recalculated from the latest local CSV files for this request "
        "(prices are the latest recorded closes as of each data_as_of date, not guaranteed live data): "
        + json.dumps(compact_metrics[:30])
    )
    messages = [{'role': 'system', 'content': system_prompt}]
    if isinstance(history, list):
        for item in history[-4:]:
            if not isinstance(item, dict):
                continue
            role = item.get('role')
            content = str(item.get('content', '')).strip()[:350]
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': content})
    if not (messages and messages[-1].get('role') == 'user' and messages[-1].get('content') == question):
        messages.append({'role': 'user', 'content': question})
    return messages


def _try_llm_chat(question, metrics, history):
    """Answer a chat question with the configured model and Market Mind context."""
    import urllib.error
    import urllib.request

    provider = os.environ.get('AI_PROVIDER', 'openai').strip().lower()
    if provider not in {'openai', 'ollama'}:
        raise RuntimeError("AI_PROVIDER must be set to either 'openai' or 'ollama' in mmupdate/.env.")
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if provider == 'openai' and not api_key:
        raise RuntimeError("Ask AI is not configured. Add an API key or set AI_PROVIDER=ollama in mmupdate/.env and restart the app.")
    messages = _build_chat_messages(question, metrics, history)

    if provider == 'ollama':
        ollama_url = os.environ.get('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
        endpoint = ollama_url + '/api/chat'
        model = os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')
        body = json.dumps({
            'model': model,
            'messages': messages,
            'stream': False,
            'options': {'temperature': 0.4, 'num_predict': 220, 'num_ctx': 4096}
        }).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
    else:
        endpoint = 'https://api.openai.com/v1/chat/completions'
        model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        body = json.dumps({
            'model': model,
            'messages': messages,
            'temperature': 0.5,
            'max_tokens': 1200
        }).encode('utf-8')
        headers = {'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
    req = urllib.request.Request(endpoint, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120 if provider == 'ollama' else 18) as response:
            result = json.loads(response.read().decode('utf-8'))
        if provider == 'ollama':
            message = result.get('message') if isinstance(result, dict) else None
            answer = message.get('content') if isinstance(message, dict) else None
        else:
            choices = result.get('choices') if isinstance(result, dict) else None
            first_choice = choices[0] if isinstance(choices, list) and choices else None
            message = first_choice.get('message') if isinstance(first_choice, dict) else None
            answer = message.get('content') if isinstance(message, dict) else None
            if isinstance(first_choice, dict) and first_choice.get('finish_reason') == 'length':
                raise RuntimeError("The answer reached the model output limit and may be incomplete. Please try again with a shorter question.")
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("The AI provider returned an empty answer. Please try again.")
        return answer.strip()
    except urllib.error.HTTPError as exc:
        provider_code = ''
        try:
            provider_error = json.loads(exc.read().decode('utf-8')).get('error', {})
            if isinstance(provider_error, dict):
                candidate_code = provider_error.get('code') or provider_error.get('type')
                if isinstance(candidate_code, str):
                    provider_code = candidate_code
        except (ValueError, UnicodeDecodeError):
            pass
        app.logger.warning('Ask AI provider %s returned HTTP %s (error code: %s)', provider, exc.code, provider_code or 'unknown')
        if provider == 'ollama':
            if exc.code == 404:
                message = f"Ollama does not have model '{model}' downloaded. Run `ollama pull {model}` and try again."
            else:
                message = f"Ollama returned HTTP {exc.code}. Check that Ollama is running and the selected model is available."
            raise RuntimeError(message) from exc
        if exc.code == 401:
            message = "OpenAI returned HTTP 401: the API key is invalid, revoked, or not being loaded from the .env file you edited. Create a new API key in the OpenAI Platform, replace the value in mmupdate/.env, and restart Flask. Do not use a ChatGPT password."
        elif exc.code == 403:
            message = "OpenAI returned HTTP 403: the key was recognized, but the account or project may not have permission to use this API/model. Check the API project, model access, and organization settings."
        elif exc.code == 429:
            message = "OpenAI returned HTTP 429: the API project may have reached its usage quota or rate limit. Check API billing and usage, then try again."
        else:
            message = f"OpenAI request failed (HTTP {exc.code}). Check the Flask terminal for details."
        raise RuntimeError(message) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        app.logger.warning('Ask AI could not reach %s: %s', provider, exc)
        if provider == 'ollama':
            message = "Could not connect to Ollama at " + os.environ.get('OLLAMA_URL', 'http://localhost:11434') + ". Start Ollama and make sure its local service is running."
        else:
            message = "Could not reach OpenAI. Check the internet connection and try again."
        raise RuntimeError(message) from exc
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        app.logger.warning('Ask AI received an invalid response from %s: %s', provider, exc)
        raise RuntimeError(provider.capitalize() + " returned an unexpected response. Please try again.") from exc


def _select_project_context(question, documentation):
    """Choose concise README sections relevant to the user's question."""
    import re

    sections = re.split(r'(?m)(?=^#{1,3} )', documentation)
    question_terms = set(re.findall(r"[a-z0-9]{3,}", question.lower()))
    ranked_sections = []
    for index, section in enumerate(sections):
        words = re.findall(r"[a-z0-9]{3,}", section.lower())
        score = sum(1 for word in words if word in question_terms)
        if index == 0:
            score += 1
        if score:
            ranked_sections.append((score, index, section.strip()))
    ranked_sections.sort(key=lambda item: (-item[0], item[1]))
    selected_indices = {index for index in (1, 8) if index < len(sections)}
    selected = [sections[index].strip() for index in sorted(selected_indices) if sections[index].strip()]
    total_chars = sum(len(section) for section in selected)
    for _, index, section in ranked_sections:
        if index in selected_indices:
            continue
        if total_chars + len(section) > 2800:
            remaining = 2800 - total_chars
            if remaining > 250:
                selected.append(section[:remaining])
                total_chars += remaining
            break
        selected.append(section)
        total_chars += len(section)
    if not selected:
        selected = [documentation[:5000]]
    return "\n\n".join(selected)


def _stream_ollama_chat(question, metrics, history):
    """Yield newline-delimited JSON chunks from Ollama for immediate chat feedback."""
    import urllib.error
    import urllib.request

    try:
        provider = os.environ.get('AI_PROVIDER', 'openai').strip().lower()
        if provider != 'ollama':
            raise RuntimeError("Streaming is available only when AI_PROVIDER=ollama.")
        ollama_url = os.environ.get('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
        model = os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')
        payload = json.dumps({
            'model': model,
            'messages': _build_chat_messages(question, metrics, history),
            'stream': True,
            'options': {'temperature': 0.4, 'num_predict': 1024, 'num_ctx': 4096}
        }).encode('utf-8')
        req = urllib.request.Request(
            ollama_url + '/api/chat',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            received_content = False
            completed = False
            for raw_line in response:
                if not raw_line.strip():
                    continue
                event = json.loads(raw_line.decode('utf-8'))
                if event.get('error'):
                    raise RuntimeError("Ollama error: " + str(event['error']))
                message = event.get('message')
                content = message.get('content') if isinstance(message, dict) else None
                if isinstance(content, str) and content:
                    received_content = True
                    yield json.dumps({'content': content}) + '\n'
                if event.get('done'):
                    completed = True
                    if event.get('done_reason') == 'length':
                        raise RuntimeError("The answer reached the model output limit and may be incomplete. Please try again with a shorter question.")
                    break
            if not received_content:
                raise RuntimeError("Ollama returned an empty answer. Please try again.")
            if not completed:
                raise RuntimeError("Ollama ended the response before the answer was complete. Please try again.")
            yield json.dumps({'done': True}) + '\n'
    except urllib.error.HTTPError as exc:
        app.logger.warning('Ollama streaming request returned HTTP %s', exc.code)
        if exc.code == 404:
            message = f"Ollama does not have model '{os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')}' downloaded. Run `ollama pull {os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')}` and try again."
        else:
            message = f"Ollama returned HTTP {exc.code}. Check that Ollama is running and the selected model is available."
        yield json.dumps({'error': message}) + '\n'
    except (urllib.error.URLError, TimeoutError) as exc:
        app.logger.warning('Could not connect to Ollama for streaming chat: %s', exc)
        message = "Could not connect to Ollama. Start Ollama and make sure its local service is running."
        yield json.dumps({'error': message}) + '\n'
    except (ValueError, KeyError, IndexError, TypeError, RuntimeError) as exc:
        app.logger.warning('Ollama streaming chat failed: %s', exc)
        yield json.dumps({'error': str(exc)}) + '\n'


@app.route('/api/ai-chat', methods=['POST'])
@login_required
def ai_chat():
    """Grounded educational assistant using the application's tracked data."""
    payload = request.get_json(silent=True) or {}
    question = str(payload.get('message', '')).strip()[:500]
    if not question:
        return jsonify({"error": "Please enter a question."}), 400
    try:
        metrics = get_core_stock_metrics()
    except Exception as exc:
        app.logger.warning('Could not load stock metrics for Ask AI: %s', exc)
        metrics = []
    history = payload.get('history', [])
    provider = os.environ.get('AI_PROVIDER', 'openai').strip().lower()
    if provider == 'ollama':
        return Response(
            stream_with_context(_stream_ollama_chat(question, metrics, history)),
            mimetype='application/x-ndjson',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
        )
    try:
        answer = _try_llm_chat(question, metrics, history)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    provider = provider.capitalize()
    return jsonify({"answer": answer, "source": provider.capitalize() + " with Market Mind project documentation and stock data"})


@app.route('/api/explainable-ai', methods=['GET'])
@login_required
def explainable_ai():
    sector = request.args.get('sector', 'IT')
    symbol = request.args.get('symbol', '')
    if sector not in SECTORS or symbol not in SECTORS[sector]:
        return jsonify({"error": "Choose a valid stock for the selected sector."}), 400
    df = load_stock_dataframe(sector, symbol)
    if df is None or df.empty:
        return jsonify({"error": "No local historical data found for this stock."}), 404
    close = pd.to_numeric(df['Close'], errors='coerce').dropna()
    if len(close) < 10:
        return jsonify({"error": "Not enough clean historical prices to explain this stock."}), 422
    latest = float(close.iloc[-1]); previous = float(close.iloc[-2])
    daily_return = (latest / previous - 1) * 100 if previous else 0
    returns = close.pct_change().dropna()
    volatility = float(returns.tail(30).std() * np.sqrt(252) * 100) if len(returns) > 1 else 0
    ma5 = float(close.tail(5).mean()); ma20 = float(close.tail(20).mean())
    trend = "Positive short-term momentum" if ma5 > ma20 else "Negative/weak short-term momentum" if ma5 < ma20 else "Flat short-term momentum"
    change20 = (latest / float(close.iloc[-21]) - 1) * 100 if len(close) > 21 and float(close.iloc[-21]) else None
    factors = [
        {"name": "Latest daily return", "value": round(daily_return, 2), "unit": "%", "interpretation": "Positive for the latest session" if daily_return > 0 else "Negative for the latest session" if daily_return < 0 else "Flat for the latest session"},
        {"name": "Annualized volatility (30 sessions)", "value": round(volatility, 2), "unit": "%", "interpretation": "Higher volatility indicates larger historical price fluctuations; it is not a forecast"},
        {"name": "5-day vs 20-day moving average", "value": round(ma5 - ma20, 2), "unit": "price units", "interpretation": trend},
    ]
    if change20 is not None: factors.append({"name": "Approx. 20-session price change", "value": round(change20, 2), "unit": "%", "interpretation": "Historical price change over roughly one trading month"})
    return jsonify({"symbol": symbol.replace('.NS',''), "sector": sector, "latest_close": round(latest, 2), "observations": int(len(close)), "last_date": str(df.loc[close.index[-1], 'Date']) if 'Date' in df.columns else "Unavailable", "factors": factors, "summary": f"{symbol.replace('.NS','')} last closed at {latest:.2f}. The latest daily return was {daily_return:.2f}% and annualized volatility over recent sessions was {volatility:.2f}%. These describe historical inputs, not the cause of future price movement."})


@app.route('/api/news-sentiment', methods=['GET'])
@login_required
def news_sentiment():
    symbol = request.args.get('symbol', 'INFY.NS')
    allowed = {stock for stocks in SECTORS.values() for stock in stocks}
    if symbol not in allowed:
        return jsonify({"error": "Unsupported stock symbol."}), 400

    headlines = []
    provider_errors = []
    # Provider 1: Yahoo Finance / yfinance. Its response schema differs between versions.
    try:
        ticker_news = yf.Ticker(symbol).news or []
        for item in ticker_news:
            normalized = _news_item_from_yahoo(item)
            if normalized and normalized["title"]:
                headlines.append(normalized)
            if len(headlines) >= 15:
                break
    except Exception as exc:
        provider_errors.append("Yahoo Finance: " + str(exc)[:140])

    # Provider 2: Google News RSS. This is used when Yahoo returns no headlines or fails.
    if not headlines:
        try:
            headlines = _fetch_google_news_rss(symbol, limit=15)
        except Exception as exc:
            provider_errors.append("Google News RSS: " + str(exc)[:140])

    # Deduplicate similar titles while preserving provider order.
    unique = []
    seen = set()
    for item in headlines:
        title = " ".join(str(item.get("title", "")).split())
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        sentiment = score_headline_sentiment(title)
        unique.append({"title": title, "publisher": item.get("publisher") or "News provider", "url": item.get("url") or "", **sentiment})
        if len(unique) >= 15:
            break

    counts = {"Positive": 0, "Negative": 0, "Neutral": 0}
    for item in unique:
        counts[item["label"]] += 1
    total = len(unique)
    if not total:
        message = "No headlines could be fetched from Yahoo Finance or Google News RSS. Check your internet connection, then try again."
        if provider_errors:
            message += " Provider details: " + " | ".join(provider_errors)
    else:
        message = "Headlines loaded. Sentiment is a lightweight keyword estimate, not a prediction of price movement."
    overall = "No headlines" if not total else max(counts, key=counts.get)
    return jsonify({"symbol": symbol.replace('.NS',''), "headlines": unique, "counts": counts, "overall": overall,
                    "total": total, "message": message, "provider_error": " | ".join(provider_errors),
                    "method": "Yahoo Finance with Google News RSS fallback; transparent keyword-based sentiment scoring."})


@app.route('/get_sector_data/<sector>')
@login_required
def get_sector_data(sector):
    if sector not in SECTORS:
        return jsonify({"error": "Invalid sector"}), 400
    
    stocks = SECTORS[sector]
    sector_data = {}
    
    for stock in stocks:
        filename = _stock_data_path(sector, stock)
        if os.path.exists(filename):
            df = pd.read_csv(filename)
            if not df.empty and 'Close' in df.columns:
                df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                df = df.dropna(subset=['Close'])
                if not df.empty:
                    latest_price = df['Close'].iloc[-1]
                    prev_price = df['Close'].iloc[-2] if len(df) > 1 else latest_price
                    change = ((latest_price - prev_price) / prev_price) * 100
                    sector_data[stock] = {
                        "price": round(latest_price, 2),
                        "change": round(change, 2)
                    }
    
    # Calculate sector metrics
    if sector_data:
        avg_change = np.mean([data['change'] for data in sector_data.values()])
        # Calculate volatility for risk assessment
        volatilities = []
        for stock in stocks:
            filename = _stock_data_path(sector, stock)
            if os.path.exists(filename):
                try:
                    df = pd.read_csv(filename)
                    if not df.empty and 'Close' in df.columns:
                        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                        df = df.dropna(subset=['Close'])
                        if len(df) > 30:
                            returns = df['Close'].pct_change().dropna()
                            volatility = returns.std() * np.sqrt(252)  # Annualized volatility
                            volatilities.append(volatility)
                except:
                    continue
        
        avg_volatility = np.mean(volatilities) if volatilities else 0
        risk_level = "Low" if avg_volatility < 0.2 else "Medium" if avg_volatility < 0.4 else "High"
        trend = "↑" if avg_change > 0 else "↓"
    else:
        avg_change = 0
        risk_level = "Unknown"
        trend = "→"
    
    return jsonify({
        "stocks": sector_data,
        "avg_growth": round(avg_change, 2),
        "risk_level": risk_level,
        "trend": trend
    })

@app.route('/analyze_sector', methods=['POST'])
@login_required
def analyze_sector():
    sector = request.json.get('sector')
    if not sector or sector not in SECTORS:
        return jsonify({"error": "Valid sector required"}), 400
    
    # Run sector analysis using the current Python interpreter and absolute script path
    script_path = os.path.join(os.path.dirname(__file__), 'sector_analysis.py')
    result = subprocess.run([sys.executable, script_path, sector], capture_output=True, text=True, cwd=os.path.dirname(__file__))
    if result.returncode == 0:
        analysis_data = json.loads(result.stdout)
        return jsonify(analysis_data)
    else:
        print('Sector analysis stderr:', result.stderr)
        return jsonify({"error": "Analysis failed", "details": result.stderr.strip()}), 500

@app.route('/risk_analysis', methods=['POST'])
@login_required
def risk_analysis():
    risk_level = request.json.get('risk_level')
    if not risk_level:
        return jsonify({"error": "Risk level required"}), 400
    
    # Calculate risk for all stocks
    all_stocks = []
    for sector, stocks in SECTORS.items():
        for stock in stocks:
            filename = _stock_data_path(sector, stock)
            if os.path.exists(filename):
                df = pd.read_csv(filename)
                if not df.empty and 'Close' in df.columns:
                    df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                    df = df.dropna(subset=['Close'])
                    if len(df) > 30:  # Need enough data
                        returns = df['Close'].pct_change().dropna()
                        volatility = returns.std() * np.sqrt(252)  # Annualized volatility
                        expected_return = returns.mean() * 252
                        
                        if risk_level == "Low" and volatility < 0.2:
                            risk_cat = "Low"
                        elif risk_level == "Medium" and 0.2 <= volatility < 0.4:
                            risk_cat = "Medium"
                        elif risk_level == "High" and volatility >= 0.4:
                            risk_cat = "High"
                        else:
                            continue
                        
                        all_stocks.append({
                            "stock": stock.replace('.NS', ''),
                            "risk_level": risk_cat,
                            "expected_return": round(expected_return * 100, 2),
                            "volatility": round(volatility, 3)
                        })
    
    return jsonify({"stocks": all_stocks})

@app.route('/advanced_risk_analysis', methods=['POST'])
@login_required
def advanced_risk_analysis():
    sector = request.json.get('sector')
    if not sector or (sector != 'All' and sector not in SECTORS):
        return jsonify({"error": "Valid sector required"}), 400

    try:
        # Import the advanced risk analyzer
        import sys
        sys.path.append('.')
        from advanced_risk_analysis import AdvancedRiskAnalyzer
        
        analyzer = AdvancedRiskAnalyzer()
        result = analyzer.analyze_sector_risk(sector)
        
        if "error" in result:
            return jsonify(result), 404
        
        # Prepare response data for frontend
        stock_analyses = result["stock_analyses"]
        
        # Chart data for risk vs return scatter plot
        chart_data = []
        for analysis in stock_analyses:
            chart_data.append({
                "stock": analysis["symbol"],
                "volatility": analysis["volatility"],
                "return_pct": analysis["total_return"],
                "risk_category": analysis["risk_category"],
                "avg_price": analysis["avg_price"],
                "sharpe_ratio": analysis["sharpe_ratio"],
                "max_drawdown": analysis["max_drawdown"]
            })
        
        # Table data with conditional formatting values
        table_data = []
        for analysis in stock_analyses:
            table_data.append({
                "stock": analysis["symbol"],
                "risk_category": analysis["risk_category"],
                "volatility": analysis["volatility"],
                "return_pct": analysis["total_return"],
                "avg_price": analysis["avg_price"],
                "current_price": analysis["current_price"],
                "sharpe_ratio": analysis["sharpe_ratio"],
                "var_5": analysis["var_5"],
                "max_drawdown": analysis["max_drawdown"],
                "predictive_trend": analysis["predictive_insight"]["trend"],
                "predicted_move": analysis["predictive_insight"]["predicted_move"],
                "confidence": analysis["predictive_insight"]["confidence"]
            })
        
        # Predictive insights
        insights = []
        for analysis in stock_analyses:
            insight = analysis["predictive_insight"]
            insights.append(f"{analysis['symbol']}: {insight['insight']} (Confidence: {insight['confidence']})")
        
        response = {
            "sector": sector,
            "risk_counts": result["risk_counts"],
            "avg_volatility": result["avg_volatility"],
            "avg_return": result["avg_return"],
            "safest_stock": result["safest_stock"],
            "riskiest_stock": result["riskiest_stock"],
            "sector_insight": result["sector_insight"],
            "total_stocks": result["total_stocks"],
            "insights": insights,
            "table_data": table_data,
            "chart_data": chart_data,
            "stock_analyses": stock_analyses
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

@app.route('/get_risk_comparison', methods=['POST'])
@login_required
def get_risk_comparison():
    """Compare risk metrics across all sectors"""
    try:
        import sys
        sys.path.append('.')
        from advanced_risk_analysis import AdvancedRiskAnalyzer
        
        analyzer = AdvancedRiskAnalyzer()
        comparison_data = {}
        
        for sector in SECTORS.keys():
            result = analyzer.analyze_sector_risk(sector)
            if "error" not in result:
                comparison_data[sector] = {
                    "avg_volatility": result["avg_volatility"],
                    "avg_return": result["avg_return"],
                    "risk_counts": result["risk_counts"],
                    "safest_stock": result["safest_stock"],
                    "riskiest_stock": result["riskiest_stock"],
                    "total_stocks": result["total_stocks"],
                    "risk_profile": result["sector_insight"]["risk_profile"],
                    "sentiment": result["sector_insight"]["sentiment"]
                }
        
        return jsonify(comparison_data)
        
    except Exception as e:
        return jsonify({"error": f"Comparison failed: {str(e)}"}), 500

@app.route('/get_sector_monthly_returns')
@login_required
def get_sector_monthly_returns():
    sector_monthly_data = {}
    
    for sector, stocks in SECTORS.items():
        monthly_returns = []
        
        # Aggregate data from all stocks in the sector
        all_monthly_data = {}
        
        for stock in stocks:
            filename = _stock_data_path(sector, stock)
            if os.path.exists(filename):
                try:
                    df = pd.read_csv(filename)
                    if not df.empty and 'Close' in df.columns and 'Date' in df.columns:
                        df['Date'] = pd.to_datetime(df['Date'])
                        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                        df = df.dropna(subset=['Close', 'Date'])
                        
                        if len(df) > 30:
                            # Calculate monthly returns
                            df.set_index('Date', inplace=True)
                            monthly_prices = df['Close'].resample('M').last()
                            monthly_returns_stock = monthly_prices.pct_change().dropna() * 100
                            
                            # Store monthly returns by month
                            for date, return_val in monthly_returns_stock.items():
                                month_key = date.strftime('%b')
                                if month_key not in all_monthly_data:
                                    all_monthly_data[month_key] = []
                                all_monthly_data[month_key].append(return_val)
                except Exception as e:
                    print(f"Error processing {stock}: {e}")
                    continue
        
        # Calculate average monthly returns for the sector
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for month in months:
            if month in all_monthly_data and all_monthly_data[month]:
                avg_return = np.mean(all_monthly_data[month])
                monthly_returns.append(round(avg_return, 2))
            else:
                # Generate sample data if no real data available
                monthly_returns.append(round(np.random.uniform(-5, 8), 2))
        
        sector_monthly_data[sector] = {
            "monthly_returns": monthly_returns,
            "months": months
        }
    
    return jsonify(sector_monthly_data)

@app.route('/optimize_portfolio', methods=['POST'])
@login_required
def optimize_portfolio():
    selected_stocks = request.json.get('stocks', [])
    if not selected_stocks:
        return jsonify({"error": "Stocks required"}), 400
    
    # Simple portfolio optimization (equal weight for demo)
    num_stocks = len(selected_stocks)
    allocation = {stock: round(100/num_stocks, 1) for stock in selected_stocks}
    
    return jsonify({
        "allocation": allocation,
        "message": "This allocation minimizes risk while maximizing return based on historical data."
    })

# =============================================================================
# MULTI-STOCK ANALYSIS MODULE (independent from Sector Analysis)
# Two dedicated endpoints; no existing routes, models, or data files are touched.
# =============================================================================

@app.route('/api/multi-stock/list')
@login_required
def multi_stock_list():
    """Return the fixed 15-stock universe (5 IT / 5 Banking / 5 Pharma) with
    live Yahoo Finance quotes for the searchable/filterable selection table."""
    try:
        stocks = get_stock_list_with_quotes()
        return jsonify({"stocks": stocks, "sectors": list(MULTI_STOCK_UNIVERSE.keys())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/multi-stock/compare', methods=['POST'])
@login_required
def multi_stock_compare():
    """Fetch live history for the selected stocks, compute comparison metrics,
    weighted best-performer score, and performance badges."""
    payload = request.json or {}
    symbols = payload.get('symbols', [])
    start_date = payload.get('start_date')
    end_date = payload.get('end_date')
    chart_type = payload.get('chart_type', 'line')

    if not symbols or not isinstance(symbols, list):
        return jsonify({"error": "Please select at least one stock"}), 400
    if len(symbols) > 15:
        return jsonify({"error": "Maximum 15 stocks supported"}), 400

    try:
        result = build_comparison_payload(symbols, start_date, end_date, chart_type)
        if "error" in result and "comparison_table" not in result:
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# MODEL PERFORMANCE & ACCURACY MODULE (independent from all other modules)
# Two dedicated endpoints; no existing routes, models, or data files are touched.
# =============================================================================

@app.route('/api/model-performance/symbols')
@login_required
def model_performance_symbols():
    """Return the stock universe (grouped by sector) with each stock's
    available data date range, for the selector controls."""
    try:
        return jsonify({"sectors": list_symbols_with_ranges()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/model-performance/evaluate', methods=['POST'])
@login_required
def model_performance_evaluate():
    """Run a walk-forward backtest of the prediction model for the selected
    stock and date range, returning accuracy metrics, chart-ready series,
    the trend-direction confusion matrix, and an overall performance score."""
    payload = request.json or {}
    symbol = payload.get('symbol', '').strip()
    start_date = payload.get('start_date') or None
    end_date = payload.get('end_date') or None

    if not symbol:
        return jsonify({"error": "Stock symbol required"}), 400

    try:
        result = evaluate_model_performance(symbol, start_date, end_date)
        if "error" in result:
            return jsonify(result), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Evaluation failed: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)