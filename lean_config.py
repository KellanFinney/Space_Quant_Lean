"""
Shared LEAN configuration: engine settings + per-run algorithm selection.

Algorithm type, path, benchmark, and results folder are chosen at run time
(dashboard, CLI script), not hardcoded in a single global config file.
"""
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ALGORITHMS_DIR = BASE_DIR / "Algorithms"
ENGINE_CONFIG_PATH = BASE_DIR / "lean.engine.json"
LEGACY_CONFIG_PATH = BASE_DIR / "config.json"
LOCAL_OVERRIDES_PATH = BASE_DIR / "config.local.json"

# Keys that must always come from the selected algorithm / run, never from disk alone
_ALGO_KEYS = (
    "algorithm-type-name",
    "algorithm-location",
    "benchmark",
)


def _strip_algo_keys(cfg: dict) -> dict:
    out = dict(cfg)
    for k in _ALGO_KEYS:
        out.pop(k, None)
    return out


def load_engine_config() -> dict:
    """
    Load engine-only JSON: lean.engine.json, else legacy config.json (stripped).
    Optional config.local.json merges on top (still strips algorithm keys from merge).
    """
    base = {}
    if ENGINE_CONFIG_PATH.exists():
        with open(ENGINE_CONFIG_PATH) as f:
            base = json.load(f)
    elif LEGACY_CONFIG_PATH.exists():
        with open(LEGACY_CONFIG_PATH) as f:
            base = json.load(f)
    base = _strip_algo_keys(base)

    if LOCAL_OVERRIDES_PATH.exists():
        with open(LOCAL_OVERRIDES_PATH) as f:
            overrides = json.load(f)
        base.update(_strip_algo_keys(overrides))

    base.setdefault("algorithm-language", "Python")
    return base


def detect_class_name(py_path: Path) -> str:
    """Parse the .py file to find the first QCAlgorithm subclass name."""
    with open(py_path) as f:
        content = f.read()
    match = re.search(r"class\s+(\w+)\s*\(\s*QCAlgorithm\s*\)", content)
    if match:
        return match.group(1)
    match = re.search(r"class\s+(\w+)\s*\(", content)
    return match.group(1) if match else "MyAlgorithm"


def infer_benchmark_symbol(py_path: Path) -> str:
    """First AddEquity/add_equity ticker in the file, else SPY."""
    with open(py_path) as f:
        content = f.read()
    pattern = r'\.(?:AddEquity|add_equity)\s*\(\s*["\']([A-Z0-9.]+)["\']'
    found = re.findall(pattern, content)
    return found[0] if found else "SPY"


def result_folder_for_algorithm(algo_rel_path: str) -> str:
    """Results subdirectory: parent_stem/stem or stem for top-level files."""
    p = Path(algo_rel_path)
    parent = str(p.parent)
    stem = p.stem
    if parent and parent != ".":
        return f"{parent}/{stem}"
    return stem


def build_run_config(
    algo_rel_path: str,
    class_name: str | None = None,
    result_folder: str | None = None,
    benchmark: str | None = None,
) -> dict:
    """
    Full LEAN config dict for one backtest run.

    algo_rel_path: path relative to Algorithms/, e.g. space_swing_strategy/rklb_swing.py
    """
    full_algo = ALGORITHMS_DIR / algo_rel_path
    if not full_algo.exists():
        raise FileNotFoundError(f"Algorithm not found: {algo_rel_path}")

    base = load_engine_config()
    cn = class_name or detect_class_name(full_algo)
    rf = result_folder or result_folder_for_algorithm(algo_rel_path)
    bm = benchmark or infer_benchmark_symbol(full_algo)

    base["algorithm-type-name"] = cn
    base["algorithm-language"] = "Python"
    base["algorithm-location"] = f"/Lean/Algorithm/{algo_rel_path}"
    base["benchmark"] = bm
    base["results-destination-folder"] = f"/Results/{rf}"
    return base
