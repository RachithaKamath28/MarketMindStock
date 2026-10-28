import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.linear_model import LinearRegression

DATA_FOLDER = "data"
DEFAULT_SECTORS = ["IT", "Banking", "Pharma", "FMCG"]


def load_sector_data():
    sector_data = {}
    csv_files = sorted(glob.glob(os.path.join(DATA_FOLDER, "*.csv")))

    for file_path in csv_files:
        file_name = Path(file_path).name
        if "_" not in file_name:
            continue

        sector_name, stock_code = file_name.split("_", 1)
        stock_code = stock_code.replace(".csv", "")

        df = pd.read_csv(file_path)
        if "Date" not in df.columns or "Close" not in df.columns:
            continue

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

        for col in ["Open", "High", "Low", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                df[col] = np.nan

        df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
        if df.empty:
            continue

        sector_data.setdefault(sector_name, {})[stock_code] = df

    return sector_data


def calculate_stock_metrics(df):
    close_series = df["Close"].dropna()
    if close_series.empty or len(close_series) < 2:
        return {
            "Percent Return": np.nan,
            "Average Price": np.nan,
            "Volatility": np.nan,
            "Latest Close": np.nan,
            "Start Date": pd.NaT,
            "End Date": pd.NaT,
            "Average Daily Return": np.nan,
            "Return Volatility": np.nan,
        }

    pct_return = (close_series.iloc[-1] / close_series.iloc[0] - 1) * 100
    avg_price = close_series.mean()
    daily_returns = close_series.pct_change().dropna()
    volatility = daily_returns.std()
    avg_daily_return = daily_returns.mean() * 100

    return {
        "Percent Return": pct_return,
        "Average Price": avg_price,
        "Volatility": volatility,
        "Latest Close": close_series.iloc[-1],
        "Start Date": df["Date"].iloc[0],
        "End Date": df["Date"].iloc[-1],
        "Average Daily Return": avg_daily_return,
        "Return Volatility": volatility,
        "Daily Return Count": len(daily_returns),
    }


def classify_risk(volatility, thresholds):
    low_threshold, high_threshold = thresholds
    if pd.isna(volatility):
        return "Unknown"
    if volatility <= low_threshold:
        return "Low"
    if volatility <= high_threshold:
        return "Medium"
    return "High"


def compute_thresholds(volatilities):
    valid = [v for v in volatilities if not pd.isna(v)]
    if not valid:
        return (np.nan, np.nan)

    low = float(np.percentile(valid, 33))
    high = float(np.percentile(valid, 66))
    if low == high:
        low = float(np.quantile(valid, 0.25))
        high = float(np.quantile(valid, 0.75))
    return low, high


def build_predictive_insight(df):
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
    if len(df) < 10:
        return None

    window = df.tail(60)
    x = np.arange(len(window)).reshape(-1, 1)
    y = np.log(window["Close"].values).reshape(-1, 1)

    model = LinearRegression()
    model.fit(x, y)
    slope = float(model.coef_[0][0])
    predicted_move = (np.exp(slope * 7) - 1) * 100
    trend = "upward" if slope > 0 else "downward"
    confidence = "higher" if abs(slope) > 0.0008 else "moderate"

    return {
        "trend": trend,
        "predicted_move": predicted_move,
        "confidence": confidence,
        "slope": slope,
    }


def filter_data_by_date(df, start_date, end_date):
    return df[(df["Date"] >= pd.to_datetime(start_date)) & (df["Date"] <= pd.to_datetime(end_date))].sort_values("Date")


def format_metric(value, precision=2, prefix="", suffix=""):
    if pd.isna(value):
        return "N/A"
    return f"{prefix}{value:.{precision}f}{suffix}"


def main():
    st.set_page_config(page_title="Risk Analysis Dashboard", layout="wide")
    st.title("Advanced Sector Risk Analysis")
    st.markdown(
        "Use historical price data to evaluate daily-return volatility, classify stocks by risk tier, "
        "and view predictive insights that contextualize potential short-term behavior."
    )

    sector_data = load_sector_data()
    available_sectors = sorted(sector_data.keys() or DEFAULT_SECTORS)

    if not sector_data:
        st.warning(
            "No stock data found in the data folder. Add CSV files under `data/` with the format `Sector_Stock.csv` and refresh."
        )
        return

    with st.sidebar:
        st.header("Risk Dashboard Filters")
        selected_sector = st.selectbox("Select sector", available_sectors)
        available_stocks = sorted(sector_data.get(selected_sector, {}).keys())
        selected_stocks = st.multiselect(
            "Choose stocks for risk comparison",
            options=available_stocks,
            default=available_stocks,
        )

        if not selected_stocks:
            st.warning("Select at least one stock to analyze risk and predictive trends.")
            return

        sector_dates = [sector_data[selected_sector][stock]["Date"] for stock in selected_stocks]
        min_date = min(series.min() for series in sector_dates)
        max_date = max(series.max() for series in sector_dates)

        start_date, end_date = st.date_input(
            "Select historical window",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        if start_date > end_date:
            st.error("Start date must be before end date.")
            return

        chart_type = st.radio("Trend chart style", ["Actual Price", "Normalized Price"], index=1)

    filtered_data = {
        stock: filter_data_by_date(sector_data[selected_sector][stock], start_date, end_date)
        for stock in selected_stocks
    }
    metrics = {stock: calculate_stock_metrics(df) for stock, df in filtered_data.items()}
    metrics_df = pd.DataFrame(metrics).T

    if metrics_df.empty or metrics_df["Percent Return"].dropna().empty:
        st.error("No valid data available for the selected stocks and date range.")
        return

    low_threshold, high_threshold = compute_thresholds(metrics_df["Volatility"].tolist())
    metrics_df["Risk Category"] = metrics_df["Volatility"].apply(lambda v: classify_risk(v, (low_threshold, high_threshold)))
    metrics_df["Risk Category"] = metrics_df["Risk Category"].fillna("Unknown")

    counts = metrics_df["Risk Category"].value_counts().reindex(["Low", "Medium", "High", "Unknown"], fill_value=0)
    safest_stock = metrics_df["Volatility"].idxmin()
    riskiest_stock = metrics_df["Volatility"].idxmax()

    st.subheader(f"{selected_sector} Risk Summary")
    high_level_cols = st.columns(4)
    high_level_cols[0].metric("Low Risk", counts["Low"])
    high_level_cols[1].metric("Medium Risk", counts["Medium"])
    high_level_cols[2].metric("High Risk", counts["High"])
    high_level_cols[3].metric("Average Volatility", format_metric(metrics_df["Volatility"].mean(), 4))

    highlight_cols = st.columns(2)
    highlight_cols[0].metric(
        "Safest Stock",
        safest_stock,
        f"Volatility {format_metric(metrics_df.loc[safest_stock, 'Volatility'], 4)}",
    )
    highlight_cols[1].metric(
        "Riskiest Stock",
        riskiest_stock,
        f"Volatility {format_metric(metrics_df.loc[riskiest_stock, 'Volatility'], 4)}",
    )

    summary_text = (
        f"The selected sector contains {len(selected_stocks)} stocks. "
        f"Volatility thresholds for this selection are: low ≤ {low_threshold:.4f}, medium ≤ {high_threshold:.4f}. "
        f"Lower volatility values indicate more stable, safer stocks, while higher volatility implies greater uncertainty."
    )
    st.info(summary_text)

    with st.expander("Predictive Risk Insights", expanded=True):
        insight_rows = []
        for stock, df in filtered_data.items():
            insight = build_predictive_insight(df)
            if insight:
                trend_phrase = (
                    f"{stock} is showing a {insight['trend']} pattern with an estimated {insight['predicted_move']:.2f}% move over the next 7 days. "
                    f"Confidence: {insight['confidence']} based on the last 60 trading days."
                )
            else:
                trend_phrase = f"Not enough recent history for predictive insight on {stock}."
            insight_rows.append(trend_phrase)
        for row in insight_rows:
            st.write(f"- {row}")

    st.markdown("---")
    st.subheader("Interactive Risk vs Return Analysis")

    plot_df = metrics_df.reset_index().rename(columns={"index": "Stock"})
    fig_3d = px.scatter_3d(
        plot_df,
        x="Volatility",
        y="Percent Return",
        z="Average Price",
        color="Risk Category",
        symbol="Risk Category",
        hover_name="Stock",
        size="Volatility",
        title="3D Risk vs Return vs Price",
        labels={
            "Volatility": "Daily Volatility",
            "Percent Return": "Total Return (%)",
            "Average Price": "Average Price (₹)",
        },
    )
    fig_3d.update_layout(scene=dict(xaxis=dict(title="Volatility"), yaxis=dict(title="Return (%)"), zaxis=dict(title="Average Price")))
    st.plotly_chart(fig_3d, use_container_width=True)

    risk_return_fig = px.scatter(
        plot_df,
        x="Volatility",
        y="Percent Return",
        color="Risk Category",
        size="Average Price",
        hover_name="Stock",
        title="Risk vs Return Scatter",
        labels={"Volatility": "Daily Volatility", "Percent Return": "Return (%)"},
    )
    st.plotly_chart(risk_return_fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Sector Comparison Table")
    metric_display = metrics_df.copy()
    metric_display["Start Date"] = metric_display["Start Date"].dt.date
    metric_display["End Date"] = metric_display["End Date"].dt.date
    styled_table = (
        metric_display.style
        .format({
            "Percent Return": "{:.2f}%",
            "Average Price": "₹{:.2f}",
            "Volatility": "{:.4f}",
            "Latest Close": "₹{:.2f}",
            "Average Daily Return": "{:.2f}%",
        })
        .background_gradient(cmap="Blues", subset=["Average Price"])
        .background_gradient(cmap="RdYlGn", subset=["Percent Return"])
        .background_gradient(cmap="YlOrRd", subset=["Volatility"])
    )
    st.dataframe(styled_table, use_container_width=True)

    st.markdown("---")
    st.subheader("Detailed Stock Profiles")
    for stock, df in filtered_data.items():
        with st.expander(f"{stock} details", expanded=False):
            if df.empty:
                st.warning(f"No data available for {stock} in the selected range.")
                continue

            stock_metrics = metrics[stock]
            detail_cols = st.columns(4)
            detail_cols[0].metric("Total Return", format_metric(stock_metrics["Percent Return"], 2, suffix="%"))
            detail_cols[1].metric("Volatility", format_metric(stock_metrics["Volatility"], 4))
            detail_cols[2].metric("Daily Return", format_metric(stock_metrics["Average Daily Return"], 2, suffix="%"))
            detail_cols[3].metric("Latest Close", format_metric(stock_metrics["Latest Close"], 2, prefix="₹"))

            chart_df = df.copy()
            if chart_type == "Normalized Price":
                chart_df["Close"] = chart_df["Close"] / chart_df["Close"].iloc[0]

            mini_fig = px.line(
                chart_df,
                x="Date",
                y="Close",
                title=f"{stock} Price Trend",
                labels={"Close": chart_type, "Date": "Date"},
            )
            st.plotly_chart(mini_fig, use_container_width=True)

            insight = build_predictive_insight(df)
            if insight:
                st.write(
                    f"**Outlook:** {stock} is trending {insight['trend']} with an estimated "
                    f"{insight['predicted_move']:.2f}% move over the next 7 trading days."
                )
            else:
                st.write("**Outlook:** Not enough recent history for a confident predictive signal.")

            st.write(
                f"Period: {df['Date'].min().date()} to {df['Date'].max().date()}  \n"
                f"Average Price: {format_metric(stock_metrics['Average Price'], 2, prefix='₹')}  \n"
                f"Volatility: {format_metric(stock_metrics['Volatility'], 4)}  \n"
                f"Risk Category: {metrics_df.loc[stock, 'Risk Category']}"
            )

    st.markdown("---")
    st.caption(
        "This dashboard integrates volatility-based risk classification with predictive market signals, providing a balanced view for sector investment decisions."
    )


if __name__ == "__main__":
    main()
