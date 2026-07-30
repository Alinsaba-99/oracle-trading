"""Investigation 1: regime detector behavior on ES 1d (2000-2026)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import numpy as np
import polars as pl

df = pl.scan_parquet("data/lake/normalized/symbol=ES/tf=1d/**/*.parquet").collect()
df = df.rename({c: c.lower() for c in df.columns}).sort("timestamp")
close = df["close"].to_numpy().astype(float)

sma200 = np.convolve(close, np.ones(200) / 200, mode="valid")
sma200_full = np.full(len(close), np.nan)
sma200_full[199:] = sma200
ratio = close / sma200_full - 1

for threshold in [0.02, 0.03, 0.05, 0.08]:
    b = float(np.mean(ratio > threshold))
    be = float(np.mean(ratio < -threshold))
    ch = float(np.mean(np.abs(ratio) <= threshold))
    print(f"Threshold {threshold:.0%}: Bull={b:.1%} Bear={be:.1%} Choppy={ch:.1%}")

print("\n=== Real Regime Detector (6-detector EnsembleVoter) ===")
from analytics.regime.ensemble import EnsembleVoter  # noqa: E402

detector = EnsembleVoter()

rng = np.random.default_rng(42)
for start in rng.integers(200, len(df) - 200, size=5):
    slice_df = df[start : start + 200]
    try:
        regime, confidence = detector.classify(slice_df)
        print(
            f"  Window {start:>5d}: {regime!s:>8s} (conf={confidence:.2f})  "
            f"price={float(close[start]):.0f} -> {float(close[start + 100]):.0f}"
        )
    except Exception as e:
        print(f"  Window {start}: FAILED {e}")
