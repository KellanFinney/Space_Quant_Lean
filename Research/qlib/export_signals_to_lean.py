#!/usr/bin/env python3
"""
Export Qlib-style predictions (long format) to CSV files LEAN can read via PythonData.

Each symbol gets: Data/custom/qlib_signals/<symbol_lower>_signal.csv
Columns: Date,Score  (ISO dates YYYY-MM-DD)

Run from repository root after you have a predictions DataFrame from Qlib:

    python -c "
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path('Research/qlib').resolve()))
    import pandas as pd
    from export_signals_to_lean import export_long_format
    df = pd.DataFrame({
        'datetime': pd.date_range('2020-01-02', periods=3, freq='B'),
        'instrument': ['RKLB','RKLB','RKLB'],
        'score': [0.1, -0.02, 0.05],
    })
    print(export_long_format(df))
    "

Or import `export_long_format` from your Qlib notebook/script after `model.predict`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "Data" / "custom" / "qlib_signals"


def export_long_format(
    df: pd.DataFrame,
    *,
    date_col: str = "datetime",
    symbol_col: str = "instrument",
    score_col: str = "score",
    out_dir: Path | None = None,
) -> list[Path]:
    """
    Parameters
    ----------
    df : DataFrame
        Must contain date, symbol, and numeric score columns.
    date_col :
        Parsed to datetime; written as YYYY-MM-DD.
    symbol_col :
        Values become filenames (e.g. RKLB -> rklb_signal.csv).
    score_col :
        Single float column (e.g. model score or predicted return).
    """
    out = out_dir or DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)

    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col]).dt.strftime("%Y-%m-%d")

    written: list[Path] = []
    for sym, g in d.groupby(symbol_col):
        sym_clean = str(sym).split(".")[-1].upper()
        sub = g[[date_col, score_col]].copy()
        sub.columns = ["Date", "Score"]
        path = out / f"{sym_clean.lower()}_signal.csv"
        sub.sort_values("Date").to_csv(path, index=False)
        written.append(path)

    return written


def main() -> int:
    print("Import from another script with:")
    print("  sys.path.insert(0, str(Path('Research/qlib').resolve()))")
    print("  from export_signals_to_lean import export_long_format")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
