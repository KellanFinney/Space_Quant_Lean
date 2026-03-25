# lean-exclude: research
"""
Lesson 15 — Research script (not a LEAN backtest).

Uses yfinance + pandas + numpy + matplotlib to build tables and charts for the
same bank tickers as the QuantConnect fundamentals tutorial.

Run from repo root (venv must have yfinance, pandas, numpy, matplotlib):

    source venv/bin/activate
    python Algorithms/quantconnect_learning/lesson15.py
    python Algorithms/quantconnect_learning/lesson15.py --show   # open plots in a window

Outputs under Research/output/lesson15/ include pe_histogram.png (bins + ticker names),
pe_by_ticker.png (horizontal bar per bank), and correlation / price charts. (and plots also display
if you have a GUI backend).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

# Repo root = .../Space_Quant_Lean
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "Research" / "output" / "lesson15"

TICKERS = ["JPM", "BAC", "MS", "SCHW", "GS", "AXP", "C"]
PRICE_START = "2021-01-01"
PRICE_END = "2022-01-01"


def fetch_fundamentals_table(tickers: Sequence[str]) -> pd.DataFrame:
    """Build a table of key valuation / size fields from yfinance .info."""
    rows: list[dict] = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
        except Exception as e:
            rows.append({"Ticker": ticker, "Error": str(e)})
            continue
        rows.append(
            {
                "Ticker": ticker,
                "Name": info.get("shortName") or info.get("longName", ""),
                "Sector": info.get("sector", ""),
                "MarketCap": info.get("marketCap"),
                "trailingPE": info.get("trailingPE"),
                "forwardPE": info.get("forwardPE"),
                "priceToBook": info.get("priceToBook"),
                "dividendYield": info.get("dividendYield"),
            }
        )
    return pd.DataFrame(rows)


def fetch_price_matrix(tickers: Sequence[str], start: str, end: str) -> pd.DataFrame:
    """Daily adjusted close matrix for correlation / normalization plots."""
    data = yf.download(
        tickers,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,
        threads=True,
    )
    if data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            closes = data["Close"]
        else:
            closes = data.xs("Close", axis=1, level=0)
    else:
        closes = data["Close"] if "Close" in data else data

    return closes.dropna(how="all")


def prepare_trailing_pe_table(fund: pd.DataFrame) -> pd.DataFrame:
    """Return clean Ticker + trailingPE table with numeric P/E only."""
    pe = fund[["Ticker", "trailingPE"]].copy()
    pe["trailingPE"] = pd.to_numeric(pe["trailingPE"], errors="coerce")
    pe = pe.dropna(subset=["trailingPE"])
    return pe


def plot_return_correlation_heatmap(
    corr: pd.DataFrame,
    out_path: Path,
    title: str = "Daily return correlation",
    show: bool = False,
) -> None:
    """Heatmap of return correlation with numeric labels on each cell."""
    fig, ax = plt.subplots(figsize=(8, 7))
    arr = corr.values.astype(float)
    im = ax.imshow(arr, cmap="RdBu_r", vmin=-1, vmax=1, aspect="equal")

    ticks = range(len(corr.columns))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.index)
    ax.set_title(title)

    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            val = arr[i, j]
            # contrast: dark text on pale cells, light text on saturated
            txt_color = "white" if abs(val) > 0.55 else "#1a1a1a"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=txt_color, fontsize=9)

    fig.colorbar(im, ax=ax, fraction=0.046, label="Correlation")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)


def save_figure(fig, path: Path, show: bool) -> None:
    """Save figure to disk and optionally display it."""
    fig.savefig(path, dpi=150)
    if show:
        plt.show()
    plt.close(fig)


def plot_pe_histogram_with_ticker_labels(fund: pd.DataFrame, out_path: Path, show: bool) -> None:
    """
    Histogram of trailing P/E with each bar annotated by the tickers in that bin.
    X-axis shows P/E range per bin.
    """
    pe_table = prepare_trailing_pe_table(fund)
    if pe_table.empty:
        return

    n_bins = min(12, max(5, len(pe_table)))
    pe_table["bin"] = pd.cut(pe_table["trailingPE"], bins=n_bins, include_lowest=True)

    rows: list[dict] = []
    for interval, group in pe_table.groupby("bin", observed=True):
        rows.append(
            {
                "interval": interval,
                "left": float(interval.left),
                "right": float(interval.right),
                "count": len(group),
                "tickers": ", ".join(sorted(group["Ticker"].astype(str))),
            }
        )

    binned = pd.DataFrame(rows).sort_values("left")
    if binned.empty:
        return

    x = np.arange(len(binned))
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(x, binned["count"], color="steelblue", edgecolor="black", alpha=0.85, width=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{r.left:.1f}-{r.right:.1f}" for r in binned["interval"]],
        rotation=35,
        ha="right",
        fontsize=9,
    )
    ax.set_xlabel("Trailing P/E (bin range)")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of trailing P/E — tickers labeled per bin")
    ymax = max(binned["count"].max(), 1) * 1.35

    for idx, (_, row) in enumerate(binned.iterrows()):
        h = row["count"]
        ax.text(idx, h + 0.08, row["tickers"], ha="center", va="bottom", fontsize=9, fontweight="medium")

    ax.set_ylim(0, ymax)
    fig.tight_layout()
    save_figure(fig, out_path, show)


def plot_trailing_pe_by_ticker(fund: pd.DataFrame, out_path: Path, show: bool) -> None:
    """Horizontal bars: one row per ticker with exact trailing P/E (easiest to read)."""
    pe_table = prepare_trailing_pe_table(fund).sort_values("trailingPE", ascending=True)
    if pe_table.empty:
        return

    fig_h = max(4.0, len(pe_table) * 0.55)
    fig, ax = plt.subplots(figsize=(8, fig_h))
    y = np.arange(len(pe_table))
    ax.barh(y, pe_table["trailingPE"], color="steelblue", edgecolor="black", alpha=0.85, height=0.65)
    ax.set_yticks(y)
    ax.set_yticklabels(pe_table["Ticker"])
    ax.set_xlabel("Trailing P/E")
    ax.set_title("Trailing P/E by ticker — large U.S. banks")
    for i, pe in enumerate(pe_table["trailingPE"]):
        ax.text(pe + 0.15, i, f"{pe:.2f}", va="center", fontsize=9)

    ax.set_xlim(0, pe_table["trailingPE"].max() * 1.18)
    fig.tight_layout()
    save_figure(fig, out_path, show)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lesson 15 bank research plots")
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open an interactive window for each figure (after saving)",
    )
    args = parser.parse_args()
    show = args.show

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching fundamentals via yfinance...")
    fund = fetch_fundamentals_table(TICKERS)
    csv_path = OUT_DIR / "bank_fundamentals.csv"
    fund.to_csv(csv_path, index=False)
    print(fund.to_string(index=False))
    print(f"\nSaved table: {csv_path}")

    # Trailing P/E: histogram with ticker labels per bin + bar chart by ticker
    pe = prepare_trailing_pe_table(fund)
    if len(pe) > 0:
        hist_path = OUT_DIR / "pe_histogram.png"
        plot_pe_histogram_with_ticker_labels(fund, hist_path, show)
        print(f"Saved histogram (tickers per bin): {hist_path}")

        pe_by_ticker_path = OUT_DIR / "pe_by_ticker.png"
        plot_trailing_pe_by_ticker(fund, pe_by_ticker_path, show)
        print(f"Saved P/E by ticker: {pe_by_ticker_path}")

    # Normalized price paths (2021 window like original lesson)
    print("\nFetching daily prices (2021–2022)...")
    prices = fetch_price_matrix(TICKERS, PRICE_START, PRICE_END)
    if not prices.empty:
        norm = prices / prices.iloc[0] * 100.0
        fig, ax = plt.subplots(figsize=(10, 5))
        for col in norm.columns:
            ax.plot(norm.index, norm[col], label=col, linewidth=1.2)
        ax.set_ylabel("Index (start = 100)")
        ax.set_title("Normalized adjusted close — 2021")
        ax.legend(loc="upper left", fontsize=8, ncol=2)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        ts_path = OUT_DIR / "normalized_prices_2021.png"
        save_figure(fig, ts_path, show)
        print(f"Saved time series: {ts_path}")

        rets = prices.pct_change().dropna()
        corr = rets.corr()
        corr_path = OUT_DIR / "return_correlation.csv"
        corr.to_csv(corr_path)
        print(f"Saved correlation matrix: {corr_path}")

        corr_png = OUT_DIR / "correlation_heatmap.png"
        plot_return_correlation_heatmap(
            corr,
            corr_png,
            title="Daily return correlation (2021)",
            show=show,
        )
        print(f"Saved return correlation heatmap: {corr_png}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
