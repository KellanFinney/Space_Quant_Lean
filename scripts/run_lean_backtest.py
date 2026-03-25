#!/usr/bin/env python3
"""
Run a LEAN Docker backtest for any algorithm under Algorithms/.

Engine settings come from lean.engine.json (and optional config.local.json).
Algorithm class, path, benchmark, and results folder are chosen per run — no
single hardcoded strategy in config.

Usage:
  python scripts/run_lean_backtest.py quantconnect_learning/lesson10.py
  python scripts/run_lean_backtest.py space_swing_strategy/rklb_swing.py --benchmark RKLB
  python scripts/run_lean_backtest.py path/to/algo.py --class-name MyBot --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lean_config import build_run_config, detect_class_name, result_folder_for_algorithm


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LEAN backtest in Docker with merged config")
    parser.add_argument(
        "algorithm",
        help="Path under Algorithms/, e.g. quantconnect_learning/lesson10.py",
    )
    parser.add_argument("--class-name", help="QCAlgorithm class name (default: auto-detect from file)")
    parser.add_argument("--benchmark", help="Benchmark symbol (default: first AddEquity ticker, else SPY)")
    parser.add_argument("--image", default="lean-nltk", help="Docker image tag (default: lean-nltk)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print merged config JSON and docker command; do not run",
    )
    args = parser.parse_args()

    algo_path = args.algorithm.replace("\\", "/").lstrip("/")
    rf = result_folder_for_algorithm(algo_path)
    cn = args.class_name or detect_class_name(ROOT / "Algorithms" / algo_path)

    try:
        cfg = build_run_config(
            algo_path,
            class_name=args.class_name,
            result_folder=rf,
            benchmark=args.benchmark,
        )
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    if args.class_name is None:
        print(f"Using class: {cn}", file=sys.stderr)

    result_dir = ROOT / "Results" / rf
    result_dir.mkdir(parents=True, exist_ok=True)

    algo_mount = ROOT / "Algorithms"
    data_mount = ROOT / "Data"
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{algo_mount}:/Lean/Algorithm",
        "-v",
        f"{data_mount}:/Lean/Data",
        "-v",
        f"{result_dir}:/Results/{rf}",
    ]

    if args.dry_run:
        print(json.dumps(cfg, indent=2))
        print("\nDocker:", " ".join(cmd + ["-v", "<tmp>:/Lean/Launcher/bin/Debug/config.json", args.image]))
        return 0

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        dir=str(ROOT),
    ) as tmp:
        json.dump(cfg, tmp, indent=2)
        tmp_path = tmp.name

    cmd.extend(["-v", f"{tmp_path}:/Lean/Launcher/bin/Debug/config.json", args.image])

    try:
        proc = subprocess.run(cmd, cwd=str(ROOT))
        return proc.returncode
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
