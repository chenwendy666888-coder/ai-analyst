# Engine API – for the app

All numbers come from these files. The app and the AI should only display or explain them.

## Files

| File | Purpose |
|---|---|
| `data.py` | Downloads Yahoo Finance data once (`python data.py`); `load_data()` reads the cached CSVs |
| `engine.py` | Liabilities, funding ratio, two-pool allocation, metrics → `build_facts()` |
| `stress.py` | Stress scenarios → `run_stress()` (used inside `build_facts`) and `custom_scenario()` |
| `compare.py` | Our portfolio vs 60/40, all stocks, all bonds → `compare_portfolios()`, `backtest_growth()` |
| `data/prices.csv`, `data/macro.csv` | Cached data (already downloaded, no internet needed) |
| `data/backtest_growth.csv` | Created by `python compare.py` |

Packages: `pandas`, `numpy`, `yfinance` (only needed to re-download data).

## 1. `build_facts()` – main input for every tab

```python
from engine import build_facts
facts = build_facts(assets=100000, annual_payment=5000, years=20)               # Option B (default)
facts_a = build_facts(assets=100000, annual_payment=5000, years=20, strategy="A")  # Option A, for comparison
```

**Strategy (team decision: B is our recommendation)**
- `strategy="B"` (default) – *Hedge the promises, grow the surplus*: bonds cover ALL promised payments (about 77%), only the surplus (about 23%) is invested for growth.
- `strategy="A"` – *Lock in the first 10 years, grow the rest*: bonds cover 10 years of payments (about 43%).
- A toggle "Option A / Option B" in the sidebar makes a good live comparison.

`matching_years` (optional, 5–20) = how many years of payments the bond pool locks in. Default: all years for B, 10 for A.

Returns a JSON-safe dict (same shape as the fake facts in TEAM_PLAN.md, plus `assumptions`):

```python
{
  "client":     {"name", "assets", "annual_payment", "years"},
  "allocation": [{"ticker", "pool", "weight", "dollars"}, ...],   # 9 ETFs, dollars sum to assets
  "metrics":    {"expected_return", "volatility", "max_drawdown", "sharpe", "funding_ratio"},
  "benchmark":  {same keys as metrics},                            # 60% VTI / 40% BND
  "stress":     [{"scenario", "portfolio_value", "funding_ratio", "obligations_met"}, ...],  # 5 scenarios (now incl. rates -2)
  "projection": {                                                   # long-term test: does the money last?
      "method", "forward_return",                                   # growth at today's rates (assumption)
      "years_lasted", "lasts_full_horizon", "ending_assets",
      "historical_years_lasted", "historical_ending_assets",        # same test at last decade's returns (reference)
      "benchmark_years_lasted", "benchmark_ending_assets",
      "path": [{"year", "payment", "assets_end"}, ...]              # one row per year, for a line chart
  },
  "assumptions": {"strategy", "strategy_name", "hedge_ratio", "liability_duration",
                  "matching_years", "pv_liabilities", "discount_rate", "inflation",
                  "risk_free", "data_end_date"}
}
```

- Ratios are decimals: `0.0698` = 6.98%. Money is whole dollars.
- `pool` is `"matching"` (bonds that cover the next 10 years of payments) or `"growth"`.
- `funding_ratio` = assets ÷ present value of promised payments. Above 1.0 = can pay.
- `hedge_ratio`: share of the fund's interest-rate risk that the bonds hedge (B about 0.75, A about 0.29). Show it as a card.
- `projection` grows the portfolio at forward-looking returns from today's rates (bonds = 10-year yield, stocks = yield + 3% premium, gold = inflation) and pays every year. The historical-return version is included for reference only. A line chart of `path` → `assets_end` shows whether the money lasts.
- Takes about a second; cache it per input (`st.cache_data`).

## 2. `custom_scenario()` – for "what if" questions in the Challenge tab

```python
from stress import custom_scenario
custom_scenario(equity_shock=-0.30)                       # stocks fall 30%
custom_scenario(rate_shock=0.02)                          # rates +2 points
custom_scenario(inflation_shock=0.03)                     # inflation +3 points for 3 years
custom_scenario(equity_shock=-0.2, rate_shock=0.02, inflation_shock=0.03,
                assets=100000, annual_payment=5000, years=20, strategy="B",
                name="My scenario")
```

Returns:

```python
{
  "scenario", "shocks": {"equity_shock", "rate_shock", "inflation_shock", "inflation_years"},
  "portfolio_value_before", "portfolio_value_after",
  "funding_ratio_before", "funding_ratio_after",
  "obligations_met",
  "holdings": [{"ticker", "before", "after", "change"}, ...]
}
```

Allowed ranges (otherwise `ValueError`): `equity_shock` −0.9 to 0.5 · `rate_shock` −0.05 to 0.05 · `inflation_shock` −0.05 to 0.10.

Suggested flow: LLM turns the question into `{"equity_shock": ..., "rate_shock": ..., "inflation_shock": ...}` → call `custom_scenario(**params)` → LLM explains the result.

## 3. `compare_portfolios()` – "Why this allocation?" table

```python
from compare import compare_portfolios
rows = compare_portfolios(assets=100000, annual_payment=5000, years=20)  # strategy="B" by default
```

List of 5 dicts: Option B (ours) first, then Option A, 60/40, all stocks, all bonds:

```python
{"portfolio", "expected_return", "volatility", "max_drawdown", "sharpe",
 "funding_ratio", "worst_funding_ratio", "scenarios_passed",   # e.g. "4 of 4"
 "survives_all_shocks",                                        # test 1: short-term shocks
 "years_lasted", "lasts_full_horizon", "ending_assets",         # test 2: does the money last?
 "passes_both_tests",
 "stress": [{"scenario", "portfolio_value", "funding_ratio", "obligations_met"}, ...]}
```

Good as a table with two tick columns ("Survives shocks", "Money lasts 20 years") plus a grouped bar chart of funding ratio per scenario, with a line at 1.0. Key message: all stocks fails a crash, 60/40 has a thin buffer, Option B passes every scenario and stays most stable when rates move.

## 4. `backtest_growth()` – line chart

```python
from compare import backtest_growth
df = backtest_growth(assets=100000)   # index = month-end date, one column per portfolio
st.line_chart(df)
```

Growth of $100,000 over the data history; payments are not deducted (investment performance only).

## Suggested dashboard inputs

Sidebar: assets (default 100,000), annual payment (default 5,000; try 6,000 to see trade-offs), years (default 20), strategy toggle (B default / A). Pass the same values to every function.

Demo moment: move annual payment from 5,000 to 6,000 → the funding ratio drops to about 1.08. With Option A the 30% crash turns red; switch to Option B and every scenario stays green.

Footer everywhere: *Educational hackathon project. Not financial advice.*
