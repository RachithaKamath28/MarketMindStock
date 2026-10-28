# Feature Specification: Sector Selection in Investment Advisor

**Status:** Implemented
**Owner module:** AI Investment Advisor (`aiAdvisor` page)
**Type:** Additive enhancement — no breaking changes to existing routes, pages, or data

---

## 1. Summary

The Investment Advisor (`/api/ai-advisor`) previously always auto-selected the single
best-scoring sector across all four tracked sectors before recommending stocks. This
enhancement adds a **Sector Selection dropdown** to the top of the Investment Advisor
page, consistent with the selector already used in **Sector Analysis**, **Risk
Analysis**, and **Future Prediction**. When a sector is chosen, the Advisor restricts
*all* analysis — scoring, ranking, top-pick selection, and budget-based substitution —
to that sector's stocks only. Leaving the dropdown on its default ("All Sectors")
preserves the original auto-pick-the-best-sector behavior, so no existing workflow
changes for users who don't touch the new control.

## 2. Goals / Non-Goals

**Goals**
- Let a user explicitly scope the Investment Advisor to one sector (IT, Banking,
  Pharma, FMCG).
- Reuse the exact same sector data source (`SECTORS` dict / `ANALYTICS_SECTORS`
  list in `app.py`) already powering Sector Analysis, Risk Analysis, and Future
  Prediction, so sector membership and stock symbols are always consistent
  app-wide.
- Recommend the best stock(s) in the chosen sector using the existing scoring
  pipeline (prediction, volatility, Sharpe-style ratio, confidence, risk-preference
  penalty) — no new/duplicate scoring logic.
- Auto-substitute the next best *in-sector* stock when the top pick doesn't fit the
  user's budget, rather than dropping the recommendation.
- Keep all outputs (charts, KPIs, cards) reactive: changing sector, budget, or date
  range refreshes results without a full page reload.
- Preserve the existing dark, glassmorphic, animated dashboard styling untouched.

**Non-Goals**
- No changes to the separate, pre-existing "Recommendation Engine"
  (`/api/investment-recommendations`), which already supports multi-sector
  filtering and is intentionally left alone.
- No changes to sector definitions, underlying CSV data, or the prediction model
  itself.
- No new sectors beyond the four currently supported.

## 3. UX / UI Specification

### 3.1 Placement
A new **Sector** field is added as the *first* control in the Investment Advisor's
`recommendation-controls` bar (before Budget, Risk preference, From, To), matching
the left-to-right reading order of "narrow the universe, then size the pick."

### 3.2 Control
```html
<select id="advisorSectorSelect">
  <option value="">All Sectors (auto-pick best)</option>
  <option value="IT">IT</option>
  <option value="Banking">Banking</option>
  <option value="Pharma">Pharma</option>
  <option value="FMCG">FMCG</option>
</select>
```
- Same four sector values, same option order, and same underlying data source as
  `sectorSelect` (Sector Analysis), `riskSectorSelect` (Risk Analysis), and
  `futureSectorSelect` (Future Prediction).
- Default value `""` = "All Sectors (auto-pick best)", preserving current behavior.
- Uses the existing `.recommendation-field` styling — no new CSS classes required,
  so the glassmorphism/dark theme is inherited automatically.

### 3.3 Result surface changes
- **Sector card badge**: reads "Recommended Sector" when auto-picked, or "Selected
  Sector" when the user explicitly chose one.
- **Sector reason text**: rephrased to "You selected {Sector}. Analysis below is
  scoped to {Sector} stocks only…" when locked, vs. the original comparative
  justification when auto-picked.
- **Stock grid heading**: "Top Stocks in {Sector}" when locked vs. "Top 3 Stocks in
  this Sector" when auto-picked.
- **Sector Comparison chart title**: "{Sector} Model Score" when locked (single-bar,
  since only one sector is in scope) vs. "Sector Comparison (Model Score)" when
  auto-picked (multi-bar, all four sectors).
- Stock cards, trend chart, and portfolio KPIs (invested amount, predicted value,
  expected profit) are unchanged in structure — only their underlying data changes.

### 3.4 Dynamic recalculation
Per the requirement that "all recommendations, charts, and calculations dynamically
update when the user changes the sector, investment budget, or date range":
- `change` on Sector, Risk preference, From date, and To date immediately
  re-triggers the recommendation fetch.
- `input` on Budget is debounced (600ms) to avoid firing a request per keystroke,
  then re-triggers the same fetch.
- The existing "Generate Recommendation" button remains for users who prefer an
  explicit trigger (e.g., after filling in several fields at once); it calls the
  same function.

## 4. Backend Specification

### 4.1 Data source
No new data source. Sector → stock membership continues to come from the existing
`SECTORS` dict and `ANALYTICS_SECTORS` list in `app.py`, and per-stock history from
`data/{sector}_{stock}.csv` via the existing `load_stock_dataframe()` loader — the
same source every other sector-aware module (Sector Analysis, Risk Analysis, Future
Prediction, the Recommendation Engine) already reads from.

### 4.2 API contract — `POST /api/ai-advisor`

**Request body (JSON), new field in bold:**

| Field | Type | Required | Notes |
|---|---|---|---|
| **`sector`** | string | No | One of `"IT"`, `"Banking"`, `"Pharma"`, `"FMCG"`, or `""`/omitted for auto-pick. Alias: `selectedSector`. |
| `budget` | number | No | Total investable amount. |
| `riskPreference` / `risk_preference` | string | No | `"Low"` \| `"Medium"` \| `"High"`. Defaults to `"Medium"`. |
| `start_date` / `startDate` | date string | No | Restricts the historical window used for scoring/forecasting. |
| `end_date` / `endDate` | date string | No | Restricts the historical window used for scoring/forecasting. |

**Response body, new/changed fields in bold:**

| Field | Type | Notes |
|---|---|---|
| `best_sector` | string | Now equals `sector` when one was supplied; otherwise the auto-picked sector (unchanged behavior). |
| **`selected_sector`** | string \| null | Echoes the request's `sector`, or `null` when auto-pick was used. |
| **`sector_locked`** | boolean | `true` when analysis was scoped to a single requested sector. |
| `sector_reason` | string | Rewritten to reflect user-selected vs. auto-picked framing (see §3.3). |
| `sector_comparison` | array | Contains only the requested sector's row when `sector_locked` is `true`; all four sectors' rows otherwise (unchanged). |
| `recommendations` | array | Every item's `sector` equals the requested sector when `sector_locked` is `true`. |
| `top_pick`, `portfolio_summary`, `assumptions`, `risk_preference`, `budget`, `date_range` | — | Unchanged shape. |

**Error responses (unchanged pattern, HTTP 404 with `{"error": "..."}`):**
- Invalid `sector` value → `"Invalid sector '<value>'. Choose one of: IT, Banking, Pharma, FMCG."`
- No processable stock data → existing message, unchanged.
- No sector could be scored for the selected date range → existing message, unchanged.

### 4.3 Core function — `analyze_ai_advisor()`

New optional parameter: `sector=None`.

Behavior:
1. If `sector` is falsy → `sectors_to_scan = ANALYTICS_SECTORS` (all four). Identical
   to current behavior; **fully backward compatible**.
2. If `sector` is truthy and valid → `sectors_to_scan = [sector]`. Every downstream
   step — building the stock universe, computing per-sector averages for the
   comparison table, choosing the top 3 stocks, and building the budget-substitution
   fallback pool — iterates only over `sectors_to_scan`. This guarantees recommended
   stocks, and any substitution when the budget is too small, never leave the
   selected sector.
3. If `sector` is truthy and *not* one of the four known sectors → return an error
   payload (HTTP 404), matching the existing error-handling convention used
   elsewhere in this function.

No other function in the scoring pipeline (`_score_stock_for_advisor`,
`build_stock_prediction`, `calculate_stock_metrics`, `_filter_df_by_date_range`) is
modified — the scoring methodology is identical whether or not a sector is selected,
which is what keeps this "additive."

### 4.4 Budget-insufficient substitution logic

Unchanged mechanism, now correctly scoped:
- If the top allocated pick can't be bought (budget below its per-share price at
  its allocated weight), the advisor looks for the next-best-scoring stock that
  *does* fit — from the same candidate pool used to build recommendations. Because
  that pool is now `sectors_to_scan`-scoped, a substitution offered while a sector
  is selected will always be another stock from that same sector, satisfying "If the
  budget is insufficient for the top recommended stock, automatically suggest the
  next best stock that fits within the user's budget" without silently crossing
  sector boundaries the user explicitly chose.
- If no in-sector stock fits either, the existing "no cheaper alternative" note is
  returned, prompting the user to raise the budget — this matches current behavior
  for the all-sectors case and is now consistent for the single-sector case too.

## 5. Non-Disruption / Compatibility Notes

- **No schema changes** to existing endpoints other than the two additive response
  fields (`selected_sector`, `sector_locked`) and one additive optional request
  field (`sector`) on `/api/ai-advisor`. Existing callers that don't send `sector`
  get byte-for-byte the same `best_sector`, `sector_reason` (for the auto-pick
  branch text — unchanged), `recommendations`, and chart data as before.
- **Recommendation Engine** (`/api/investment-recommendations`,
  `analyze_investment_recommendations()`) is untouched — it already had its own,
  independent multi-select sector filter and is not part of this change.
- **CSS**: no new stylesheet rules; the new `<select>` reuses `.recommendation-field`
  and `.recommendation-controls`, so it inherits the existing dark theme, spacing,
  and hover states automatically.
- **Charts**: `renderAdvisorSectorChart()` already handles a single-entry
  `sector_comparison` array gracefully (renders one bar); no chart-library changes
  were needed.
- **Global budget sync**: the existing sidebar-budget-to-advisor-budget sync
  (`advisorBudgetSyncHint`) is untouched and continues to work regardless of sector
  selection.

## 6. Test Coverage

Added to `tests/test_investment_recommendations.py`:
1. No sector supplied → auto-picks a sector from `ANALYTICS_SECTORS`;
   `sector_locked` is `False`; `selected_sector` is `None`.
2. Explicit `sector="IT"` → `best_sector == "IT"`, `sector_locked == True`, every
   recommendation and every `sector_comparison` row is IT-only.
3. Small budget with an explicit sector → every recommendation (including any
   substitution) stays within that sector.
4. Invalid sector string → response contains an `"error"` key.

All pre-existing tests continue to pass unmodified.

## 7. Rollout / Risk

- Purely additive change behind an optional parameter with a safe default — no
  feature flag needed.
- Risk is limited to the new dropdown's default value; verified it defaults to
  `""` (auto-pick), so a user who never touches it sees identical behavior to
  today.
