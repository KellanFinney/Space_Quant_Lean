# lean-exclude: research
"""
SPY linear regression research using SMA20 + Bollinger Bands.

This is a standalone research script (not a LEAN backtest).

What it does:
1) Downloads SPY daily closes from Yahoo Finance
2) Computes SMA20 + Bollinger Bands (20-day, 2 std)
3) Trains a simple linear regression (numpy least squares) to predict next-day return
4) Compares model vs naive baseline (predict 0 return)
5) Reports MAE / RMSE / R^2 + directional hit-rate on a chronological holdout set
6) Builds a simple long/flat test strategy from predicted returns
5) Saves plots + metrics under Research/output/linear_regression_predictions/

Run:
    source venv/bin/activate
    python Algorithms/linear_regression_predictions/boilingerBand_SMA20.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "Research" / "output" / "linear_regression_predictions"

TICKER = "SPY"
START = "2015-01-01"
END = "2026-01-01"
WINDOW = 20
STD_MULT = 2.0
TRAIN_RATIO = 0.8


def load_prices(ticker: str, start: str, end: str) -> pd.DataFrame:
    data = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError(f"No price data returned for {ticker} ({start} to {end})")

    # yfinance may return either:
    # - simple columns: Open, High, Low, Close, ...
    # - MultiIndex columns: (field, ticker)
    if isinstance(data.columns, pd.MultiIndex):
        if "Close" not in data.columns.get_level_values(0):
            raise ValueError("Downloaded data missing Close column.")
        close = data["Close"]
    else:
        if "Close" not in data.columns:
            raise ValueError("Downloaded data missing Close column.")
        close = data["Close"]

    # Force a 1D Series regardless of whether close came back as DataFrame/Series.
    if isinstance(close, pd.DataFrame):
        if close.shape[1] == 0:
            raise ValueError("Close data has no columns.")
        close = close.iloc[:, 0]

    close = pd.to_numeric(close, errors="coerce")
    out = pd.DataFrame({"close": close}).dropna()
    return out


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ret_1d"] = out["close"].pct_change()
    out["ret_5d"] = out["close"].pct_change(5)
    out["sma20"] = out["close"].rolling(WINDOW).mean()
    out["std20"] = out["close"].rolling(WINDOW).std()
    out["bb_upper"] = out["sma20"] + STD_MULT * out["std20"]
    out["bb_lower"] = out["sma20"] - STD_MULT * out["std20"]
    out["bb_width"] = out["bb_upper"] - out["bb_lower"]
    out["pct_b"] = (out["close"] - out["bb_lower"]) / out["bb_width"].replace(0, np.nan)
    out["close_to_sma"] = out["close"] / out["sma20"] - 1.0
    out["zscore"] = (out["close"] - out["sma20"]) / out["std20"].replace(0, np.nan)
    out["bb_width_pct"] = out["bb_width"] / out["sma20"].replace(0, np.nan)

    # Target: predict next day's return
    out["target_next_return"] = out["ret_1d"].shift(-1)
    out = out.dropna().copy()
    return out


def fit_linear_regression(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    # Add intercept term
    X_design = np.column_stack([np.ones(len(X)), X])
    coeffs, _, _, _ = np.linalg.lstsq(X_design, y, rcond=None)
    return coeffs


def predict_linear_regression(X: np.ndarray, coeffs: np.ndarray) -> np.ndarray:
    X_design = np.column_stack([np.ones(len(X)), X])
    return X_design @ coeffs


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return {"mae": mae, "rmse": rmse, "r2": r2}


def directional_hit_rate(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Share of times predicted sign matches actual sign.

    Neutral predictions (exactly 0) are excluded from scoring, so a baseline that
    predicts 0 return is not unfairly forced to 0% hit-rate.
    """
    if len(y_true) == 0:
        return 0.0
    true_sign = np.sign(y_true)
    pred_sign = np.sign(y_pred)
    active = pred_sign != 0
    if not np.any(active):
        return float("nan")
    return float(np.mean(true_sign[active] == pred_sign[active]))


def coverage_rate(y_pred: np.ndarray) -> float:
    """Fraction of observations with non-neutral directional prediction."""
    if len(y_pred) == 0:
        return 0.0
    return float(np.mean(np.sign(y_pred) != 0))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = load_prices(TICKER, START, END)
    data = build_features(prices)

    # Use stationary features to avoid inflated price-level fits.
    feature_cols = ["ret_1d", "ret_5d", "close_to_sma", "zscore", "bb_width_pct", "pct_b"]
    X = data[feature_cols].values
    y = data["target_next_return"].values

    split = int(len(data) * TRAIN_RATIO)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    idx_test = data.index[split:]

    coeffs = fit_linear_regression(X_train, y_train)
    y_pred = predict_linear_regression(X_test, coeffs)
    baseline_zero_pred = np.zeros_like(y_test)  # naive: tomorrow return = 0
    baseline_mean_pred = np.full_like(y_test, float(np.mean(y_train)))

    # Directional baselines for fair hit-rate comparison
    majority_sign = 1.0 if np.mean(y_train > 0) >= 0.5 else -1.0
    baseline_majority_sign_pred = np.full_like(y_test, majority_sign)
    baseline_prev_sign_pred = np.sign(data["ret_1d"].values[split:])

    model_metrics = metrics(y_test, y_pred)
    baseline_zero_metrics = metrics(y_test, baseline_zero_pred)
    baseline_mean_metrics = metrics(y_test, baseline_mean_pred)
    model_hit = directional_hit_rate(y_test, y_pred)
    baseline_majority_hit = directional_hit_rate(y_test, baseline_majority_sign_pred)
    baseline_prev_sign_hit = directional_hit_rate(y_test, baseline_prev_sign_pred)
    baseline_zero_hit = directional_hit_rate(y_test, baseline_zero_pred)
    model_coverage = coverage_rate(y_pred)

    # Save metrics + coefficients
    coeff_df = pd.DataFrame(
        {
            "feature": ["intercept"] + feature_cols,
            "coefficient": coeffs,
        }
    )
    coeff_path = OUT_DIR / "linear_regression_coefficients.csv"
    coeff_df.to_csv(coeff_path, index=False)

    metrics_path = OUT_DIR / "linear_regression_metrics.csv"
    pd.DataFrame(
        [
            {
                "model_mae": model_metrics["mae"],
                "model_rmse": model_metrics["rmse"],
                "model_r2": model_metrics["r2"],
                "model_hit_rate": model_hit,
                "model_coverage_rate": model_coverage,
                "baseline_zero_mae": baseline_zero_metrics["mae"],
                "baseline_zero_rmse": baseline_zero_metrics["rmse"],
                "baseline_zero_r2": baseline_zero_metrics["r2"],
                "baseline_zero_hit_rate": baseline_zero_hit,
                "baseline_mean_mae": baseline_mean_metrics["mae"],
                "baseline_mean_rmse": baseline_mean_metrics["rmse"],
                "baseline_mean_r2": baseline_mean_metrics["r2"],
                "baseline_majority_hit_rate": baseline_majority_hit,
                "baseline_prev_sign_hit_rate": baseline_prev_sign_hit,
            }
        ]
    ).to_csv(metrics_path, index=False)

    # Simple long/flat strategy from predicted returns (test set only)
    signal = (y_pred > 0).astype(float)
    strat_rets = signal * y_test
    bh_rets = y_test
    strat_curve = np.cumprod(1.0 + strat_rets)
    bh_curve = np.cumprod(1.0 + bh_rets)

    pred_df = pd.DataFrame(
        {
            "date": idx_test,
            "actual_next_return": y_test,
            "predicted_next_return": y_pred,
            "baseline_zero_return": baseline_zero_pred,
            "baseline_mean_return": baseline_mean_pred,
            "baseline_majority_sign": np.sign(baseline_majority_sign_pred).astype(int),
            "baseline_prev_sign": np.sign(baseline_prev_sign_pred).astype(int),
            "signal_long_if_pred_gt_0": signal.astype(int),
            "strategy_return": strat_rets,
            "buy_hold_return": bh_rets,
            "strategy_curve": strat_curve,
            "buy_hold_curve": bh_curve,
        }
    )
    preds_path = OUT_DIR / "predictions.csv"
    pred_df.to_csv(preds_path, index=False)

    # Plot 1: SPY close + SMA20 + Bollinger Bands
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(data.index, data["close"], label="Close", linewidth=1.2)
    ax1.plot(data.index, data["sma20"], label="SMA20", linewidth=1.2)
    ax1.plot(data.index, data["bb_upper"], label="BB Upper", linestyle="--", linewidth=1.0)
    ax1.plot(data.index, data["bb_lower"], label="BB Lower", linestyle="--", linewidth=1.0)
    ax1.set_title("SPY Close with SMA20 + Bollinger Bands")
    ax1.set_ylabel("Price")
    ax1.grid(alpha=0.25)
    ax1.legend()
    fig1.tight_layout()
    fig1.savefig(OUT_DIR / "spy_sma20_bollinger.png", dpi=150)
    plt.close(fig1)

    # Plot 2: Actual vs predicted returns on test set
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    ax2.plot(idx_test, y_test, label="Actual next return", linewidth=1.1)
    ax2.plot(idx_test, y_pred, label="Predicted next return", linewidth=1.1)
    ax2.axhline(0, color="black", linewidth=0.8, alpha=0.6)
    ax2.set_title("Linear Regression: Actual vs Predicted Next-Day Return (Test Set)")
    ax2.set_ylabel("Return")
    ax2.grid(alpha=0.25)
    ax2.legend()
    fig2.tight_layout()
    fig2.savefig(OUT_DIR / "actual_vs_predicted.png", dpi=150)
    plt.close(fig2)

    # Plot 3: Scatter predicted vs actual returns
    fig3, ax3 = plt.subplots(figsize=(7, 7))
    ax3.scatter(y_test, y_pred, alpha=0.45)
    lo = float(min(y_test.min(), y_pred.min()))
    hi = float(max(y_test.max(), y_pred.max()))
    ax3.plot([lo, hi], [lo, hi], linestyle="--", linewidth=1.0, label="Ideal fit")
    ax3.set_xlabel("Actual next return")
    ax3.set_ylabel("Predicted next return")
    ax3.set_title("Predicted vs Actual Return Scatter")
    ax3.grid(alpha=0.25)
    ax3.legend()
    fig3.tight_layout()
    fig3.savefig(OUT_DIR / "predicted_vs_actual_scatter.png", dpi=150)
    plt.close(fig3)

    # Plot 4: Strategy curve vs buy-and-hold on test period
    fig4, ax4 = plt.subplots(figsize=(12, 6))
    ax4.plot(idx_test, strat_curve, label="Model long/flat", linewidth=1.4)
    ax4.plot(idx_test, bh_curve, label="Buy & Hold (test window)", linewidth=1.2)
    ax4.set_title("Test-Window Equity Curve (Model Signal vs Buy & Hold)")
    ax4.set_ylabel("Growth of $1")
    ax4.grid(alpha=0.25)
    ax4.legend()
    fig4.tight_layout()
    fig4.savefig(OUT_DIR / "strategy_vs_buyhold.png", dpi=150)
    plt.close(fig4)

    print("Saved outputs:")
    print(f"  - {coeff_path}")
    print(f"  - {metrics_path}")
    print(f"  - {preds_path}")
    print(f"  - {OUT_DIR / 'spy_sma20_bollinger.png'}")
    print(f"  - {OUT_DIR / 'actual_vs_predicted.png'}")
    print(f"  - {OUT_DIR / 'predicted_vs_actual_scatter.png'}")
    print(f"  - {OUT_DIR / 'strategy_vs_buyhold.png'}")
    print("\nMetrics:")
    print("  Model (next-day return)")
    print(f"    MAE : {model_metrics['mae']:.6f}")
    print(f"    RMSE: {model_metrics['rmse']:.6f}")
    print(f"    R^2 : {model_metrics['r2']:.4f}")
    print(f"    Hit : {model_hit:.2%}")
    print(f"    Coverage (non-neutral): {model_coverage:.2%}")
    print("  Baseline (predict 0 return)")
    print(f"    MAE : {baseline_zero_metrics['mae']:.6f}")
    print(f"    RMSE: {baseline_zero_metrics['rmse']:.6f}")
    print(f"    R^2 : {baseline_zero_metrics['r2']:.4f}")
    print(f"    Hit : {baseline_zero_hit:.2%}" if not np.isnan(baseline_zero_hit) else "    Hit : N/A (all neutral)")
    print("  Baseline (predict train-mean return)")
    print(f"    MAE : {baseline_mean_metrics['mae']:.6f}")
    print(f"    RMSE: {baseline_mean_metrics['rmse']:.6f}")
    print(f"    R^2 : {baseline_mean_metrics['r2']:.4f}")
    print("  Directional baselines")
    print(f"    Majority-sign hit : {baseline_majority_hit:.2%}")
    print(f"    Prev-day-sign hit : {baseline_prev_sign_hit:.2%}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
