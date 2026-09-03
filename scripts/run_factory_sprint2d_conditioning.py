#!/usr/bin/env python3
"""BL-718 Sprint 2d — funding-z as a *conditioning* feature (EF-006 APPROVED use).

Sprint 2c showed the funding-z edge is informative (IC) but not directly
monetisable as a directional long/flat strategy post-2022.  The APPROVED
use (registry EF-006) is as a conditioning/sizing feature for other
signals.  This runner tests exactly that on the Lane A crypto trend legs:

1. **baseline** — EMA(20/50) trend leg on ETH/BTC 1h, vol-targeted 20%,
   taker costs 10 bps/turnover, reband 0.25 (same engine as Sprint 2c).
2. **conditioned** — same leg, but the position is scaled by
   ``1 − clip(|funding_z|, 0, 2)/2``: when funding crowding is extreme
   against the trend (|z| ≥ 2) the position is fully vetoed; when |z| ≤ 0
   the position is untouched.  Crowding against = sign(z) == sign(pos).

Both are evaluated on the walk-forward test window (> 2022-12-31) with
identical costs.  The conditioning is frozen at sprint-time — no tuning.

Outputs:
    docs/reports/edge-factory/sprint-2d.md
    docs/reports/edge-factory/sprint-2d.json

Usage:
    uv run --frozen python scripts/run_factory_sprint2d_conditioning.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_factory_sprint2_qualification import load_funding_onto_prices  # noqa: E402
from scripts.run_factory_sprint2c_trading import (  # noqa: E402
    COST_BPS_PER_TURNOVER,
    POSITION_CAP,
    REBAND,
    TARGET_VOL,
    TEST_SPLIT,
    _apply_costs,
    _result_from_returns,
    _vol_scalar,
)

FUNDING_ASSETS = ("ETHUSDT", "BTCUSDT")
EMA_FAST, EMA_SLOW = 20, 50
VETO_FULL_Z: float = 2.0  # |z| >= this vetoes the position entirely


@dataclass
class ConditioningResult:
    name: str
    variant: str  # baseline | conditioned
    asset: str
    sharpe: float
    annual_return: float
    max_drawdown: float
    trades: int
    turnover: float
    cost_drag_annual: float
    months: int
    p_monthly_geq_5pct: float


def ema_signal(close: pd.Series) -> pd.Series:
    """EMA(20/50) trend signal in {-1, 0, +1} (Lane A backbone, frozen)."""
    fast = close.ewm(span=EMA_FAST, min_periods=EMA_FAST).mean()
    slow = close.ewm(span=EMA_SLOW, min_periods=EMA_SLOW).mean()
    diff = fast - slow
    sign = np.sign(diff).replace(0.0, 0)
    return sign.shift(1).fillna(0.0)  # causal


def _reband_position(target: pd.Series) -> pd.Series:
    """Dead-band execution identical to Sprint 2c (_sized_position tail)."""
    tgt_vals = target.to_numpy(dtype=np.float64)
    pos_vals = np.zeros(len(tgt_vals), dtype=np.float64)
    cur = 0.0
    for i in range(len(tgt_vals)):
        t = tgt_vals[i]
        if np.isfinite(t) and abs(t - cur) > REBAND:
            cur = t
        pos_vals[i] = cur if np.isfinite(t) else 0.0
    return pd.Series(pos_vals, index=target.index)


def funding_z_series(funding: pd.Series) -> pd.Series:
    return (funding - funding.rolling(180, min_periods=90).mean()) / funding.rolling(
        180, min_periods=90
    ).std(ddof=1).replace(0.0, np.nan)


def run_variant(
    close: pd.Series, funding: pd.Series, conditioned: bool
) -> tuple[pd.Series, float, int, float]:
    sig = ema_signal(close)
    scalar = _vol_scalar(close)
    target = (sig * scalar).clip(-POSITION_CAP, POSITION_CAP)
    if conditioned:
        z = funding_z_series(funding)
        # veto scale: 1 when |z|=0, 0 when |z|>=VETO_FULL_Z, only when
        # crowding is AGAINST the position direction; with crowding,
        # positions are kept.
        against = np.sign(z) == np.sign(sig)
        scale = 1.0 - (z.abs() / VETO_FULL_Z).clip(0.0, 1.0).where(against, 0.0)
        # against=True → scale in [0,1]; against=False → 0 (full keep).
        # (np.sign(z)==np.sign(sig) mask: where against, 1-|z|/2; else 1)
        scale = scale.where(against, 1.0)
        target = target * scale
    pos = _reband_position(target)
    return _apply_costs(pos, close)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funding-dir", default="data/lake/raw/funding")
    parser.add_argument("--lake-root", default="data/lake/curated")
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    args = parser.parse_args()
    funding_dir, lake_root, out_dir = (
        Path(args.funding_dir),
        Path(args.lake_root),
        Path(args.out_dir),
    )

    results: list[ConditioningResult] = []
    for asset in FUNDING_ASSETS:
        loaded = load_funding_onto_prices(funding_dir, lake_root, asset)
        if loaded is None:
            print(f"SKIP {asset}: data missing", file=sys.stderr)
            continue
        close, funding = loaded
        for conditioned in (False, True):
            strat, costs, trades, turnover = run_variant(close, funding, conditioned)
            r = _result_from_returns(
                f"{'cond' if conditioned else 'base'}_{asset}",
                "conditioned" if conditioned else "baseline",
                asset,
                strat,
                costs,
                trades,
                turnover,
            )
            results.append(
                ConditioningResult(
                    name=r.name,
                    variant="conditioned" if conditioned else "baseline",
                    asset=r.asset,
                    sharpe=r.sharpe,
                    annual_return=r.annual_return,
                    max_drawdown=r.max_drawdown,
                    trades=r.trades,
                    turnover=r.turnover,
                    cost_drag_annual=r.cost_drag_annual,
                    months=r.months,
                    p_monthly_geq_5pct=r.p_monthly_geq_5pct,
                )
            )
            print(
                f"{r.name:20s} SR={r.sharpe:+.2f} ann={r.annual_return:+.2%} "
                f"DD={r.max_drawdown:.1%} trades={r.trades} P(m≥5%)={r.p_monthly_geq_5pct:.1%}"
            )

    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "Edge Factory Sprint 2d — funding-z conditioning on trend legs",
        "parameters": {
            "test_split": str(TEST_SPLIT),
            "ema": [EMA_FAST, EMA_SLOW],
            "veto_full_z": VETO_FULL_Z,
            "cost_bps_per_turnover": COST_BPS_PER_TURNOVER,
            "target_vol": TARGET_VOL,
            "reband": REBAND,
        },
        "results": [asdict(r) for r in results],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sprint-2d.json").write_text(json.dumps(payload, indent=2, default=str))
    lines = [
        "# Sprint 2d — funding-z as conditioning feature (EF-006 APPROVED use)",
        "",
        f"**Generated**: {payload['generated']}",
        "",
        "EMA(20/50) trend leg on 1h, vol-target 20%, taker 10bps/turnover, reband 0.25.",
        "Conditioned: position scaled by 1 − clip(|funding_z|, 0, 2)/2 when crowding",
        " is against the trade.",
        "",
        "| variant | asset | SR | ann ret | MaxDD | trades | P(m≥5%) |",
        "|---|---|---|---|---|---|---|",
    ]
    for cr in results:
        lines.append(
            f"| {cr.variant} | {cr.asset} | {cr.sharpe:+.2f} | {cr.annual_return:+.1%} | "
            f"{cr.max_drawdown:.1%} | {cr.trades} | {cr.p_monthly_geq_5pct:.1%} |"
        )
    (out_dir / "sprint-2d.md").write_text("\n".join(lines) + "\n")
    print(f"\nReport → {out_dir / 'sprint-2d.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
