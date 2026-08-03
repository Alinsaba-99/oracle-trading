"""BL-023 Fase 4 — signal candidate probe on the ES 1d lake.

Derives candidate signals on TRAIN (pre-2023) only, measures whether they
produce trade targets at all (the known failure: RegimeAwareEnsemble emits
ZERO targets inside M31 windows — the "30/30 with 0 trades" mystery), then
reports gross returns on the holdout (2023+) for a quick walk-forward look.

Anti-overfit rule (user): candidate decisions are derived on train pre-2023,
NEVER on the M31 evaluation window. The holdout is for reading, not fitting.

Usage:
    uv run --frozen python scripts/probe_signal_candidates.py
    uv run --frozen python scripts/probe_signal_candidates.py --min-targets 20
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analytics.backtest.providers import read_from_lake
from analytics.strategy.signals import (
    BbandReversion,
    DonchianBreakout,
    EmaTrend,
    KeltnerReversion,
    RocMomentum,
    RsiReversion,
    TrendFilteredBreakout,
    ZscoreReversion,
)

EXPECTED_ROWS = 6522  # ES|1d lake pin (BL-023 F-07)
TRAIN_CUTOFF = datetime(2023, 1, 1)
REPORT_DIR = Path("docs/reports/signal-candidates")


def _targets(signal: Any, df: pl.DataFrame) -> list[dict[str, Any]]:
    """Emit target rows (signal direction + bar index) using only past bars.

    Uses the signals' real API: compute(df) -> pl.Series of int8 direction
    (1 long, -1 short, 0 flat). Vectorized per window; the signal itself is
    point-in-time (only past bars feed its indicators).
    """
    targets: list[dict[str, Any]] = []
    series = signal.compute(df)
    if series is None or len(series) != df.height:
        return targets
    directions = series.to_list()
    timestamps = df["timestamp"].to_list()
    closes = df["close"].to_list()
    for i, direction in enumerate(directions):
        if direction not in (1, -1):
            continue
        targets.append(
            {
                "bar": i,
                "timestamp": timestamps[i],
                "direction": int(direction),
                "close": float(closes[i]),
            }
        )
    return targets


def _gross_return(
    targets: list[dict[str, Any]], closes: list[float], horizon: int = 5
) -> list[float]:
    """Gross per-target return over the next `horizon` bars (direction-aware)."""
    returns: list[float] = []
    for t in targets:
        i = t["bar"]
        if i + horizon >= len(closes):
            continue
        move = (closes[i + horizon] - closes[i]) / closes[i]
        returns.append(move * t["direction"])
    return returns


def _candidates() -> list[tuple[str, Any]]:
    return [
        ("roc_momentum_12", RocMomentum(period=12)),
        ("bollinger_reversion", BbandReversion()),
        ("donchian_breakout", DonchianBreakout()),
        ("rsi_reversion", RsiReversion()),
        ("ema_trend", EmaTrend()),
        ("zscore_reversion", ZscoreReversion()),
        ("keltner_reversion", KeltnerReversion()),
        ("trend_filtered_breakout", TrendFilteredBreakout()),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-targets", type=int, default=10, help="min targets on train to be viable"
    )
    parser.add_argument("--horizon", type=int, default=5, help="gross return horizon in bars")
    args = parser.parse_args()

    data = read_from_lake("ES", "1d")
    if data is None or data.height != EXPECTED_ROWS:
        print(f"FATAL: ES 1d lake rows {data.height if data is not None else 0} != {EXPECTED_ROWS}")
        return 2

    df = data.with_columns(pl.col("timestamp").dt.replace_time_zone(None))
    train = df.filter(pl.col("timestamp") < TRAIN_CUTOFF)
    holdout = df.filter(pl.col("timestamp") >= TRAIN_CUTOFF)
    closes_train = train["close"].to_list()
    closes_holdout = holdout["close"].to_list()
    print(
        f"Dataset: ES 1d lake ({data.height} bars) | "
        f"train < 2023: {train.height} | holdout: {holdout.height}"
    )

    results: list[dict[str, Any]] = []
    for name, signal in _candidates():
        train_targets = _targets(signal, train)
        if len(train_targets) < args.min_targets:
            results.append(
                {
                    "candidate": name,
                    "train_targets": len(train_targets),
                    "status": "NOT_VIABLE",
                    "reason": f"fewer than {args.min_targets} targets on train",
                }
            )
            print(
                f"  {name:<26} train_targets={len(train_targets):>5} "
                f"NOT_VIABLE (min {args.min_targets})"
            )
            continue

        train_ret = _gross_return(train_targets, closes_train, args.horizon)
        # Same signal, applied to the holdout for a read-only walk-forward glance.
        holdout_targets = _targets(signal, holdout)
        holdout_ret = _gross_return(holdout_targets, closes_holdout, args.horizon)

        row: dict[str, Any] = {
            "candidate": name,
            "train_targets": len(train_targets),
            "train_mean_return": round(statistics.mean(train_ret), 6) if train_ret else 0.0,
            "train_win_rate": round(sum(1 for r in train_ret if r > 0) / len(train_ret), 4)
            if train_ret
            else 0.0,
            "holdout_targets": len(holdout_targets),
            "holdout_mean_return": round(statistics.mean(holdout_ret), 6) if holdout_ret else 0.0,
            "holdout_win_rate": round(sum(1 for r in holdout_ret if r > 0) / len(holdout_ret), 4)
            if holdout_ret
            else 0.0,
            "status": "VIABLE",
        }
        results.append(row)
        print(
            f"  {name:<26} train_targets={len(train_targets):>5} "
            f"train_mean={row['train_mean_return']:.5f} "
            f"win={row['train_win_rate']:.3f} | "
            f"holdout_targets={len(holdout_targets):>5} "
            f"holdout_mean={row['holdout_mean_return']:.5f} "
            f"win={row['holdout_win_rate']:.3f}"
        )

    viable = [r for r in results if r["status"] == "VIABLE"]
    print(f"\nVIABLE: {len(viable)}/{len(results)}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "title": "BL-023 Fase 4 — signal candidate probe (ES 1d lake)",
        "dataset": f"lake:ES:1d ({data.height} bars)",
        "train_cutoff": TRAIN_CUTOFF.isoformat(),
        "horizon_bars": args.horizon,
        "min_targets": args.min_targets,
        "candidates": results,
        "note": (
            "Derivation on train pre-2023 only; holdout is read-only "
            "walk-forward glance, not a fit."
        ),
    }
    out = REPORT_DIR / "signal-candidates.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
