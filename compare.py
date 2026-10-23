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
"""
import pandas as pd

from data import load_data
from engine import analyze, portfolio_metrics
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


def compare_portfolios(assets=100000, annual_payment=5000, years=20):
    """
    Metrics and stress results for our portfolio and each alternative.
    Returns a list of plain-Python dicts (JSON-safe), ours first.
    """
    res = analyze(assets, annual_payment, years)
    prices, _ = load_data()
    rf = res["inputs"]["risk_free"]
    base_funding = assets / res["liability_pv"]

    portfolios = {OURS: _weights_of_ours(res)}
    portfolios.update({name: pd.Series(w, dtype=float) for name, w in ALTERNATIVES.items()})

    rows = []
    for name, weights in portfolios.items():
        metrics = portfolio_metrics(weights, prices, rf)
        variant = dict(res, allocation=_allocation_frame(weights, assets))
        stress = [apply_shock(variant, scen, **shocks) for scen, shocks in SCENARIOS]
        passed = sum(bool(s["obligations_met"]) for s in stress)
        rows.append({
            "portfolio": name,
            "expected_return": round(metrics["expected_return"], 4),
            "volatility": round(metrics["volatility"], 4),
            "max_drawdown": round(metrics["max_drawdown"], 4),
            "sharpe": round(metrics["sharpe"], 4),
            "funding_ratio": round(base_funding, 4),
            "worst_funding_ratio": round(min(s["funding_ratio"] for s in stress), 4),
            "scenarios_passed": f"{passed} of {len(stress)}",
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


def backtest_growth(assets=100000, annual_payment=5000, years=20, monthly=True):
    """
    Growth of `assets` over the data history for each portfolio, rebalanced daily
    to fixed weights. Payments are NOT deducted: this shows investment performance only.
    Returns a DataFrame (index = date, one column per portfolio), month-end by default.
    """
    res = analyze(assets, annual_payment, years)
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


def _print_table(rows, annual_payment):
    print(f"\n=== Portfolio comparison (annual payment ${annual_payment:,}) ===")
    print(f"{'Portfolio':<22}{'Return':>8}{'Vol':>8}{'MaxDD':>9}{'Sharpe':>8}"
          f"{'Worst FR':>10}{'Passed':>9}")
    for r in rows:
        print(f"{r['portfolio']:<22}{r['expected_return']:>8.2%}{r['volatility']:>8.2%}"
              f"{r['max_drawdown']:>9.2%}{r['sharpe']:>8.2f}"
              f"{r['worst_funding_ratio']:>10.2f}{r['scenarios_passed']:>9}")
    print("\nFunding ratio in each scenario:")
    scenarios = [s["scenario"] for s in rows[0]["stress"]]
    for i, scen in enumerate(scenarios):
        cells = "   ".join(
            f"{SHORT[r['portfolio']]}: {r['stress'][i]['funding_ratio']:.2f}"
            f"{'' if r['stress'][i]['obligations_met'] else ' (FAIL)'}"
            for r in rows
        )
        print(f"  {scen[:32]:<32} {cells}")
    print("  (FAIL = funding ratio below 1.0, so the fund could not cover its promises)")


if __name__ == "__main__":
    for payment in (5000, 6000):
        _print_table(compare_portfolios(annual_payment=payment), payment)

    g = backtest_growth()
    print("\n=== Growth of $100,000 (start -> end, payments not deducted) ===")
    for col in g.columns:
        print(f"  {col:<22} ${g[col].iloc[0]:>10,.0f} -> ${g[col].iloc[-1]:>10,.0f}")
    g.to_csv("data/backtest_growth.csv")
    print("\nSaved: data/backtest_growth.csv (for the app's line chart)")
