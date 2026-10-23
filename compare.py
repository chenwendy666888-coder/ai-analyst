"""
compare.py - Why this allocation? Compare our portfolio with simple alternatives.

Run:
    python compare.py
Use from the app:
    from compare import compare_portfolios, backtest_growth
    table = compare_portfolios(assets=100000, annual_payment=5000, years=20)
    growth = backtest_growth(assets=100000)   # DataFrame for a line chart

What it answers for the judges:
  - "Why not just use 60/40?"           -> same stress tests for every portfolio
  - "How did it do in the past?"        -> growth of $100,000 over 10 years
  - "Is 5% a year too much to pay?"     -> run with a different annual_payment
  - "Doesn't all-bonds look safest?"    -> long-term test: does the money last 20 years?

Two tests for every portfolio:
  1. Short-term shock: funding ratio in each stress scenario (>= 1.0 = can pay)
  2. Long-term: grow at the portfolio's historical return, pay every year -> does it last?
"""
import pandas as pd

from data import load_data
from engine import analyze, portfolio_metrics, project_assets, MATCHING_YEARS
from stress import SCENARIOS, apply_shock

OURS = "Our portfolio (LDI)"
ALTERNATIVES = {
    "60/40 stocks/bonds": {"VTI": 0.60, "BND": 0.40},
    "All stocks": {"VTI": 1.00},
    "All bonds": {"BND": 1.00},
}


def _weights_of_ours(res):
    alloc = res["allocation"]
    return pd.Series(alloc["weight"].values, index=alloc["ticker"].values, dtype=float)


def _allocation_frame(weights, assets):
    """Same shape as engine.allocate() output, so stress.apply_shock() can use it."""
    return pd.DataFrame(
        [{"ticker": t, "pool": "n/a", "weight": w, "dollars": w * assets} for t, w in weights.items()]
    )


def compare_portfolios(assets=100000, annual_payment=5000, years=20, matching_years=MATCHING_YEARS):
    """
    Metrics and stress results for our portfolio and each alternative.
    Returns a list of plain-Python dicts (JSON-safe), ours first.
    """
    res = analyze(assets, annual_payment, years, matching_years)
    prices, _ = load_data()
    rf = res["inputs"]["risk_free"]
    inflation = res["inputs"]["inflation"]
    base_funding = assets / res["liability_pv"]

    portfolios = {OURS: _weights_of_ours(res)}
    portfolios.update({name: pd.Series(w, dtype=float) for name, w in ALTERNATIVES.items()})

    rows = []
    for name, weights in portfolios.items():
        metrics = portfolio_metrics(weights, prices, rf)
        variant = dict(res, allocation=_allocation_frame(weights, assets))
        stress = [apply_shock(variant, scen, **shocks) for scen, shocks in SCENARIOS]
        passed = sum(bool(s["obligations_met"]) for s in stress)
        _, lasted, ending = project_assets(assets, annual_payment, years, inflation,
                                           metrics["expected_return"])
        survives_shocks = passed == len(stress)
        lasts = lasted >= years
        rows.append({
            "portfolio": name,
            "expected_return": round(metrics["expected_return"], 4),
            "volatility": round(metrics["volatility"], 4),
            "max_drawdown": round(metrics["max_drawdown"], 4),
            "sharpe": round(metrics["sharpe"], 4),
            "funding_ratio": round(base_funding, 4),
            "worst_funding_ratio": round(min(s["funding_ratio"] for s in stress), 4),
            "scenarios_passed": f"{passed} of {len(stress)}",
            "survives_all_shocks": survives_shocks,
            "years_lasted": int(lasted),
            "lasts_full_horizon": lasts,
            "ending_assets": int(round(ending)),
            "passes_both_tests": survives_shocks and lasts,
            "stress": [
                {
                    "scenario": s["scenario"],
                    "portfolio_value": int(round(s["portfolio_value"])),
                    "funding_ratio": round(float(s["funding_ratio"]), 4),
                    "obligations_met": bool(s["obligations_met"]),
                }
                for s in stress
            ],
        })
    return rows


def backtest_growth(assets=100000, annual_payment=5000, years=20, monthly=True,
                    matching_years=MATCHING_YEARS):
    """
    Growth of `assets` over the data history for each portfolio, rebalanced daily
    to fixed weights. Payments are NOT deducted: this shows investment performance only.
    Returns a DataFrame (index = date, one column per portfolio), month-end by default.
    """
    res = analyze(assets, annual_payment, years, matching_years)
    prices, _ = load_data()
    portfolios = {OURS: _weights_of_ours(res)}
    portfolios.update({name: pd.Series(w, dtype=float) for name, w in ALTERNATIVES.items()})

    growth = {}
    for name, w in portfolios.items():
        daily = prices[w.index].pct_change().dropna() @ w
        growth[name] = (1 + daily).cumprod() * assets
    out = pd.DataFrame(growth)
    if monthly:
        out = out.resample("ME").last()
    out.index.name = "date"
    return out.round(0)


SHORT = {OURS: "Ours", "60/40 stocks/bonds": "60/40", "All stocks": "Stocks", "All bonds": "Bonds"}


def _print_table(rows, annual_payment, years=20):
    print(f"\n=== Portfolio comparison (annual payment ${annual_payment:,}, {years} years) ===")
    print(f"{'Portfolio':<22}{'Return':>8}{'Vol':>8}{'MaxDD':>9}"
          f"{'Worst FR':>10}{'Shocks':>8}{'Lasts':>12}{'Both':>7}")
    for r in rows:
        lasts = f"{r['years_lasted']} yrs" if not r["lasts_full_horizon"] else "yes"
        print(f"{r['portfolio']:<22}{r['expected_return']:>8.2%}{r['volatility']:>8.2%}"
              f"{r['max_drawdown']:>9.2%}{r['worst_funding_ratio']:>10.2f}"
              f"{r['scenarios_passed']:>8}{lasts:>12}{'YES' if r['passes_both_tests'] else 'no':>7}")
    print("\nFunding ratio in each scenario:")
    scenarios = [s["scenario"] for s in rows[0]["stress"]]
    for i, scen in enumerate(scenarios):
        cells = "   ".join(
            f"{SHORT[r['portfolio']]}: {r['stress'][i]['funding_ratio']:.2f}"
            f"{'' if r['stress'][i]['obligations_met'] else ' (FAIL)'}"
            for r in rows
        )
        print(f"  {scen[:32]:<32} {cells}")
    print("\nMoney left after the full horizon (growing at each portfolio's historical return):")
    for r in rows:
        status = f"${r['ending_assets']:,}" if r["lasts_full_horizon"] else f"runs out after {r['years_lasted']} years"
        print(f"  {r['portfolio']:<22} {status}")
    print("  (Shocks = stress scenarios passed; Lasts = money lasts the full horizon; Both = passes both tests)")


def _matching_years_table(annual_payment=5000):
    print(f"\n=== Effect of the matching-pool length (annual payment ${annual_payment:,}) ===")
    print(f"{'Matching years':<16}{'Bonds %':>9}{'Return':>9}{'MaxDD':>9}{'Worst FR':>10}{'Lasts':>10}")
    for m in (5, 10, 15, 20):
        r = compare_portfolios(annual_payment=annual_payment, matching_years=m)[0]
        res = analyze(annual_payment=annual_payment, matching_years=m)
        bonds = res["allocation"].loc[res["allocation"]["pool"] == "matching", "weight"].sum()
        lasts = "yes" if r["lasts_full_horizon"] else f"{r['years_lasted']} yrs"
        print(f"{m:<16}{bonds:>9.0%}{r['expected_return']:>9.2%}{r['max_drawdown']:>9.2%}"
              f"{r['worst_funding_ratio']:>10.2f}{lasts:>10}")


if __name__ == "__main__":
    for payment in (5000, 6000):
        _print_table(compare_portfolios(annual_payment=payment), payment)
    _matching_years_table(5000)

    g = backtest_growth()
    print("\n=== Growth of $100,000 (start -> end, payments not deducted) ===")
    for col in g.columns:
        print(f"  {col:<22} ${g[col].iloc[0]:>10,.0f} -> ${g[col].iloc[-1]:>10,.0f}")
    g.to_csv("data/backtest_growth.csv")
    print("\nSaved: data/backtest_growth.csv (for the app's line chart)")
