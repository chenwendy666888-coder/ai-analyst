"""
test_all.py - Check that every part of the engine works before handing it to the app.

Run:
    python test_all.py
"""
import json
import traceback

results = []


def check(name, fn):
    try:
        detail = fn()
        results.append((True, name, detail or ""))
    except Exception as err:
        results.append((False, name, f"{type(err).__name__}: {err}"))
        traceback.print_exc()


def t_data():
    from data import load_data
    prices, macro = load_data()
    assert prices.shape[1] == 9, f"expected 9 ETFs, got {prices.shape[1]}"
    assert prices.isna().sum().sum() == 0, "prices have missing values"
    for col in ["DTB3", "DGS10", "T10YIE"]:
        assert col in macro.columns, f"macro is missing {col}"
    return f"{prices.shape[0]} days, {prices.index.min().date()} to {prices.index.max().date()}"


def t_facts():
    from engine import build_facts
    f = build_facts()
    json.dumps(f)
    for key in ["client", "allocation", "metrics", "benchmark", "stress", "projection", "assumptions"]:
        assert key in f, f"missing key {key}"
    assert len(f["allocation"]) == 9, "allocation should list 9 ETFs"
    assert sum(a["dollars"] for a in f["allocation"]) == f["client"]["assets"], "dollars do not sum to assets"
    assert abs(sum(a["weight"] for a in f["allocation"]) - 1) < 1e-3, "weights do not sum to 1"
    assert len(f["stress"]) == 4, "expected 4 stress scenarios"
    return f"funding ratio {f['metrics']['funding_ratio']}, return {f['metrics']['expected_return']:.2%}"


def t_inputs():
    from engine import build_facts
    a = build_facts(annual_payment=5000)["metrics"]["funding_ratio"]
    b = build_facts(annual_payment=6000)["metrics"]["funding_ratio"]
    c = build_facts(assets=200000)["client"]["assets"]
    assert b < a, "a higher payment should lower the funding ratio"
    assert c == 200000, "assets input not used"
    return f"payment $5k -> {a}, $6k -> {b}"


def t_custom():
    from stress import custom_scenario
    s = custom_scenario(equity_shock=-0.30)
    json.dumps(s)
    assert s["portfolio_value_after"] < s["portfolio_value_before"], "a crash should lower the value"
    r = custom_scenario(rate_shock=0.02)
    try:
        custom_scenario(equity_shock=-5)
        raise AssertionError("an impossible shock was not rejected")
    except ValueError:
        pass
    return (f"crash -30%: FR {s['funding_ratio_before']} -> {s['funding_ratio_after']}; "
            f"rates +2: FR {r['funding_ratio_before']} -> {r['funding_ratio_after']}")


def t_projection():
    from engine import build_facts
    p = build_facts()["projection"]
    assert len(p["path"]) == 20, "projection should have one row per year"
    assert "years_lasted" in p and "lasts_full_horizon" in p, "projection fields missing"
    return (f"ours lasts {p['years_lasted']} years, ends with ${p['ending_assets']:,}; "
            f"60/40 ends with ${p['benchmark_ending_assets']:,}")


def t_matching():
    from engine import build_facts
    def bonds(m):
        f = build_facts(matching_years=m)
        return sum(a["weight"] for a in f["allocation"] if a["pool"] == "matching")
    b5, b10, b15 = bonds(5), bonds(10), bonds(15)
    assert b5 < b10 < b15, "more matching years should mean more bonds"
    return f"bonds share: 5 yrs {b5:.0%}, 10 yrs {b10:.0%}, 15 yrs {b15:.0%}"


def t_compare():
    from compare import compare_portfolios
    rows = compare_portfolios()
    json.dumps(rows)
    assert len(rows) == 4, "expected 4 portfolios"
    for key in ["survives_all_shocks", "lasts_full_horizon", "passes_both_tests"]:
        assert key in rows[0], f"missing {key}"
    return "; ".join(
        f"{r['portfolio']}: shocks {r['scenarios_passed']}, "
        f"{'lasts' if r['lasts_full_horizon'] else 'runs out yr ' + str(r['years_lasted'])}"
        for r in rows)


def t_backtest():
    from compare import backtest_growth
    g = backtest_growth()
    assert g.shape[1] == 4 and len(g) > 100, "unexpected backtest shape"
    return f"{len(g)} months, ours ends at ${g.iloc[-1, 0]:,.0f}"


if __name__ == "__main__":
    check("1. Data loads (9 ETFs, no gaps)", t_data)
    check("2. build_facts() has the right format", t_facts)
    check("3. Inputs change the result", t_inputs)
    check("4. custom_scenario() for 'what if'", t_custom)
    check("5. 20-year projection (does the money last?)", t_projection)
    check("6. Matching-years slider changes the bond share", t_matching)
    check("7. compare_portfolios() with both tests", t_compare)
    check("8. backtest_growth()", t_backtest)

    print("\n" + "=" * 70)
    for ok, name, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        if detail:
            print(f"       {detail}")
    passed = sum(ok for ok, _, _ in results)
    print("=" * 70)
    print(f"{passed} of {len(results)} checks passed")
