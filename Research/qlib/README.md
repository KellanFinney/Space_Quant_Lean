# Qlib + Space Quant Lean (editable install)

The [Qlib](https://github.com/microsoft/qlib) source lives in its **own** clone next to this repo. This folder holds **helpers** that connect Qlib research to LEAN.

## 1. Clone Qlib

From the parent of this repository:

```bash
cd ..
git clone https://github.com/microsoft/qlib.git
cd Space_Quant_Lean
```

## 2. Editable install

Use a venv with a **supported Python** (3.8–3.12 per Qlib):

```bash
source venv/bin/activate
pip install -e ../qlib
pip install -r requirements-qlib.txt
```

Verify:

```bash
python -c "import qlib; print('ok', getattr(qlib, '__version__', ''))"
```

## 3. macOS + LightGBM

If `lightgbm` fails to build:

```bash
brew install libomp
```

Then retry `pip install -r requirements-qlib.txt`.

## 4. Data

Qlib expects **prepared bin data** under e.g. `~/.qlib/qlib_data/us_data` or `cn_data`. Follow:

- [Qlib README — Data Preparation](https://github.com/microsoft/qlib#data-preparation)
- [ReadTheDocs](https://qlib.readthedocs.io/)

---

## How to use it (day-to-day)

### A. Confirm this repo + Qlib see your data

From **Space_Quant_Lean** root (with venv active):

```bash
python Research/qlib/smoke_test.py
```

- If bin data is missing, it still checks that `import qlib` works and prints where to put data.
- Optional: `QLIB_DATA=~/.qlib/qlib_data/us_data QLIB_REGION=us python Research/qlib/smoke_test.py`

### B. Run Qlib’s own examples (learning / baselines)

Work inside your **Qlib clone**, not inside Space_Quant_Lean:

```bash
cd ../qlib/examples
# Official walkthrough — same idea as qrun YAML workflows
python workflow_by_code.py
```

Or use configs under `examples/benchmarks/` with `qrun` (see Qlib README). That teaches the Dataset → model → prediction pipeline.

### C. Use Qlib from a notebook or script

Typical pattern (after `qlib.init(...)` with your `provider_uri`):

1. Build a `DatasetH` / handler (e.g. Alpha158) for your instruments and date range.
2. Fit a model (e.g. LightGBM).
3. Call `predict` to get a **DataFrame** of scores indexed by datetime × instrument.

Exact APIs match the version you installed from `../qlib`; copy patterns from `examples/workflow_by_code.py` and the benchmark YAMLs.

### D. Feed LEAN: export scores to CSV

When you have a long-format predictions table with columns like `datetime`, `instrument`, `score`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("Research/qlib").resolve()))
from export_signals_to_lean import export_long_format

# predictions_df from Qlib
paths = export_long_format(predictions_df)
print(paths)  # writes under Data/custom/qlib_signals/<ticker>_signal.csv
```

Files look like:

```text
Date,Score
2020-01-02,0.041
```

`Data/` is gitignored; files stay on your machine.

### E. Backtest in LEAN

1. Ensure equity **market data** exists under `Data/` for any tickers you trade (your existing download scripts / dashboard pipeline).
2. Add or use a LEAN algorithm that reads `Data/custom/qlib_signals/<ticker>_signal.csv` via `PythonData` and maps **Score** to position size or long/flat rules.

The exact algorithm file can live under `Algorithms/` next to your other strategies; wire it the same way as other custom CSV feeds (see `lesson13` VIX `PythonData` for the pattern).

---

## Interpreting `examples/workflow_by_code.py` output

If the script **ends with portfolio metrics** (benchmark return, excess return with/without cost), the pipeline **succeeded**. Rough map of what you saw:

| What you saw | Meaning |
|--------------|---------|
| Zip download + unzip under `~/.qlib/qlib_data/cn_data` | Demo **China** daily bin data (Yahoo-sourced; quality disclaimer is normal). |
| `[5 rows x 159 columns]` + factor names like `KMID`, `LABEL0` | **Alpha158**-style feature matrix + label loaded correctly. |
| LightGBM training + early stopping | **LGBModel** trained; `pred.pkl` / prediction `score` block is the model output. |
| `IC`, `ICIR`, `Rank IC` | **Information coefficient** stats: how aligned predictions are with realized returns (higher \|IC\| is better; sign matters). |
| `port_analysis_1day.pkl` + risk tables | **Qlib backtest** inside their simulator (not LEAN): benchmark vs strategy excess return, with optional costs. |
| `mlruns` / MLflow messages | Experiment tracking wrote under `./mlruns` in the **current working directory** (here `qlib/examples/`). |

**Usually safe to ignore (noisy but common):**

- **Gym** warnings — RL-related imports; this workflow is **not** RL. You can `pip install gymnasium` to quiet some stacks, or ignore.
- **CatBoost / XGBoost / PyTorch skipped** — optional model imports; **LightGBM** still ran.
- **`$close` / `factor.day.bin` / `adjusted_price`** — exchange/backtest edge cases on demo data; does not mean the ML part failed.
- **`Mean of empty slice`** — some backtest steps had no positions or empty windows.
- **`load calendar` / future calendar** — calendar extension; see Qlib docs if you need true future dates.

**Optional cleanups**

- Use **Python 3.10–3.12** for Qlib + ML stacks (you ran with 3.14 from `Space_Quant_Lean/venv`; it worked here but is outside Qlib’s documented matrix).
- Install extras only if you need those models: `pip install catboost xgboost torch` (large).

---

## Files in this folder

| File | Purpose |
|------|---------|
| `smoke_test.py` | Verify `qlib` import + optional `qlib.init` against local bin data |
| `export_signals_to_lean.py` | `export_long_format(df)` → per-ticker CSVs under `Data/custom/qlib_signals/` |

---

## Mental model

| Layer | Tool |
|-------|------|
| Research, factors, ML, IC, backtest analytics | **Qlib** (clone + notebooks / `examples/`) |
| Execution simulation, orders, LEAN-specific algos | **LEAN** in Docker + this repo’s `Algorithms/` |

Qlib does not replace LEAN here; it **generates signals** you export and optionally consume in LEAN.
