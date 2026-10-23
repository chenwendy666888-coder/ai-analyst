"""
engine.py - Portfolio analytics for a defined-benefit (DB) pension.

Client: $100,000 of assets; pays $5,000 a year, growing with inflation, for 20 years.

Contents
  stats()            per-ETF annualised return, volatility, max drawdown, Sharpe
  pv_liabilities()   present value of the inflation-linked payments
  allocate()         two-pool allocation (liability-matching pool + growth pool)
  portfolio_metrics  the same metrics for any fixed-weight portfolio
  analyze()          runs everything; also used by stress.py
  build_facts()      final output dict for the app / LLM (JSON-safe)

Usage
  python engine.py                                            # full output + checks
  python -c "from engine import build_facts; print(build_facts())"

Data: read from the cached CSVs via data.load_data(). Nothing is downloaded here.

Key assumptions
  - Expected return = historical annualised (geometric) return over the last 10 years.
  - Risk-free rate = latest 3-month T-bill yield (DTB3), used for all Sharpe ratios.
  - Payments are made at the end of each year: payment_t = annual_payment * (1 + infl)^(t-1),
    infl = latest 10-year breakeven inflation (T10YIE).
  - Liabilities are discounted at the latest 10-year Treasury yield (DGS10), flat curve.
  - Historical portfolio metrics assume daily rebalancing to fixed weights.
"""
import json

import numpy as np
import pandas as pd

from data import load_data

TRADING_DAYS = 252

CLIENT_NAME = "Riverside Pension Fund"
MATCHING_ETFS = ["TIP", "IEF", "SHY", "BND"]
GROWTH_ETFS = ["VTI", "VEA", "VWO", "VNQ", "GLD"]
MATCHING_YEARS = 10        # matching pool = PV of the first 10 years of payments
TIP_MIN_WEIGHT = 0.40      # TIP >= 40% of the matching pool
GROWTH_MAX_WEIGHT = 0.40   # each growth ETF <= 40% of the growth pool
BENCHMARK = {"VTI": 0.60, "BND": 0.40}


# ------------------------------------------------------------------ market inputs
def latest_value(macro, column):
    """Latest valid value of a FRED series, converted from percent to a decimal."""
    s = macro[column].dropna()
    return float(s.iloc[-1]) / 100


def market_inputs(prices, macro):
    return {
        "risk_free": latest_value(macro, "DTB3"),
        "discount_rate": latest_value(macro, "DGS10"),
        "inflation": latest_value(macro, "T10YIE"),
        "data_end_date": str(prices.index.max().date()),
    }


# ------------------------------------------------------------------ performance
def performance(returns, rf):
    """Annualised return, volatility, max drawdown and Sharpe for a daily return series."""
    wealth = (1 + returns).cumprod()
    ann_return = wealth.iloc[-1] ** (TRADING_DAYS / len(returns)) - 1
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    peak = wealth.cummax().clip(lower=1.0)  # the starting value of 1.0 counts as a peak
    max_dd = (wealth / peak - 1).min()
    sharpe = (ann_return - rf) / vol if vol > 0 else float("nan")
    return {
        "expected_return": float(ann_return),
        "volatility": float(vol),
        "max_drawdown": float(max_dd),
        "sharpe": float(sharpe),
    }


def stats(prices, rf):
    """Per-ETF metrics, one row per ticker."""
    rows = {t: performance(prices[t].pct_change().dropna(), rf) for t in prices.columns}
    return pd.DataFrame(rows).T


def portfolio_metrics(weights, prices, rf):
    """Metrics for a fixed-weight portfolio. weights: Series indexed by ticker, summing to 1."""
    rets = prices[weights.index].pct_change().dropna()
    return performance(rets @ weights, rf)


# ------------------------------------------------------------------ liabilities
def liability_schedule(annual_payment, years, inflation, rate):
    """
    Year-by-year payments and present values.
    inflation: one rate for all years, or a list of per-year rates, where inflation[k]
    is the growth applied between payment k+1 and payment k+2.
    """
    if np.isscalar(inflation):
        infl = [float(inflation)] * years
    else:
        infl = list(inflation) + [inflation[-1]] * max(0, years - len(inflation))

    rows, payment = [], float(annual_payment)
    for t in range(1, years + 1):
        if t > 1:
            payment *= 1 + infl[t - 2]
        discount = (1 + rate) ** -t
        rows.append({"year": t, "payment": payment, "discount_factor": discount, "pv": payment * discount})
    return pd.DataFrame(rows)


def pv_liabilities(annual_payment, years, inflation, rate):
    """Present value of all payments over `years`."""
    return float(liability_schedule(annual_payment, years, inflation, rate)["pv"].sum())


# ------------------------------------------------------------------ allocation
def inverse_vol_weights(vols, floors=None, cap=None):
    """
    Inverse-volatility weights summing to 1, with optional per-ticker floors and a common cap.
    A ticker that breaks a floor or cap is fixed at that level; the remaining weight is
    shared among the other tickers by inverse volatility. Repeats until nothing breaks.
    """
    floors = floors or {}
    inv = 1 / vols
    fixed = {}
    while True:
        free = [t for t in vols.index if t not in fixed]
        if not free:
            w = pd.Series(dtype=float)
            break
        remaining = 1 - sum(fixed.values())
        w = inv[free] / inv[free].sum() * remaining
        changed = False
        for t in free:
            if t in floors and w[t] < floors[t]:
                fixed[t], changed = floors[t], True
            elif cap is not None and w[t] > cap:
                fixed[t], changed = cap, True
        if not changed:
            break
    return pd.concat([pd.Series(fixed, dtype=float), w]).reindex(vols.index)


def allocate(assets, annual_payment, years, etf_stats, inputs):
    """
    Matching pool = PV of the first 10 years of payments (capped at assets),
                    in TIP/IEF/SHY/BND, inverse-vol weighted, TIP >= 40%.
    Growth pool   = assets - matching pool,
                    in VTI/VEA/VWO/VNQ/GLD, inverse-vol weighted, each <= 40%.
    Returns a DataFrame: ticker, pool, weight (of total assets), dollars.
    """
    schedule = liability_schedule(annual_payment, years, inputs["inflation"], inputs["discount_rate"])
    matching_amount = float(schedule.loc[schedule["year"] <= MATCHING_YEARS, "pv"].sum())
    matching_amount = min(matching_amount, float(assets))
    growth_amount = float(assets) - matching_amount

    vols = etf_stats["volatility"]
    pools = [
        ("matching", matching_amount, inverse_vol_weights(vols[MATCHING_ETFS], floors={"TIP": TIP_MIN_WEIGHT})),
        ("growth", growth_amount, inverse_vol_weights(vols[GROWTH_ETFS], cap=GROWTH_MAX_WEIGHT)),
    ]
    rows = []
    for pool, amount, w in pools:
        for ticker, wt in w.items():
            rows.append({"ticker": ticker, "pool": pool, "weight": amount * wt / assets, "dollars": amount * wt})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ full analysis
def analyze(assets=100000, annual_payment=5000, years=20):
    """Run the full analysis. Returns a dict of intermediate results (also used by stress.py)."""
    prices, macro = load_data()
    inputs = market_inputs(prices, macro)
    etf_stats = stats(prices, inputs["risk_free"])

    pv = pv_liabilities(annual_payment, years, inputs["inflation"], inputs["discount_rate"])
    allocation = allocate(assets, annual_payment, years, etf_stats, inputs)
    weights = allocation.set_index("ticker")["weight"]

    metrics = portfolio_metrics(weights, prices, inputs["risk_free"])
    metrics["funding_ratio"] = assets / pv
    benchmark = portfolio_metrics(pd.Series(BENCHMARK), prices, inputs["risk_free"])
    benchmark["funding_ratio"] = assets / pv

    return {
        "assets": assets,
        "annual_payment": annual_payment,
        "years": years,
        "inputs": inputs,
        "etf_stats": etf_stats,
        "liability_pv": pv,
        "allocation": allocation,
        "metrics": metrics,
        "benchmark": benchmark,
    }


# ------------------------------------------------------------------ output
def _ratio(x):
    return round(float(x), 4)


def _whole_dollars(values, total):
    """Round to whole dollars so that the rounded amounts still add up exactly to `total`."""
    rounded = [int(round(v)) for v in values]
    diff = int(round(total)) - sum(rounded)
    if diff:
        i = int(np.argmax(values))  # absorb the rounding difference in the largest holding
        rounded[i] += diff
    return rounded


def build_facts(assets=100000, annual_payment=5000, years=20):
    """
    Final output for the app / LLM. Plain Python types only (JSON-safe).
    Money is in whole dollars; ratios are decimals rounded to 4 places (0.05 = 5%).
    """
    res = analyze(assets, annual_payment, years)
    keys = ["expected_return", "volatility", "max_drawdown", "sharpe", "funding_ratio"]

    alloc = res["allocation"]
    dollars = _whole_dollars(alloc["dollars"].tolist(), assets)

    try:
        from stress import run_stress  # imported here to avoid a circular import
        stress_rows = run_stress(res)
    except ImportError as err:
        print(f"WARNING: stress results skipped ({err}). Add the latest stress.py.")
        stress_rows = []

    return {
        "client": {
            "name": CLIENT_NAME,
            "assets": int(round(assets)),
            "annual_payment": int(round(annual_payment)),
            "years": int(years),
        },
        "allocation": [
            {"ticker": str(t), "pool": str(p), "weight": _ratio(w), "dollars": d}
            for t, p, w, d in zip(alloc["ticker"], alloc["pool"], alloc["weight"], dollars)
        ],
        "metrics": {k: _ratio(res["metrics"][k]) for k in keys},
        "benchmark": {k: _ratio(res["benchmark"][k]) for k in keys},
        "stress": [
            {
                "scenario": str(s["scenario"]),
                "portfolio_value": int(round(s["portfolio_value"])),
                "funding_ratio": _ratio(s["funding_ratio"]),
                "obligations_met": bool(s["obligations_met"]),
            }
            for s in stress_rows
        ],
        "assumptions": {
            "discount_rate": _ratio(res["inputs"]["discount_rate"]),
            "inflation": _ratio(res["inputs"]["inflation"]),
            "risk_free": _ratio(res["inputs"]["risk_free"]),
            "data_end_date": res["inputs"]["data_end_date"],
        },
    }


# ------------------------------------------------------------------ self-test
if __name__ == "__main__":
    facts = build_facts()
    print(json.dumps(facts, indent=2))  # also proves the dict is JSON-safe

    alloc = facts["allocation"]
    weight_sum = sum(a["weight"] for a in alloc)
    dollar_sum = sum(a["dollars"] for a in alloc)
    tickers = [a["ticker"] for a in alloc]
    expected = MATCHING_ETFS + GROWTH_ETFS

    checks = {
        f"weights sum to 1.0 (got {weight_sum:.4f})": abs(weight_sum - 1) < 1e-3,
        f"dollars sum to assets (got {dollar_sum:,})": dollar_sum == facts["client"]["assets"],
        "every ETF appears exactly once": sorted(tickers) == sorted(expected) and len(set(tickers)) == len(tickers),
    }
    print("\nChecks:")
    for label, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
