import json
import os
import re
import subprocess
import sys
import threading
import uuid
import zipfile
from datetime import datetime
from glob import glob
from pathlib import Path

import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
ALGORITHMS_DIR = BASE_DIR / "Algorithms"
RESULTS_DIR = BASE_DIR / "Results"
DATA_DIR = BASE_DIR / "Data"
CONFIG_PATH = BASE_DIR / "config.json"

# In-memory store for running backtest jobs
backtest_jobs = {}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("dashboard.html")


# ---------------------------------------------------------------------------
# API — algorithm discovery
# ---------------------------------------------------------------------------

@app.route("/api/algorithms")
def list_algorithms():
    """Return every .py file under Algorithms/, grouped by subfolder."""
    algos = []
    for py_file in sorted(ALGORITHMS_DIR.rglob("*.py")):
        rel = py_file.relative_to(ALGORITHMS_DIR)
        algos.append({
            "path": str(rel),
            "name": py_file.stem,
            "dir": str(rel.parent) if str(rel.parent) != "." else "",
        })
    return jsonify(algos)


# ---------------------------------------------------------------------------
# API — list available result sets
# ---------------------------------------------------------------------------

@app.route("/api/results")
def list_results():
    """Return folders inside Results/ that contain a *-summary.json."""
    result_sets = []
    if RESULTS_DIR.exists():
        for folder in sorted(RESULTS_DIR.iterdir()):
            if folder.is_dir():
                summaries = list(folder.glob("*-summary.json"))
                if summaries:
                    algo_name = summaries[0].stem.replace("-summary", "")
                    result_sets.append({
                        "folder": folder.name,
                        "algorithm": algo_name,
                    })
    return jsonify(result_sets)


# ---------------------------------------------------------------------------
# API — load a single result set
# ---------------------------------------------------------------------------

@app.route("/api/results/<path:strategy>")
def get_results(strategy):
    """Load and return parsed backtest results for a strategy folder."""
    results_dir = RESULTS_DIR / strategy
    if not results_dir.exists():
        return jsonify({"error": f"Results folder '{strategy}' not found"}), 404

    summaries = list(results_dir.glob("*-summary.json"))
    if not summaries:
        return jsonify({"error": "No summary JSON found"}), 404

    algo_name = summaries[0].stem.replace("-summary", "")

    data = {"algorithm": algo_name, "strategy": strategy}

    # Summary JSON (charts, statistics, algorithm config)
    summary_path = results_dir / f"{algo_name}-summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            data["summary"] = json.load(f)

    # Main results JSON (orders, profit, etc.)
    main_path = results_dir / f"{algo_name}.json"
    if main_path.exists():
        with open(main_path) as f:
            data["main"] = json.load(f)

    # Log file
    log_path = results_dir / f"{algo_name}-log.txt"
    if log_path.exists():
        with open(log_path) as f:
            data["log"] = f.read()

    # Order events
    orders_path = results_dir / f"{algo_name}-order-events.json"
    if orders_path.exists():
        with open(orders_path) as f:
            data["order_events"] = json.load(f)

    # Parse out useful bits
    data["statistics"] = _extract_statistics(data)
    data["equity_curve"] = _extract_equity_curve(data)
    data["benchmark_curve"] = _extract_benchmark_curve(data)
    data["daily_performance"] = _extract_daily_performance(data)
    data["custom_charts"] = _extract_custom_charts(data)
    data["orders"] = _extract_orders(data)

    # Don't send raw summary/main blobs to the frontend — too large
    data.pop("summary", None)
    data.pop("main", None)
    data.pop("order_events", None)

    return jsonify(data)


# ---------------------------------------------------------------------------
# API — run a backtest
# ---------------------------------------------------------------------------

@app.route("/api/run-backtest", methods=["POST"])
def run_backtest():
    """Kick off a LEAN backtest in Docker for the given algorithm."""
    body = request.json or {}
    algo_path = body.get("algorithm")  # e.g. "space_strategy/rklb_swing.py"
    if not algo_path:
        return jsonify({"error": "Missing 'algorithm' field"}), 400

    full_algo = ALGORITHMS_DIR / algo_path
    if not full_algo.exists():
        return jsonify({"error": f"Algorithm not found: {algo_path}"}), 404

    job_id = str(uuid.uuid4())[:8]

    # Determine output folder name and class name
    algo_dir = str(Path(algo_path).parent) if str(Path(algo_path).parent) != "." else Path(algo_path).stem
    class_name = _detect_class_name(full_algo)
    result_folder = algo_dir if algo_dir != "." else Path(algo_path).stem

    # Build a config for this run
    run_config = _build_config(algo_path, class_name, result_folder)

    backtest_jobs[job_id] = {
        "status": "running",
        "algorithm": algo_path,
        "result_folder": result_folder,
        "log": "",
        "started": datetime.now().isoformat(),
    }

    thread = threading.Thread(
        target=_run_docker_backtest,
        args=(job_id, run_config, result_folder),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/backtest-status/<job_id>")
def backtest_status(job_id):
    """Poll the status of a running backtest."""
    job = backtest_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


# ---------------------------------------------------------------------------
# Helpers — result parsing
# ---------------------------------------------------------------------------

def _extract_statistics(data):
    try:
        return data["summary"]["statistics"]
    except (KeyError, TypeError):
        return {}


def _extract_equity_curve(data):
    try:
        values = data["summary"]["charts"]["Strategy Equity"]["series"]["Equity"]["values"]
        return [{"date": _ts_to_date(p[0]), "value": p[4]} for p in values]
    except (KeyError, TypeError):
        return []


def _extract_benchmark_curve(data):
    try:
        values = data["summary"]["charts"]["Benchmark"]["series"]["Benchmark"]["values"]
        return [{"date": _ts_to_date(p[0]), "value": p[4]} for p in values]
    except (KeyError, TypeError):
        return []


def _extract_daily_performance(data):
    try:
        values = data["summary"]["charts"]["Strategy Equity"]["series"]["Daily Performance"]["values"]
        return [{"date": _ts_to_date(p[0]), "value": p[4]} for p in values]
    except (KeyError, TypeError):
        return []


def _extract_custom_charts(data):
    """Pull any user-plotted charts (e.g. SMA overlays) from the summary."""
    charts = {}
    try:
        all_charts = data["summary"]["charts"]
        skip = {"Strategy Equity", "Benchmark", "Capacity", "Drawdown",
                "Portfolio Margin", "Portfolio Turnover"}
        for name, chart in all_charts.items():
            if name in skip:
                continue
            series_out = {}
            for series_name, series_data in chart.get("series", {}).items():
                vals = series_data.get("values", [])
                series_out[series_name] = [
                    {"date": _ts_to_date(p[0]), "value": p[4]} for p in vals
                ]
            if series_out:
                charts[name] = series_out
    except (KeyError, TypeError):
        pass
    return charts


def _extract_orders(data):
    orders = []
    try:
        raw_orders = data["main"].get("Orders", {})
        for oid, o in raw_orders.items():
            orders.append({
                "id": oid,
                "symbol": o.get("Symbol", {}).get("Value", ""),
                "type": _order_type_name(o.get("Type", 0)),
                "direction": "Buy" if o.get("Quantity", 0) > 0 else "Sell",
                "quantity": o.get("Quantity", 0),
                "price": o.get("Price", 0),
                "value": round(abs(o.get("Quantity", 0)) * o.get("Price", 0), 2),
                "time": o.get("Time", ""),
                "status": _order_status_name(o.get("Status", 0)),
                "tag": o.get("Tag", ""),
            })
    except (KeyError, TypeError):
        pass
    return orders


def _ts_to_date(ts):
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (OSError, ValueError, TypeError):
        return ""


def _order_type_name(t):
    return {0: "Market", 1: "Limit", 2: "StopMarket", 3: "StopLimit",
            5: "MarketOnOpen", 6: "MarketOnClose"}.get(t, str(t))


def _order_status_name(s):
    return {0: "New", 1: "Submitted", 2: "PartiallyFilled", 3: "Filled",
            5: "Canceled", 6: "None", 7: "Invalid"}.get(s, str(s))


# ---------------------------------------------------------------------------
# Helpers — Docker backtest runner
# ---------------------------------------------------------------------------

def _detect_class_name(py_path):
    """Parse the .py file to find the QCAlgorithm subclass name."""
    with open(py_path) as f:
        content = f.read()
    match = re.search(r"class\s+(\w+)\s*\(", content)
    return match.group(1) if match else "MyAlgorithm"


# ---------------------------------------------------------------------------
# Helpers — auto-detect tickers & download missing data
# ---------------------------------------------------------------------------

EQUITY_DATA_DIR = DATA_DIR / "equity" / "usa" / "daily"

def _detect_tickers(py_path):
    """Parse an algorithm .py file for AddEquity / add_equity calls and return ticker list."""
    with open(py_path) as f:
        content = f.read()
    # Matches both self.AddEquity("SPY", ...) and self.add_equity("SPY", ...)
    pattern = r'\.(?:AddEquity|add_equity)\s*\(\s*["\']([A-Z0-9.]+)["\']'
    return list(set(re.findall(pattern, content)))


def _get_missing_tickers(tickers):
    """Return tickers whose .zip is missing or contains corrupt/empty data."""
    missing = []
    for t in tickers:
        zip_path = EQUITY_DATA_DIR / f"{t.lower()}.zip"
        if not zip_path.exists():
            missing.append(t)
            continue
        if _is_corrupt_data(zip_path):
            missing.append(t)
    return missing


def _is_corrupt_data(zip_path):
    """Check if a LEAN data zip has empty or malformed rows."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():
                with z.open(name) as f:
                    first_line = f.readline().decode().strip()
                    if not first_line:
                        return True
                    fields = first_line.split(",")
                    # Valid LEAN row: datetime,open,high,low,close,volume (6 fields, all non-empty)
                    if len(fields) < 6 or any(f.strip() == "" for f in fields):
                        return True
        return False
    except Exception:
        return True


def _download_ticker(ticker, start="2000-01-01", end="2026-12-31"):
    """Download a single ticker from Yahoo Finance and save in LEAN format."""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(start=start, end=end, interval="1d")
        if data.empty:
            return False, f"No data found for {ticker}"

        data = data.reset_index()
        EQUITY_DATA_DIR.mkdir(parents=True, exist_ok=True)

        lean_data = pd.DataFrame({
            "datetime": data["Date"].dt.strftime("%Y%m%d 00:00"),
            "open":   (data["Open"]  * 10000).round().astype(int),
            "high":   (data["High"]  * 10000).round().astype(int),
            "low":    (data["Low"]   * 10000).round().astype(int),
            "close":  (data["Close"] * 10000).round().astype(int),
            "volume": data["Volume"].astype(int),
        })

        zip_path = EQUITY_DATA_DIR / f"{ticker.lower()}.zip"
        csv_content = lean_data.to_csv(index=False, header=False)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{ticker.lower()}.csv", csv_content)

        return True, f"Downloaded {len(lean_data)} rows for {ticker}"
    except Exception as e:
        return False, f"Failed to download {ticker}: {e}"


def _ensure_ticker_data(py_path):
    """Detect tickers in an algorithm and download any missing data. Returns log lines."""
    tickers = _detect_tickers(py_path)
    if not tickers:
        return [f"No equity tickers detected in {py_path.name}"]

    missing = _get_missing_tickers(tickers)
    log_lines = [f"Detected tickers: {', '.join(sorted(tickers))}"]

    if not missing:
        log_lines.append("All ticker data already present.")
        return log_lines

    log_lines.append(f"Missing data for: {', '.join(sorted(missing))}  — downloading...")
    for t in sorted(missing):
        ok, msg = _download_ticker(t)
        log_lines.append(f"  {'OK' if ok else 'FAIL'}: {msg}")

    return log_lines


def _build_config(algo_path, class_name, result_folder):
    """Build a LEAN config dict for the given algorithm."""
    base = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            base = json.load(f)

    base["algorithm-type-name"] = class_name
    base["algorithm-language"] = "Python"
    base["algorithm-location"] = f"/Lean/Algorithm/{algo_path}"
    base["results-destination-folder"] = f"/Results/{result_folder}"
    return base


def _run_docker_backtest(job_id, config, result_folder):
    """Execute the LEAN Docker container and capture output."""
    job = backtest_jobs[job_id]

    # Auto-download any missing ticker data before running
    algo_file = ALGORITHMS_DIR / job["algorithm"]
    try:
        job["status"] = "downloading_data"
        data_log = _ensure_ticker_data(algo_file)
        job["log"] = "\n".join(data_log) + "\n\n"
    except Exception as e:
        job["log"] += f"Data download error: {e}\n"

    job["status"] = "running"

    # Write temporary config
    tmp_config = BASE_DIR / f".tmp_config_{job_id}.json"
    with open(tmp_config, "w") as f:
        json.dump(config, f, indent=2)

    # Ensure result directory exists
    result_dir = RESULTS_DIR / result_folder
    result_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{ALGORITHMS_DIR}:/Lean/Algorithm",
        "-v", f"{DATA_DIR}:/Lean/Data",
        "-v", f"{result_dir}:/Results/{result_folder}",
        "-v", f"{tmp_config}:/Lean/Launcher/bin/Debug/config.json",
        "lean-nltk",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        job["log"] = proc.stdout + proc.stderr
        job["exit_code"] = proc.returncode
        job["status"] = "completed" if proc.returncode == 0 else "failed"
    except subprocess.TimeoutExpired:
        job["status"] = "timeout"
        job["log"] += "\nBacktest timed out after 10 minutes."
    except Exception as e:
        job["status"] = "error"
        job["log"] += f"\n{e}"
    finally:
        tmp_config.unlink(missing_ok=True)
        job["finished"] = datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
