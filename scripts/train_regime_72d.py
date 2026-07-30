#!/usr/bin/env python3
# ruff: noqa: N806, E501, E741
"""Re-train regime classifier con 72 feature multi-TF (1h + 4h + 1d).

Carica ES 1h, 4h, 1d allineati per timestamp, computa 18 feature su
ogni TF, concatena in vettore 72-dim, e riallena il ResBlock MLP.

Usage::
    uv run --frozen python scripts/train_regime_72d.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import polars as pl
import torch

from analytics.regime.ml_classifier import INPUT_DIM_MULTI, RegimeClassifier, TradingMLP
from analytics.regime.ml_features import compute_multi_tf_features


def load_aligned_data() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Load ES 1h/4h/1d aligned by date range."""

    def load_tf(tf: str) -> pl.DataFrame:
        df = pl.scan_parquet(f"data/lake/normalized/symbol=ES/tf={tf}/**/*.parquet").collect()
        df = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
        return df

    df_1h = load_tf("1h")
    df_4h = load_tf("4h")
    df_1d = load_tf("1d")
    print(f"  Loaded: 1h={len(df_1h)}, 4h={len(df_4h)}, 1d={len(df_1d)}")
    return df_1h, df_4h, df_1d


def label_by_return(close_1d: np.ndarray, forward: int = 5, n_classes: int = 8) -> list[int]:
    """Label each bar by forward return percentile."""
    labels = [-1] * len(close_1d)
    for i in range(len(close_1d) - forward):
        ret = close_1d[i + forward] / close_1d[i] - 1
        all_fwd = [close_1d[j + forward] / close_1d[j] - 1 for j in range(len(close_1d) - forward)]
        pct = sum(1 for r in all_fwd if r < ret) / max(len(all_fwd), 1)
        labels[i] = min(int(pct * n_classes), n_classes - 1)
    return labels


async def main() -> int:
    print(f"\n{'=' * 70}")
    print("TRAINING 72-DIM — Multi-TF Regime Classifier (ES 1h+4h+1d)")
    print(f"{'=' * 70}\n")

    df_1h, df_4h, df_1d = load_aligned_data()
    close_1d = df_1d["close"].to_numpy().astype(float)
    n = min(len(df_1d), len(df_1h) // 24)  # align by daily bars
    print(f"  Aligned: ~{n} daily samples")

    # Label by forward return on daily
    labels = label_by_return(close_1d, forward=5, n_classes=8)
    valid = [i for i, l in enumerate(labels) if l >= 0]
    print(f"  Valid samples: {len(valid)}")

    if len(valid) < 100:
        print("  Not enough samples")
        return 1

    # Build feature vectors — use daily TF bars directly
    # For each valid daily bar, compute multi-TF features
    X_list = []
    y_list = []
    for i in valid[:2000]:  # limit to 2000 for speed
        idx = i
        # Get context windows
        day_slice_1h = (
            df_1h.slice(max(0, idx * 24 - 60), 60) if idx * 24 < len(df_1h) else df_1h[:60]
        )
        day_slice_4h = (
            df_4h.slice(max(0, idx * 6 - 60), 60)
            if df_4h is not None and idx * 6 < len(df_4h)
            else None
        )
        day_slice_1d = df_1d.slice(max(0, idx - 60), 60)

        vec = compute_multi_tf_features(day_slice_1h, day_slice_4h, day_slice_1d)
        if vec is not None:
            # Pad to INPUT_DIM_MULTI (72)
            full = np.zeros(INPUT_DIM_MULTI, dtype=np.float32)
            full[: min(len(vec), INPUT_DIM_MULTI)] = vec[:INPUT_DIM_MULTI]
            X_list.append(full)
            y_list.append(labels[i])

    if len(X_list) < 100:
        print(f"  Not enough feature vectors: {len(X_list)}")
        return 1

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    print(f"  Feature matrix: {X.shape}")

    # Train/Test split (temporal)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # Initialize classifier with 72-dim input
    clf = RegimeClassifier(model_dir="models/regime_72d")
    clf.model = TradingMLP(input_dim=INPUT_DIM_MULTI).to(
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )
    clf.scaler = clf._make_scaler()

    # Fit scaler
    X_train_t = torch.tensor(X_train)
    clf.scaler.fit(X_train_t)
    X_train_s = clf.scaler.transform(X_train_t)
    X_test_t = torch.tensor(X_test)
    X_test_s = clf.scaler.transform(X_test_t)

    # Training
    clf.model.train()
    optimizer = torch.optim.Adam(clf.model.parameters(), lr=1e-4)
    criterion = torch.nn.CrossEntropyLoss()

    for epoch in range(50):
        optimizer.zero_grad()
        logits = clf.model(X_train_s.to(clf.model.input_layer[0].weight.device))
        loss = criterion(logits, torch.tensor(y_train, dtype=torch.long, device=logits.device))
        loss.backward()
        optimizer.step()

        if epoch % 10 == 0 or epoch == 49:
            with torch.no_grad():
                train_acc = (
                    (
                        logits.argmax(dim=1)
                        == torch.tensor(y_train, dtype=torch.long, device=logits.device)
                    )
                    .float()
                    .mean()
                    .item()
                )
                test_logits = clf.model(X_test_s.to(logits.device))
                test_acc = (
                    (
                        test_logits.argmax(dim=1)
                        == torch.tensor(y_test, dtype=torch.long, device=logits.device)
                    )
                    .float()
                    .mean()
                    .item()
                )
                print(
                    f"  Epoch {epoch:>2d}: loss={loss.item():.4f} train_acc={train_acc:.1%} test_acc={test_acc:.1%}"
                )

    # Save
    clf.model.eval()
    torch.save(clf.model.state_dict(), str(clf.model_path))
    clf.scaler.save(str(clf.scaler_path))
    info = {
        "input_dim": INPUT_DIM_MULTI,
        "output_dim": 8,
        "feature_names": [],
        "epochs": 50,
        "final_loss": float(loss.item()),
        "test_acc": test_acc,
    }
    import json

    with open(clf.info_path, "w") as f:
        json.dump(info, f)

    print(f"\n  Model saved to {clf.model_path}")
    print(f"  Test accuracy: {test_acc:.1%}")
    print("  ✅ Training 72-dim complete")
    return 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
