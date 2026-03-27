# lean-exclude: research
"""
Bitcoin neural network price-direction prediction.

This is a standalone research script (not a LEAN backtest).

What it does:
1) Downloads BTC-USD daily OHLCV from Yahoo Finance
2) Computes daily percent changes, handles inf values in volume
3) Creates sliding-window sequences (30 steps x 5 features)
4) Trains a Keras Dense neural net to predict next-step price direction
5) Evaluates accuracy on a chronological 70/30 train/test split
6) Saves trained model config + weights to Data/custom/bitcoin_model.json
   (the LEAN algorithm in lesson16_algo.py loads this file)
7) Saves plots + metrics under Research/output/lesson16/

Run:
    source venv/bin/activate
    python Algorithms/quantconnect_learning/lesson16_neural_net.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from tensorflow.keras.layers import Dense, Flatten
from tensorflow.keras.models import Sequential

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "Research" / "output" / "lesson16"
MODEL_PATH = ROOT / "Data" / "custom" / "bitcoin_model.json"

TICKER = "BTC-USD"
START = "2018-01-01"
END = "2022-01-01"
N_STEPS = 30
TRAIN_RATIO = 0.7
EPOCHS = 5
BATCH_SIZE = 32


def load_prices(ticker: str, start: str, end: str) -> pd.DataFrame:
    data = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError(f"No price data returned for {ticker} ({start} to {end})")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(f"Downloaded data missing columns: {missing}")

    return data[required].dropna()


def build_pct_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Daily percent changes with inf volume values capped."""
    pct = df.pct_change().dropna()

    inf_mask = pct["Volume"].isin([float("inf"), float("-inf")])
    if inf_mask.any():
        max_vol = pct.loc[~inf_mask, "Volume"].max()
        pct.loc[inf_mask, "Volume"] = max_vol

    return pct


def create_sequences(
    df: pd.DataFrame, n_steps: int
) -> tuple[np.ndarray, np.ndarray]:
    """Sliding-window sequences. Label = 1 if close pct_change at step i+n_steps >= 0."""
    values = df.values
    close_col = list(df.columns).index("Close")

    features, labels = [], []
    for i in range(len(df) - n_steps):
        features.append(values[i : i + n_steps])
        labels.append(1 if values[i + n_steps, close_col] >= 0 else 0)

    return np.array(features), np.array(labels)


def build_model(input_shape: tuple[int, ...]) -> Sequential:
    model = Sequential(
        [
            Dense(30, input_shape=input_shape, activation="relu"),
            Dense(20, activation="relu"),
            Flatten(),
            Dense(1, activation="sigmoid"),
        ]
    )
    model.compile(
        loss="binary_crossentropy", optimizer="adam", metrics=["accuracy", "mse"]
    )
    return model


def save_model_for_lean(model: Sequential, path: Path) -> None:
    """Save architecture + weights as JSON so the LEAN algo can reload them."""
    model_data = {
        "config": model.get_config(),
        "weights": [w.tolist() for w in model.get_weights()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(model_data, f)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {TICKER} data ({START} to {END})...")
    prices = load_prices(TICKER, START, END)
    print(f"  {len(prices)} bars loaded")

    pct = build_pct_changes(prices)
    print(f"  {len(pct)} rows after pct_change")

    X, y = create_sequences(pct, N_STEPS)
    print(f"  {len(X)} sequences of {N_STEPS} steps x {X.shape[2]} features")

    split = int(len(X) * TRAIN_RATIO)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    print(f"  Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"  Train label balance: {y_train.mean():.2%} up")
    print(f"  Test label balance:  {y_test.mean():.2%} up")

    model = build_model(X_train[0].shape)
    model.summary()

    history = model.fit(
        X_train,
        y_train,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_data=(X_test, y_test),
        verbose=1,
    )

    train_scores = model.evaluate(X_train, y_train, verbose=0)
    test_scores = model.evaluate(X_test, y_test, verbose=0)

    print(f"\nTraining accuracy:  {train_scores[1]:.2%}  (error: {1 - train_scores[1]:.2%})")
    print(f"Test accuracy:      {test_scores[1]:.2%}  (error: {1 - test_scores[1]:.2%})")

    y_hat_test = model.predict(X_test).flatten()

    # ── Save model for LEAN algorithm ──
    save_model_for_lean(model, MODEL_PATH)
    print(f"\nModel saved to {MODEL_PATH}")

    # ── Save metrics ──
    metrics_df = pd.DataFrame(
        [
            {
                "train_accuracy": train_scores[1],
                "train_error": 1 - train_scores[1],
                "train_mse": train_scores[2],
                "test_accuracy": test_scores[1],
                "test_error": 1 - test_scores[1],
                "test_mse": test_scores[2],
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "epochs": EPOCHS,
                "n_steps": N_STEPS,
            }
        ]
    )
    metrics_path = OUT_DIR / "neural_net_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False)

    # ── Save predictions ──
    results_df = pd.DataFrame(
        {
            "actual": y_test,
            "predicted_prob": y_hat_test,
            "predicted_class": (y_hat_test >= 0.5).astype(int),
        }
    )
    results_path = OUT_DIR / "predictions.csv"
    results_df.to_csv(results_path, index=False)

    # ── Plot 1: Predicted probability vs actual label ──
    fig1, ax1 = plt.subplots(figsize=(14, 6))
    ax1.plot(y_test, label="Actual (0/1)", alpha=0.7)
    ax1.plot(y_hat_test, label="Predicted probability", alpha=0.7)
    ax1.set_title("Model Performance: Predicted vs Actual")
    ax1.set_xlabel("Sample")
    ax1.set_ylabel("Value")
    ax1.legend()
    ax1.grid(alpha=0.25)
    fig1.tight_layout()
    fig1.savefig(OUT_DIR / "predicted_vs_actual.png", dpi=150)
    plt.close(fig1)

    # ── Plot 2: Training history (accuracy + loss) ──
    fig2, (ax2a, ax2b) = plt.subplots(1, 2, figsize=(14, 5))
    ax2a.plot(history.history["accuracy"], label="Train")
    ax2a.plot(history.history["val_accuracy"], label="Validation")
    ax2a.set_title("Accuracy")
    ax2a.set_xlabel("Epoch")
    ax2a.legend()
    ax2a.grid(alpha=0.25)

    ax2b.plot(history.history["loss"], label="Train")
    ax2b.plot(history.history["val_loss"], label="Validation")
    ax2b.set_title("Loss")
    ax2b.set_xlabel("Epoch")
    ax2b.legend()
    ax2b.grid(alpha=0.25)

    fig2.suptitle("Training History")
    fig2.tight_layout()
    fig2.savefig(OUT_DIR / "training_history.png", dpi=150)
    plt.close(fig2)

    # ── Plot 3: Classification results bar chart ──
    correct = int(((y_hat_test >= 0.5).astype(int) == y_test).sum())
    incorrect = len(y_test) - correct
    fig3, ax3 = plt.subplots(figsize=(6, 5))
    ax3.bar(
        ["Correct", "Incorrect"],
        [correct, incorrect],
        color=["#2ecc71", "#e74c3c"],
    )
    ax3.set_title(
        f"Test Set: {correct}/{len(y_test)} correct ({correct / len(y_test):.1%})"
    )
    ax3.set_ylabel("Count")
    fig3.tight_layout()
    fig3.savefig(OUT_DIR / "classification_results.png", dpi=150)
    plt.close(fig3)

    print("\nSaved outputs:")
    print(f"  - {metrics_path}")
    print(f"  - {results_path}")
    print(f"  - {MODEL_PATH}")
    for png in sorted(OUT_DIR.glob("*.png")):
        print(f"  - {png}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
