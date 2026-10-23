# PLACEHOLDER: replace the dict below with the one from TEAM_PLAN.md.
# Schema assumed by app.py (all rates are decimal fractions: 0.062 = 6.2%):
#   inputs, allocation[{pool, ticker, name, weight}], metrics, benchmark,
#   stress_tests[{scenario, funding_ratio, obligations_met}]

FAKE_FACTS = {
    "inputs": {"assets": 500_000_000, "annual_payment": 25_000_000, "years": 20},
    "allocation": [
        {"pool": "Liability matching", "ticker": "TLT", "name": "iShares 20+ Year Treasury", "weight": 0.30},
        {"pool": "Liability matching", "ticker": "TIP", "name": "iShares TIPS Bond", "weight": 0.15},
        {"pool": "Growth", "ticker": "VTI", "name": "Vanguard Total US Stock", "weight": 0.25},
        {"pool": "Growth", "ticker": "VXUS", "name": "Vanguard Total Intl Stock", "weight": 0.15},
        {"pool": "Diversifiers", "ticker": "GLD", "name": "SPDR Gold Shares", "weight": 0.10},
        {"pool": "Diversifiers", "ticker": "VNQ", "name": "Vanguard Real Estate", "weight": 0.05},
    ],
    "metrics": {"expected_return": 0.062, "volatility": 0.094, "max_drawdown": -0.183, "funding_ratio": 1.04},
    "benchmark": {"expected_return": 0.058, "volatility": 0.112, "max_drawdown": -0.221, "funding_ratio": 0.98},
    "stress_tests": [
        {"scenario": "Equity crash (-30%)", "funding_ratio": 0.91, "obligations_met": False},
        {"scenario": "Rates +2%", "funding_ratio": 1.01, "obligations_met": True},
        {"scenario": "Rates -2%", "funding_ratio": 1.09, "obligations_met": True},
        {"scenario": "High inflation (+4%)", "funding_ratio": 0.95, "obligations_met": False},
        {"scenario": "Stagflation", "funding_ratio": 0.88, "obligations_met": False},
        {"scenario": "Base case", "funding_ratio": 1.04, "obligations_met": True},
    ],
}
