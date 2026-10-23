"""
stress.py - Stress tests for the pension portfolio.

Used automatically by engine.build_facts() through run_stress(res).
For "what if" questions from the app:
    from stress import custom_scenario
    custom_scenario(equity_shock=-0.30)            # markets fall 30%
    custom_scenario(rate_shock=0.02)               # rates rise 2 points
    custom_scenario(inflation_shock=0.03)          # inflation 3 points higher for 3 years

How a shock works (simple, explainable rules):
  - Equity shock: VTI, VEA, VWO, VNQ move by equity_shock. GLD is unchanged.
  - Rate shock: bond prices change by about -duration x rate_shock.
    Liabilities are re-discounted at (discount rate + rate_shock), so a
    rate rise lowers the value of the promises too. This is why pension
    funds match liabilities with bonds.
  - Inflation shock: inflation is higher by inflation_shock for
    inflation_years years, so future payments grow faster. TIP rises by
    roughly inflation_shock x inflation_years because it is inflation-linked.
  - Obligations are met if the funding ratio after the shock is at least 1.0.

All shock sizes and durations are stated ASSUMPTIONS, not forecasts.
"""
from engine import analyze, pv_liabilities, MATCHING_YEARS

EQUITY_ETFS = ["VTI", "VEA", "VWO", "VNQ"]

# Approximate durations in years (assumption; check the ETF fact sheets if needed)
DURATIONS = {"SHY": 1.9, "IEF": 7.5, "BND": 6.0, "TIP": 6.5}

INFLATION_YEARS = 3

SCENARIOS = [
    ("Equity crash -30%", {"equity_shock": -0.30}),
    ("Interest rates +2 points", {"rate_shock": 0.02}),
    ("Inflation +3 points for 3 years", {"inflation_shock": 0.03}),
    ("2022-style shock (stocks -20%, rates +2, inflation +3)",
     {"equity_shock": -0.20, "rate_shock": 0.02, "inflation_shock": 0.03}),
]


def asset_change(ticker, equity_shock=0.0, rate_shock=0.0, inflation_shock=0.0,
                 inflation_years=INFLATION_YEARS):
    """Percentage change in one ETF's value under a shock."""
    change = 0.0
    if ticker in EQUITY_ETFS:
        change += equity_shock
    if ticker in DURATIONS:
        change += -DURATIONS[ticker] * rate_shock
    if ticker == "TIP":
        change += inflation_shock * inflation_years
    return change


def apply_shock(res, name, equity_shock=0.0, rate_shock=0.0, inflation_shock=0.0,
                inflation_years=INFLATION_YEARS):
    """Apply one scenario to the results of engine.analyze()."""
    inputs = res["inputs"]
    years = res["years"]

    holdings = []
    for _, row in res["allocation"].iterrows():
        change = asset_change(row["ticker"], equity_shock, rate_shock, inflation_shock, inflation_years)
        after = max(0.0, float(row["dollars"]) * (1 + change))
        holdings.append({"ticker": row["ticker"], "before": float(row["dollars"]),
                         "after": after, "change": change})
    portfolio_value = sum(h["after"] for h in holdings)

    base_inflation = inputs["inflation"]
    inflation_path = ([base_inflation + inflation_shock] * inflation_years
                      + [base_inflation] * years)
    pv_after = pv_liabilities(res["annual_payment"], years, inflation_path,
                              inputs["discount_rate"] + rate_shock)
    funding_ratio = portfolio_value / pv_after

    return {
        "scenario": name,
        "portfolio_value": portfolio_value,
        "funding_ratio": funding_ratio,
        "obligations_met": funding_ratio >= 1.0,
        # Extra detail for the app and the "Challenge" chat (not required by build_facts)
        "pv_liabilities_after": pv_after,
        "holdings": holdings,
        "shocks": {"equity_shock": equity_shock, "rate_shock": rate_shock,
                   "inflation_shock": inflation_shock, "inflation_years": inflation_years},
    }


def run_stress(res):
    """All standard scenarios. Called by engine.build_facts()."""
    return [apply_shock(res, name, **shocks) for name, shocks in SCENARIOS]


def custom_scenario(equity_shock=0.0, rate_shock=0.0, inflation_shock=0.0,
                    assets=100000, annual_payment=5000, years=20, name="Custom scenario",
                    matching_years=MATCHING_YEARS):
    """
    One "what if" scenario, ready for the app or the LLM (plain Python types).
    Shocks are decimals: -0.30 = fall 30%, 0.02 = +2 percentage points.
    """
    for label, value, low, high in [("equity_shock", equity_shock, -0.9, 0.5),
                                    ("rate_shock", rate_shock, -0.05, 0.05),
                                    ("inflation_shock", inflation_shock, -0.05, 0.10)]:
        if not low <= value <= high:
            raise ValueError(f"{label}={value} is outside the allowed range [{low}, {high}]")

    res = analyze(assets, annual_payment, years, matching_years)
    s = apply_shock(res, name, equity_shock, rate_shock, inflation_shock)
    base_value = float(res["allocation"]["dollars"].sum())
    base_fr = float(res["metrics"]["funding_ratio"])
    return {
        "scenario": name,
        "shocks": s["shocks"],
        "portfolio_value_before": int(round(base_value)),
        "portfolio_value_after": int(round(s["portfolio_value"])),
        "funding_ratio_before": round(base_fr, 4),
        "funding_ratio_after": round(float(s["funding_ratio"]), 4),
        "obligations_met": bool(s["obligations_met"]),
        "holdings": [
            {"ticker": h["ticker"], "before": int(round(h["before"])),
             "after": int(round(h["after"])), "change": round(h["change"], 4)}
            for h in s["holdings"]
        ],
    }


if __name__ == "__main__":
    import json
    res = analyze()
    print(f"Base: value ${res['allocation']['dollars'].sum():,.0f}, "
          f"funding ratio {res['metrics']['funding_ratio']:.3f}\n")
    for s in run_stress(res):
        status = "MET" if s["obligations_met"] else "NOT MET"
        print(f"{s['scenario']:<58} value ${s['portfolio_value']:>9,.0f}   "
              f"funding ratio {s['funding_ratio']:.3f}   {status}")
    print("\nExample what-if (markets fall 30%):")
    print(json.dumps(custom_scenario(equity_shock=-0.30, name="Markets fall 30%"), indent=2))
