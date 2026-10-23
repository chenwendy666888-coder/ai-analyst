"""
data.py - Download and cache market data from Yahoo Finance (one public source).

First run (downloads from the internet and writes to data/):
    python data.py
Everywhere else, read the cached CSVs only:
    from data import load_data
    prices, macro = load_data()

Sources
  - ETF prices: Yahoo Finance daily adjusted close (dividends included)
  - 10-year US Treasury yield: Yahoo Finance ^TNX  -> column DGS10
  - 13-week US Treasury bill yield: Yahoo Finance ^IRX -> column DTB3
  - Inflation: a stated ASSUMPTION (INFLATION_ASSUMPTION) -> column T10YIE
    (Yahoo Finance has no inflation series.)
Column names are kept as DGS10 / DTB3 / T10YIE so engine.py works unchanged.
All rates are stored in PERCENT (4.2 means 4.2%).
"""
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).parent / "data"
PRICES_CSV = DATA_DIR / "prices.csv"
MACRO_CSV = DATA_DIR / "macro.csv"

TICKERS = ["TIP", "IEF", "SHY", "BND", "VTI", "VEA", "VWO", "VNQ", "GLD"]
RATE_TICKERS = {"DGS10": "^TNX", "DTB3": "^IRX"}  # 10-year yield, 13-week T-bill yield
INFLATION_ASSUMPTION = 2.5  # percent per year; slightly above the Fed's 2% target, a cautious choice
YEARS = 10


def _download_close(tickers, start, adjust):
    """Daily close prices from Yahoo Finance as a DataFrame with a plain date index."""
    df = yf.download(tickers, start=str(start), auto_adjust=adjust, progress=False)
    if df.empty:
        raise RuntimeError("Yahoo Finance returned no data: check the network or retry in a minute (rate limit)")
    close = df["Close"].reindex(columns=tickers)  # a failed ticker shows up as an all-NaN column
    close.index = pd.to_datetime(close.index)
    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)
    close.index.name = "date"
    return close


def download_prices(start):
    """ETF prices, adjusted for dividends and splits."""
    return _download_close(TICKERS, start, adjust=True)


def download_macro(start):
    """Interest rates from Yahoo Finance plus the inflation assumption, in percent."""
    rates = _download_close(list(RATE_TICKERS.values()), start, adjust=False)
    macro = pd.DataFrame(index=rates.index)
    for column, ticker in RATE_TICKERS.items():
        series = rates[ticker].astype(float)
        if series.dropna().median() > 20:  # some feeds quote the yield x10
            series = series / 10
        macro[column] = series
    macro["T10YIE"] = INFLATION_ASSUMPTION
    macro.index.name = "date"
    return macro


def report(name, s):
    """Print a series' first and last valid dates, number of observations and missing values."""
    valid = s.dropna()
    if valid.empty:
        print(f"  {name:<9} NO DATA (missing {len(s)})")
        return
    print(
        f"  {name:<9} {valid.index.min().date()} -> {valid.index.max().date()}"
        f"   obs {len(s):>5}   missing {int(s.isna().sum()):>4}"
    )


def download_all():
    DATA_DIR.mkdir(exist_ok=True)
    start = (pd.Timestamp.today() - pd.DateOffset(years=YEARS)).date()
    print(f"Source: Yahoo Finance   Download window: {start} to today\n")

    prices = download_prices(start)
    prices.to_csv(PRICES_CSV)
    print("=== ETF adjusted close (daily) ===")
    for t in TICKERS:
        report(t, prices[t])

    macro = download_macro(start)
    macro.to_csv(MACRO_CSV)
    print("\n=== Rates (Yahoo Finance) and inflation assumption ===")
    report("DGS10", macro["DGS10"])
    report("DTB3", macro["DTB3"])
    print(f"  T10YIE    fixed assumption: {INFLATION_ASSUMPTION}% a year")
    print(f"\n  Latest 10-year yield: {macro['DGS10'].dropna().iloc[-1]:.2f}%")
    print(f"  Latest 13-week T-bill: {macro['DTB3'].dropna().iloc[-1]:.2f}%")

    print(f"\nSaved: {PRICES_CSV}")
    print(f"Saved: {MACRO_CSV}")


def load_data():
    """Read the cached CSVs only. Returns (prices, macro) DataFrames indexed by date."""
    if not PRICES_CSV.exists() or not MACRO_CSV.exists():
        raise FileNotFoundError("Cached CSVs not found in data/. Run: python data.py")
    prices = pd.read_csv(PRICES_CSV, index_col="date", parse_dates=True)
    macro = pd.read_csv(MACRO_CSV, index_col="date", parse_dates=True)
    return prices, macro


if __name__ == "__main__":
    download_all()
    prices, macro = load_data()
    print(f"\nload_data() check: prices {prices.shape}, macro {macro.shape}")