#!/usr/bin/env python3
"""
Quick check: Qlib imports and (if present) local bin data under ~/.qlib/qlib_data/.

Run from repository root:
    python Research/qlib/smoke_test.py

Optional env:
    QLIB_DATA=~/.qlib/qlib_data/us_data  QLIB_REGION=us
    QLIB_DATA=~/.qlib/qlib_data/cn_data  QLIB_REGION=cn
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    try:
        import qlib
        from qlib.constant import REG_CN, REG_US
    except ImportError:
        print(
            "Cannot import qlib. Install with: pip install -e /path/to/qlib",
            file=sys.stderr,
        )
        return 1

    ver = getattr(qlib, "__version__", "unknown")
    print(f"qlib import OK (version {ver})")

    region = os.environ.get("QLIB_REGION", "us").lower()
    reg = REG_US if region == "us" else REG_CN

    default_uri = (
        "~/.qlib/qlib_data/us_data" if region == "us" else "~/.qlib/qlib_data/cn_data"
    )
    provider_uri = os.path.expanduser(os.environ.get("QLIB_DATA", default_uri))
    p = Path(provider_uri)

    if not p.exists():
        print(f"No Qlib bin data at: {provider_uri}")
        print("Prepare data per https://github.com/microsoft/qlib#data-preparation")
        return 0

    qlib.init(provider_uri=provider_uri, region=reg)
    print(f"qlib.init OK (provider_uri={provider_uri}, region={region})")

    try:
        from qlib.data import D

        cal = D.calendar(start_time="2020-01-01", end_time="2020-01-10")
        print(f"Sample calendar slice: {len(cal)} days")
    except Exception as e:
        print(f"Calendar query note: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
