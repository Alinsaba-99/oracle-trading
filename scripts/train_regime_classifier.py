#!/usr/bin/env python3
"""Train the PyTorch regime classifier on ES 1d historical data.

Labeling: il regime di ogni barra e' il percentile del rendimento
futuro a N barre. Divide in 8 classi percentile (0-12.5% = bear estremo,
12.5-25% = bear, ..., 87.5-100% = bull estremo).

Mapping Kairos 8-regime:
  0 Dong_Bang  = percentile 0-5%     (congelato)
  1 Nen_Chat   = percentile 5-15%    (compressione)
  2 Dau_XH     = percentile 15-35%   (inizio uptrend)
  3 XH_Manh    = percentile 35-55%   (uptrend forte)
  4 Cao_Trao   = percentile 55-75%   (climax)
  5 Hoi_Quy    = percentile 75-90%   (ritraccio)
  6 Nhieu_Dong = percentile 90-98%   (noisy/choppy)
  7 Quet_TK    = percentile 98-100%  (stop hunting)

Usage::
    uv run --frozen python scripts/train_regime_classifier.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.regime.ml_classifier import RegimeClassifier
from analytics.regime.ml_features import FEATURE_NAMES, compute_all_features


def label_regime_by_return(
    df: pl.DataFrame, forward_bars: int = 5, n_quantiles: int = 8
) -> list[int]:
    """Label each bar with a regime class based on forward return percentile.

    Args:
        df: OHLCV DataFrame with close column (must have 18 features computed).
        forward_bars: How many bars ahead to measure return.
        n_quantiles: Number of regime classes (default 8).

    Returns:
        List of integer labels (0..n_quantiles-1), -1 for bars without forward data.
    """
    close = df["close"].to_numpy().astype(float)
    n = len(close)
    labels = [-1] * n

    for i in range(n - forward_bars):
        ret = (close[i + forward_bars] / close[i] - 1) * 100
        # Percentile rank among all forward returns
        all_future = [close[j + forward_bars] / close[j] - 1 for j in range(n - forward_bars)]
        pct = sum(1 for r in all_future if r < ret) / max(len(all_future), 1)
        label = min(int(pct * n_quantiles), n_quantiles - 1)
        labels[i] = label

    return labels


async def main() -> int:
    print(f"\n{'=' * 70}")
    print("TRAINING — PyTorch Regime Classifier (ES 1d)")
    print(f"{'=' * 70}\n")

    # Load ES 1d
    df = pl.scan_parquet("data/lake/normalized/symbol=ES/tf=1d/**/*.parquet").collect()
    df = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
    n_total = len(df)
    print(f"  Data: {n_total} bars ({df[0, 'timestamp']} -> {df[-1, 'timestamp']})")

    # Compute 18 features
    print(f"  Computing {len(FEATURE_NAMES)} features...")
    df_features = compute_all_features(df)
    print(f"  Done. Shape: {df_features.shape}")

    # Label
    print("  Labeling regimes (forward=5 bars, 8 classes)...")
    labels = label_regime_by_return(df_features, forward_bars=5, n_quantiles=8)
    valid_indices = [i for i, lbl in enumerate(labels) if lbl >= 0]
    print(f"  Effective samples: {len(valid_indices)}")

    if len(valid_indices) < 100:
        print(f"  ❌ Too few samples ({len(valid_indices)}). Need at least 100.")
        return 1

    # Train/Test split (temporal)
    split = int(len(valid_indices) * 0.8)
    train_idx = valid_indices[:split]
    test_idx = valid_indices[split:]

    # Build df_list and labels_list
    train_dfs = [df_features[i - 50 : i + 1] for i in train_idx if i >= 50]
    test_dfs = [df_features[i - 50 : i + 1] for i in test_idx if i >= 50]

    train_labels = [labels[i] for i in train_idx if i >= 50]
    test_labels = [labels[i] for i in test_idx if i >= 50]

    print(f"  Train samples: {len(train_dfs)}")
    print(f"  Test samples:  {len(test_dfs)}")

    # Initialize classifier
    clf = RegimeClassifier(model_dir="models/regime")
    clf.load_or_init(input_dim=18)

    # Train
    print("\n  Training (epochs=50, lr=1e-4)...")
    history = clf.train(train_dfs, train_labels, epochs=50, lr=1e-4)

    print(f"\n  Final loss: {history['loss'][-1]:.4f}")

    # Test accuracy
    correct = 0
    total = 0
    for df_sample, true_label in zip(test_dfs[:500], test_labels[:500], strict=False):
        predicted, _ = clf.predict(df_sample)
        [
            i
            for i, name in enumerate(
                [
                    "Dong_Bang",
                    "Nen_Chat",
                    "Dau_XH",
                    "XH_Manh",
                    "Cao_Trao",
                    "Hoi_Quy",
                    "Nhieu_Dong",
                    "Quet_TK",
                ]
            )
        ]
        pred_map = {
            "Dong_Bang": 0,
            "Nen_Chat": 1,
            "Dau_XH": 2,
            "XH_Manh": 3,
            "Cao_Trao": 4,
            "Hoi_Quy": 5,
            "Nhieu_Dong": 6,
            "Quet_TK": 7,
        }
        if pred_map.get(predicted, -1) == true_label:
            correct += 1
        total += 1

    accuracy = correct / max(total, 1)
    print(f"\n  Test accuracy: {accuracy:.1%} ({correct}/{total})")
    print("\n  Model saved to: models/regime/model_pytorch.pth")
    print("  ✅ Training complete")

    return 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
