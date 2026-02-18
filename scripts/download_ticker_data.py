"""
Download equity data from Yahoo Finance and convert to LEAN format.

Usage:
    python scripts/download_ticker_data.py SPY BND
    python scripts/download_ticker_data.py RKLB --start 2021-08-25
    python scripts/download_ticker_data.py SPY BND RKLB TSLA --end 2025-12-31
"""
import argparse
import os
import sys
import zipfile
from pathlib import Path

import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "Data" / "equity" / "usa" / "daily"


def download_and_save(ticker, start_date, end_date, output_dir):
    print(f"\n{'='*50}")
    print(f"Downloading {ticker} ({start_date} to {end_date})...")

    stock = yf.Ticker(ticker)
    data = stock.history(start=start_date, end=end_date, interval="1d")

    if data.empty:
        print(f"  No data found for {ticker}")
        return False

    data = data.reset_index()
    print(f"  {len(data)} rows  |  {data['Date'].iloc[0].date()} to {data['Date'].iloc[-1].date()}")

    os.makedirs(output_dir, exist_ok=True)

    lean_data = pd.DataFrame({
        "datetime": data["Date"].dt.strftime("%Y%m%d 00:00"),
        "open":   (data["Open"]  * 10000).round().astype(int),
        "high":   (data["High"]  * 10000).round().astype(int),
        "low":    (data["Low"]   * 10000).round().astype(int),
        "close":  (data["Close"] * 10000).round().astype(int),
        "volume": data["Volume"].astype(int),
    })

    zip_path = os.path.join(output_dir, f"{ticker.lower()}.zip")
    csv_content = lean_data.to_csv(index=False, header=False)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{ticker.lower()}.csv", csv_content)

    print(f"  Saved to {zip_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Download equity data for LEAN")
    parser.add_argument("tickers", nargs="+", help="Ticker symbols (e.g. SPY BND RKLB)")
    parser.add_argument("--start", default="2000-01-01", help="Start date (default: 2000-01-01)")
    parser.add_argument("--end", default="2026-12-31", help="End date (default: 2026-12-31)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output directory")
    args = parser.parse_args()

    success = 0
    for ticker in args.tickers:
        if download_and_save(ticker.upper(), args.start, args.end, args.output):
            success += 1

    print(f"\nDone! Downloaded {success}/{len(args.tickers)} tickers to {args.output}")


if __name__ == "__main__":
    main()
