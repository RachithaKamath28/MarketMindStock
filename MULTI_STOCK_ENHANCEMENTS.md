# Multi-Stock Analysis — Enhancement Documentation

This document describes the changes made to the **Multi-Stock Analysis** module only.
No other module (Sector Analysis, LSTM prediction, Advanced Risk Analysis), route,
data file, database, or theme file was modified. All backend calculations continue
to use real, live-fetched data (Yahoo Finance via `yfinance`) — nothing here is
mocked, hardcoded, or simulated.

## Files touched

| File | Nature of change |
|---|---|
| `multi_stock_analysis.py` | Additive only — new functions and new fields appended to the existing response payload. No existing function signature, return key, or behavior was removed. |
| `templates/index.html` | Removed sector-filter/search controls from the Multi-Stock Analysis section only. Added a "Select All 15 / Clear Selection" control pair. |
| `static/script.js` | Removed search/sector-filter JS logic for this module; added Select All / Clear handlers, a 2-stock minimum for comparisons, and rendering for the new metrics (Beta, Sharpe Ratio, Growth, Predicted Price, best-performer explanation). |
| `static/style.css` | Replaced now-unused filter-row styles with styles for the new controls, wider comparison table, prediction deltas, and explanation text. Existing glassmorphism/3D theme variables (`--bg-panel`, `--border`, `--pos`, `--neg`, `--amber`, etc.) are reused as-is. |
| `app.py` | **No changes required.** The existing `/api/multi-stock/list` and `/api/multi-stock/compare` routes already pass the full `multi_stock_analysis.py` payload through to the frontend, so the new fields flow automatically. |

## 1. Removed: sector filters & symbol search

**What changed:** The "All / IT / Banking / Pharma" sector dropdown and the
"Search by Symbol" text input have been removed from the Multi-Stock Analysis
page.

**Why:** These controls existed to narrow a long list down for browsing. Per
the new requirement, the full 15-stock universe is always shown at once, so
filtering is no longer needed — removing it eliminates a click and reduces
visual clutter, in line with the "streamlined" goal.

**Impact on the user:** Analysts see all 15 stocks immediately on page load,
grouped by sector (IT → Banking → Pharma) exactly as returned by the existing
`get_stock_list_with_quotes()` backend function (unchanged). A **"Select All
15"** and **"Clear Selection"** button pair was added so users can still
quickly select the entire universe or start over, which is a faster path to
comparison than search/filter ever was.

## 2. All 15 stocks visible by default, any combination selectable

**What changed:** No frontend code change was needed to the selection
mechanism itself — the checkbox-per-row pattern already supported
cross-sector selection. Removing the filter simply means every row (and its
checkbox) is always present, so a user can already tick, e.g., `TCS`
(IT) + `HDFCBANK` (Banking) + `CIPLA` (Pharma) in one pass.

**What changed for validation:** The comparison now requires **at least two**
selected stocks before it runs (previously a single stock alone triggered a
"comparison"). This matches the explicit "select and compare any two or more
stocks" requirement and avoids a meaningless single-stock "comparison" view.

## 3. New comparison metrics (real backend data, no ML model changes)

All of the following are computed inside `multi_stock_analysis.py`, using the
same `yfinance`-sourced OHLCV history already fetched for the existing return/
volatility/volume metrics. No existing metric, weight, or scoring formula was
altered — these are pure additions.

| Metric | Method | Notes |
|---|---|---|
| **Beta** | `Cov(stock, NIFTY 50) / Var(NIFTY 50)`, computed on daily returns aligned by date over the selected range. | NIFTY 50 (`^NSEI`) is fetched once per comparison request (not per stock) and reused for every selected stock's Beta — same live-data approach as the rest of the module. |
| **Sharpe Ratio** | `(annualized mean return − risk-free rate) / annualized volatility`. | Risk-free rate is a documented, configurable assumption (`RISK_FREE_RATE_ANNUAL = 6.5%`, approximating Indian 10-year G-Sec yields) and is returned in the API response (`risk_free_rate_used`) for transparency. |
| **Growth (CAGR)** | `((end_price / start_price) ^ (365 / days_in_range) − 1) × 100`. | Annualizes the return over the *exact* selected date range, rather than the un-annualized total return already shown. |
| **Predicted Price** | Linear regression (`numpy.polyfit`, degree 1) fit over the selected range's closing prices, extrapolated 10 trading days forward. | This is a transparent statistical trend estimate, not a new ML model — it is explicitly labeled in the UI as a *recommendation/estimate*, with a disclaimer, per the evidence-handling requirement that speculative output be framed as such rather than asserted as fact. |

These are added to both the per-stock **comparison table** and the
**Best Performer summary card**, and update automatically whenever the
selection or date range changes, using the existing `/api/multi-stock/compare`
POST flow (no new endpoint was introduced).

## 4. Automatic best-performer identification with a generated explanation

**What existed already:** A weighted score (`return`, `risk`, `volume`,
`consistency` — weights unchanged) already picked a "Best Performer" and
attached badges (Best Return, Lowest Risk, Highest Volume, Most Consistent).

**What was added:** A new `_build_best_performer_explanation()` function
composes a short, plain-language paragraph *entirely from the numbers already
computed for that stock* — its return vs. the average of the other selected
stocks, its risk category and volatility vs. the group average, its CAGR, its
Sharpe Ratio (with a compensates/doesn't-compensate framing relative to the
risk-free rate), its Beta (with an in-line/amplifies/dampens framing relative
to the market), and a closing line noting the score reflects a combination of
factors, not return alone. Nothing here is hardcoded per stock — swap the
selection or date range and the explanation text regenerates from the new
figures.

**Example (illustrative, will vary per real request):**

> *"HDFCBANK posted a +18.42% return over the selected period (vs. an average
> of +11.05% for the other selected stocks), with low risk (16.30% annualized
> volatility), which is lower than the 22.80% average for the rest of the
> selection. Its annualized growth (CAGR) over this window was +21.90%. A
> Sharpe Ratio of 1.35 indicates its return adequately compensates for the risk
> taken, relative to a 6.5% risk-free benchmark. With a Beta of 0.94, it moves
> roughly in line with the broader NIFTY 50 market. Combined, these factors
> produced the highest weighted score (78.3/100) in this comparison — weighing
> return, risk, liquidity and consistency together, not return alone."*

## 5. Dynamic updates preserved

- Changing the stock selection, the chart type (Line / Bar / Candlestick), or
  the date range all still trigger the same `/api/multi-stock/compare` request
  used before — every table cell, the summary card, and now a **dashed
  forecast segment** on the line chart (showing each stock's 10-day predicted
  price visually) all update together.
- All Plotly chart theming (transparent backgrounds, existing color palette,
  grid colors, legend placement) is untouched — the forecast segment reuses
  each stock's existing trace color, rendered as a dotted line so it's visibly
  distinct from historical data.

## 6. UI/UX and theme integrity

- No CSS variables, layout containers (`chart-container-3d`, `summary-card`,
  glassmorphism panel classes), animations, or responsiveness rules were
  altered — only new, additive classes were introduced (`multi-stock-select-btn`,
  `multi-stock-table-scroll`, `multi-stock-disclaimer`, `multi-stock-pred-delta`,
  `multi-stock-summary-explanation`), all built from the same design tokens
  already used throughout the module (e.g., `var(--pos)`, `var(--neg)`,
  `var(--amber)`, `var(--text-dim)`).
- The comparison table now has more columns (Growth, Beta, Sharpe, Predicted
  Price), so it is wrapped in a horizontally scrollable container on narrower
  viewports to preserve responsiveness without compressing the existing
  columns.

## 7. What was explicitly NOT changed

- `sector_analysis.py`, `sector_prediction.py`, `lstm_sector.py`,
  `advanced_risk_analysis.py` — untouched.
- The 15-stock universe, sector groupings, and existing weighted-score formula
  (`return` 45% / `risk` 30% / `volume` 15% / `consistency` 10%) — untouched.
- The `/api/multi-stock/list` and `/api/multi-stock/compare` route definitions
  in `app.py` — untouched (the existing pass-through design meant no route
  changes were necessary to expose the new fields).
- Login/auth flow, other sidebar pages, and all other CSS/JS outside the
  Multi-Stock module — untouched.

## Caveats & recommendations (flagged as such, not asserted as fact)

- **Predicted Price** is a simple linear-trend extrapolation over the selected
  date range, intended as a directional, short-horizon estimate to complement
  return/risk/volatility — not a substitute for the LSTM-based prediction used
  elsewhere in the app (which was intentionally left untouched, per the "no ML
  model changes" constraint). Consider it a recommendation for further
  analysis, not a forecast guarantee.
- **Risk-free rate (6.5%)** is a static, documented assumption. If Treasury/
  G-Sec yields move meaningfully, this constant should be revisited — it is
  isolated in one place (`RISK_FREE_RATE_ANNUAL`) specifically so it can be
  updated without touching the calculation logic.
- **Beta** requires overlapping trading days between the stock and the NIFTY
  50 benchmark; for very short date ranges (a few days) it may return `null`
  rather than an unreliable figure — the UI displays `—` in that case rather
  than a misleading number.

---

## Addendum — Presentation Streamlining (data/graph-only view)

A follow-up, **frontend-only** update removed all narrative content from the
comparison results, per a request to keep the page focused exclusively on
visualization and tabular data.

### What changed
- The "Best Performer" summary card — including its headline, badge row, and
  the generated explanation paragraph — is **no longer rendered** on the page.
- The Predicted-Price methodology disclaimer paragraph (below the comparison
  table) was removed.
- After selecting two or more stocks, the page now shows, in order:
  1. **Historical Price Trend** — the existing Line/Bar/Candlestick toggle and
     chart (unchanged behavior).
  2. **Comparison Charts** — a responsive grid of seven dedicated bar charts,
     built from the same `comparison_table` data already in the API response:
     Predicted Price Comparison (current vs. predicted, grouped bars), Return
     Comparison, Volatility Comparison, Risk Comparison (color-coded by
     Low/Medium/High tier), Trading Volume Comparison, Beta Comparison, and
     Sharpe Ratio Comparison.
  3. **Comparison Table** — unchanged, all calculated metrics per stock
     (Price, Return, Growth/CAGR, Volatility, Risk, Beta, Sharpe, Avg Volume,
     Predicted Price, Score, Badges).

### What did NOT change
- `multi_stock_analysis.py` and `app.py` are **byte-for-byte unchanged** in
  this update — no backend logic, API contract, scoring formula, or metric
  calculation was touched. The backend still computes and returns the
  best-performer `summary` object (including `explanation`) exactly as
  before; the frontend simply no longer renders that field. This keeps the
  change reversible and fully backend-agnostic.
- The Score and Badges (Best Return, Lowest Risk, Highest Volume, Most
  Consistent) remain as **table columns** — these are compact, factual data
  tags rather than narrative text, consistent with a "tabular comparison"
  focus.
- All existing theme variables, the `chart-container-3d` glassmorphism
  panels, animations, and responsive behavior are reused for the new chart
  grid — no new visual language was introduced.

---

## Addendum — Stock Universe Alignment (15 predefined stocks)

A follow-up update corrected the Multi-Stock Analysis stock universe so it is
**identical** to the dataset already used by every other module in the
application, replacing a previously divergent 5 IT / 5 Banking / 5 Pharma
(no FMCG) list.

### What changed
`MULTI_STOCK_UNIVERSE` in `multi_stock_analysis.py` was updated from:

```python
{
    "IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "Banking": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "AUROPHARMA.NS"],
}
```

to:

```python
{
    "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "Banking": ["HDFCBANK.NS", "SBIN.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS"],
}
```

This is now **4 IT + 4 Banking + 3 Pharma + 4 FMCG = 15 stocks**, and is
byte-for-byte identical (same tickers, same sector groupings) to the
`sectors`/`SECTORS` dictionary already defined in `sector_analysis.py`,
`sector_prediction.py`, `lstm_sector.py`, `advanced_risk_analysis.py`, and
`app.py` — verified programmatically against all five files. Every module
(Dashboard, Sector Analysis, Risk Analysis, Portfolio Optimization, Stock
Prediction, and Multi-Stock Analysis) now reasons about the exact same 15
companies.

### What did NOT change
- The **method** of sourcing data for this module: Multi-Stock Analysis still
  fetches live OHLCV history and quotes via `yfinance`, exactly as before —
  only the *set of tickers* was aligned, not the data-fetching approach. The
  CSV-based modules (Sector Analysis, Risk Analysis, etc.) are untouched and
  continue reading from `data/*.csv`.
- No scoring formula, metric calculation (return, volatility, Beta, Sharpe,
  CAGR, prediction), API route, or response schema was altered. Removing 5
  tickers not shared with the rest of the app (`TECHM.NS`, `KOTAKBANK.NS`,
  `DIVISLAB.NS`, `AUROPHARMA.NS`) and adding the 4 FMCG tickers used
  elsewhere is a data-scope correction, not a logic change.
- Any two or more of the 15 stocks, in any sector combination, remain
  selectable for comparison — this behavior (checkbox selection, Select
  All / Clear buttons, 2-stock minimum) is unaffected by which 15 tickers are
  in scope.
- The UI/UX changes from the presentation-streamlining update (charts +
  table only, no narrative summary) are fully preserved.

### Minor copy updates (frontend text only, no logic)
- The Multi-Stock Analysis intro line now reads "IT, Banking, Pharma & FMCG"
  instead of "IT, Banking & Pharma", reflecting the corrected universe.
- An internal code comment in `static/script.js` was updated to match.

