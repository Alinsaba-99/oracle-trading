"""BL-010..014 — Regime rebalance verification.

Distribution check: feed M31-pinned data through 30 non-overlapping
windows and confirm regime distribution roughly hits:
- bull/bear 10-30% combined
- choppy 40-60%
- volatile 10-20%
- unknown < 5%
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from analytics.strategy.lorentzian import LorentzianKNN
from analytics.strategy.regime_ensemble import RegimeAwareEnsemble, RegimeLabel, SpecialistId
from analytics.strategy.signals import DonchianBreakout, EmaTrend, RsiReversion


def _build_ensemble() -> RegimeAwareEnsemble:
    return RegimeAwareEnsemble(
        specialists={
            SpecialistId.TREND: EmaTrend(fast=10, slow=30),
            SpecialistId.MEAN_REVERSION: RsiReversion(period=14),
            SpecialistId.BREAKOUT: DonchianBreakout(period=20),
            SpecialistId.LORENTZIAN: LorentzianKNN(
                k=4, lookahead=4, max_bars_back=80, feature_count=3
            ),
        },
        min_confidence=0.5,
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/ohlcv/ES_1d.parquet")
    p.add_argument("--windows", type=int, default=30)
    p.add_argument("--output", default="logs/regime_distribution.json")
    args = p.parse_args()

    raw = pl.read_parquet(args.data)
    rename = {c: c.lower() for c in raw.columns}
    df = raw.rename(rename)
    n = len(df)
    win_size = n // args.windows
    if win_size < 30:
        print(f"ERROR: not enough bars ({n}) for {args.windows} windows")
        return 1

    ensemble = _build_ensemble()
    counts: Counter[RegimeLabel] = Counter()
    specialist_counts: Counter[SpecialistId] = Counter()
    confidences: list[float] = []
    per_window: list[dict] = []

    for i in range(args.windows):
        start = i * win_size
        end = start + win_size if i < args.windows - 1 else n
        sub = df[start:end]
        decision = ensemble.route(sub)
        counts[decision.regime] += 1
        specialist_counts[decision.specialist] += 1
        confidences.append(decision.regime_confidence)
        per_window.append(
            {
                "window": i + 1,
                "regime": decision.regime.value,
                "specialist": decision.specialist.value,
                "confidence": round(decision.regime_confidence, 4),
            }
        )

    total = sum(counts.values())
    distribution = {r.value: round(c / total * 100, 1) for r, c in counts.items()}
    spec_distribution = {s.value: round(c / total * 100, 1) for s, c in specialist_counts.items()}

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "metadata": {
            "data": args.data,
            "n_bars": n,
            "windows": args.windows,
            "timestamp": "2026-07-25",
            "bl": "BL-010..014",
        },
        "regime_distribution_pct": distribution,
        "specialist_distribution_pct": spec_distribution,
        "mean_confidence": round(statistics.mean(confidences), 4),
        "per_window": per_window,
        "target_distribution": {
            "bull": "5-15%",
            "bear": "5-15%",
            "choppy": "40-60%",
            "volatile": "10-20%",
            "unknown": "< 5%",
        },
    }
    out_path.write_text(json.dumps(out, indent=2))

    print(f"Regime distribution ({total} windows on {n} bar dataset):")
    for r, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {r.value:<10} {c:>3d}/{total} ({c / total * 100:>5.1f}%)")
    print("\nSpecialist distribution:")
    for s, c in sorted(specialist_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {s.value:<15} {c:>3d}/{total} ({c / total * 100:>5.1f}%)")
    print(f"\nMean confidence: {statistics.mean(confidences):.3f}")
    print(f"\nSaved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
