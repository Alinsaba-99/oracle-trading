#!/usr/bin/env python3
"""BL-737 — Universe scan: N-orthogonal-legs portfolio (Renaissance-style).

Goal (user 2026-09-04): approach 5%/month net via MANY weak orthogonal
edges, not one strong signal.  Math: equal-weight portfolio of N legs
with average per-leg SR s and average pairwise correlation ρ has
SR_port = s * sqrt(N / (1 + (N-1)ρ)).  This runner measures the actual
curve SR_port(N) on the full 1d lake universe (~100 symbols) using the
frozen signal families already qualified (no new fitting):

  - donchian breakout (20, 50)
  - ema trend (20/50)
  - bband reversion (20/2.0, 30/2.5)
  - rsi reversion (14, 30, 55) — crypto only

Leg admission (frozen, in-sample FREE): none — all legs enter, the
SR(N) curve is the honest full-universe curve, not a selected one.
The walk-forward test window (> 2022-12-31) is the same as all sprints.

Outputs:
    docs/reports/edge-factory/universe-scan-sr-n.md|.json

Usage:
    uv run --frozen python scripts/run_universe_scan_sr_n.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_multi_strategy_ensemble import backtest_leg, load_asset_1d  # noqa: E402

from analytics.metrics.canonical import max_drawdown_from_returns, sharpe_ratio  # noqa: E402

TEST_END = datetime(2022, 12, 31)
START, END = datetime(2017, 1, 1), datetime(2025, 12, 31)
PERIODS_PER_YEAR_1D = 252
CRYPTO_SET = {
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "LINKUSDT",
    "AVAXUSDT",
}


def leg_specs(symbol: str) -> list[tuple[Any, ...]]:
    """Frozen families per symbol (trend + reversion; rsi crypto only)."""
    specs = [
        (f"{symbol}_donchian_20", "trend_breakout", ("donchian", 20)),
        (f"{symbol}_donchian_50", "trend_breakout", ("donchian", 50)),
        (f"{symbol}_ema_20_50", "trend_breakout", ("ema", 20, 50)),
        (f"{symbol}_bband_20_2", "mean_reversion", ("bband", 20, 2.0)),
    ]
    if symbol in CRYPTO_SET:
        specs.append((f"{symbol}_rsi_14", "mean_reversion", ("rsi", 14, 30.0, 55.0)))
    return specs


def scan() -> dict[str, pd.Series]:
    symbols = sorted(
        p.name.split("=", 1)[1]
        for p in (ROOT / "data/lake/normalized").iterdir()
        if p.is_dir() and p.name.startswith("symbol=")
    )
    legs: dict[str, pd.Series] = {}
    skipped = 0
    for sym in symbols:
        try:
            df = load_asset_1d(sym, START, END)
        except FileNotFoundError:
            skipped += 1
            continue
        if df.height < 600:  # need history for warm-up + test window
            skipped += 1
            continue
        for name, family, signal in leg_specs(sym):
            try:
                res, _pos = backtest_leg(df, signal, name, family, sym, TEST_END, target_vol=0.12)
            except (ValueError, KeyError):
                continue
            rets = np.asarray(res.daily_returns, dtype=np.float64)
            idx = pd.to_datetime(df["timestamp"].to_list()[-len(rets) :])
            legs[name] = pd.Series(rets, index=idx, name=name)
    print(f"legs built: {len(legs)} (skipped {skipped} symbols)")
    return legs


def sr_n_curve(legs: dict[str, pd.Series], args: argparse.Namespace) -> list[dict[str, Any]]:
    """SR of the equal-weight portfolio vs number of legs (fixed seed order)."""
    names = sorted(legs)
    rng = np.random.default_rng(args.seed)
    rng.shuffle(names)
    df = pd.DataFrame({k: legs[k] for k in names})
    test = df[df.index > pd.Timestamp(args.test_split)]
    test = test.dropna(how="all").fillna(0.0)
    curve = []
    n_total = len(names)
    checkpoints = sorted({5, 10, 20, 40, 80, 120, 160, 200, n_total})
    for n in checkpoints:
        if n > n_total:
            continue
        sub = test.iloc[:, :n]
        port = sub.mean(axis=1)
        arr = port.to_numpy()
        monthly = port.resample("ME").apply(lambda x: (1 + x).prod() - 1)
        sr = sharpe_ratio(arr, periods_per_year=PERIODS_PER_YEAR_1D)
        vol = float(np.std(arr, ddof=1) * math.sqrt(252))
        # leverage to a fixed portfolio vol: return scales, SR unchanged
        lev30 = 0.30 / vol if vol > 0 else 0.0
        m30 = monthly * lev30
        curve.append(
            {
                "n_legs": n,
                "sharpe": float(sr) if np.isfinite(sr) else 0.0,
                "annual_return": float((1 + port).prod() ** (252 / len(port)) - 1),
                "vol": vol,
                "max_drawdown": float(max_drawdown_from_returns(arr)),
                "monthly_mean": float(monthly.mean()),
                "p_monthly_geq_5pct": float((monthly >= 0.05).mean()),
                "lev30_monthly_mean": float(m30.mean()),
                "lev30_p_monthly_geq_5pct": float((m30 >= 0.05).mean()),
            }
        )
    return curve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-split", default="2022-12-31")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)

    legs = scan()
    if not legs:
        print("FATAL: no legs")
        return 1
    curve = sr_n_curve(legs, args)

    print(f"\nSR(N) curve — equal-weight, test > {args.test_split}:")
    print(f"{'N':>4} {'SR':>6} {'ann ret':>9} {'vol':>7} {'MaxDD':>7} {'P(m≥5%)':>8}")
    for c in curve:
        print(
            f"{c['n_legs']:>4} {c['sharpe']:>6.2f} {c['annual_return']:>9.2%} "
            f"{c['vol']:>7.2%} {c['max_drawdown']:>7.1%} {c['p_monthly_geq_5pct']:>8.1%}"
        )

    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "BL-737 universe scan — SR(N) equal-weight curve, frozen families",
        "n_legs_total": len(legs),
        "sr_n_curve": curve,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "universe-scan-sr-n.json").write_text(json.dumps(payload, indent=2, default=str))
    lines = [
        "# BL-737 — Universe scan: SR(N) curve (Renaissance-style N orthogonal legs)",
        "",
        f"**Generated**: {payload['generated']}",
        "",
        f"{len(legs)} legs from frozen families (donchian/ema/bband/rsi) on the full 1d lake.",
        f"Equal-weight portfolio vs number of legs, walk-forward test > {args.test_split}.",
        "",
        "| N legs | SR | ann ret | vol | MaxDD | P(m≥5%) |",
        "|---|---|---|---|---|---|",
    ]
    for c in curve:
        lines.append(
            f"| {c['n_legs']} | {c['sharpe']:+.2f} | {c['annual_return']:+.1%} | "
            f"{c['vol']:.1%} | {c['max_drawdown']:.1%} | {c['p_monthly_geq_5pct']:.1%} |"
        )
    (out_dir / "universe-scan-sr-n.md").write_text("\n".join(lines) + "\n")
    print(f"\nReport → {out_dir / 'universe-scan-sr-n.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
