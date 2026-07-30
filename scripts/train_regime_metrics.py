#!/usr/bin/env python3
# ruff: noqa: N806, E741
"""Retrain 72-dim classifier with REAL metric-based regime labels.

Usage::
    uv run --frozen python scripts/train_regime_metrics.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.regime.ml_classifier import INPUT_DIM_MULTI, RegimeClassifier, TradingMLP
from analytics.regime.ml_features import compute_multi_tf_features
from analytics.regime.regime_labeler import label_by_metrics


async def main() -> int:
    print(f"\n{'=' * 70}")
    print("TRAINING 72-DIM — Metric-based Regime Labels (ES 1h+4h+1d)")
    print(f"{'=' * 70}\n")

    # Load all 3 TFs
    dfs = {}
    for tf in ["1h", "4h", "1d"]:
        df = pl.scan_parquet(f"data/lake/normalized/symbol=ES/tf={tf}/**/*.parquet").collect()
        dfs[tf] = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
    print(f"  1h: {len(dfs['1h'])} | 4h: {len(dfs['4h'])} | 1d: {len(dfs['1d'])}")

    # Label daily bars using metric-based regime on 1h closest to daily close
    dfs["1d"]["close"].to_numpy().astype(float)
    labels = []
    for i in range(len(dfs["1d"])):
        if i < len(dfs["1h"]) // 24:
            # Use the last 1h bar of each day for feature computation
            day_1h = dfs["1h"].slice(max(0, i * 24 - 60), 60)
            day_4h = dfs["4h"].slice(max(0, i * 6 - 60), 60)
            day_1d = dfs["1d"].slice(max(0, i - 60), 60)

            vec = compute_multi_tf_features(day_1h, day_4h, day_1d)
            if vec is not None:
                # Label from daily features (using metric-based regime)
                from analytics.regime.ml_features import compute_all_features

                feat_1d = compute_all_features(day_1d)
                daily_labels = label_by_metrics(feat_1d)
                label = daily_labels[-1] if daily_labels else 6
                labels.append((label, vec))
            else:
                labels.append((6, None))

    # Filter valid samples
    valid = [(l, v) for l, v in labels if v is not None and len(v) >= 10]
    print(f"  Valid samples: {len(valid)}")

    if len(valid) < 200:
        print("  Not enough valid samples")
        return 1

    # Build feature matrix + labels
    # Pad to 72
    X_list = []
    y_list = []
    for label, vec in valid:
        full = np.zeros(INPUT_DIM_MULTI, dtype=np.float32)
        n = min(len(vec), INPUT_DIM_MULTI)
        full[:n] = vec[:n]
        X_list.append(full)
        y_list.append(label)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    print(f"  Feature matrix: {X.shape}")

    # Distribution
    dist = {}
    for label in range(8):
        cnt = int((y == label).sum())
        if cnt:
            dist[label] = cnt
    print(f"  Label distribution: {dist}")

    # Train/Test split (temporal 80/20)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # Create model
    clf = RegimeClassifier(model_dir="models/regime_72d")
    clf.model = TradingMLP(input_dim=INPUT_DIM_MULTI).to(
        torch.device("cuda" if torch.cuda.is_available() else "cpu")
    )
    from analytics.regime.ml_classifier import MyTorchScaler

    clf.scaler = MyTorchScaler()

    # Train
    X_train_t = torch.tensor(X_train)
    clf.scaler.fit(X_train_t)
    X_train_s = clf.scaler.transform(X_train_t)
    X_test_t = torch.tensor(X_test)
    X_test_s = clf.scaler.transform(X_test_t)

    clf.model.train()
    optimizer = torch.optim.Adam(clf.model.parameters(), lr=1e-4)
    criterion = torch.nn.CrossEntropyLoss()

    for epoch in range(100):
        optimizer.zero_grad()
        logits = clf.model(X_train_s.to(clf.model.input_layer[0].weight.device))
        loss = criterion(logits, torch.tensor(y_train, dtype=torch.long, device=logits.device))
        loss.backward()
        optimizer.step()

        if epoch % 20 == 0 or epoch == 99:
            with torch.no_grad():
                train_preds = logits.argmax(dim=1)
                train_acc = (
                    (train_preds == torch.tensor(y_train, dtype=torch.long, device=logits.device))
                    .float()
                    .mean()
                    .item()
                )
                test_logits = clf.model(X_test_s.to(logits.device))
                test_preds = test_logits.argmax(dim=1)
                test_acc = (
                    (test_preds == torch.tensor(y_test, dtype=torch.long, device=logits.device))
                    .float()
                    .mean()
                    .item()
                )
                baseline = 1.0 / 8
                print(
                    f"  Epoch {epoch:>2d}: loss={loss.item():.4f} "
                    f"train_acc={train_acc:.1%} test_acc={test_acc:.1%} "
                    f"(random={baseline:.1%})"
                )

    # Save
    clf.model.eval()
    torch.save(clf.model.state_dict(), str(clf.model_path))
    clf.scaler.save(str(clf.scaler_path))
    with open(clf.info_path, "w") as f:
        json.dump(
            {
                "input_dim": INPUT_DIM_MULTI,
                "output_dim": 8,
                "feature_names": [],
                "epochs": 100,
                "final_loss": float(loss.item()),
                "test_accuracy": test_acc,
                "baseline_accuracy": baseline,
                "labeling_method": "metric_based_8_regime",
            },
            f,
        )

    print(f"\n  Model saved to {clf.model_path}")
    print(f"  Test accuracy: {test_acc:.1%} (random baseline: {baseline:.1%})")
    improvement = (test_acc - baseline) / baseline * 100
    print(f"  Improvement over random: {improvement:+.1f}%")
    print("  ✅ Training complete")

    return 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
