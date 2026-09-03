#!/usr/bin/env python3
"""BL-718 Sprint 2c — Trading-strategy qualification of the funding/basis edges.

Sprint 2/2b qualified EF-006 (funding-z) and EF-007 (perp-basis) as
*information* (IC screen).  This runner asks the next question: can they
be *traded* after realistic costs?  Sign-based strategies failed the
haircut-Sharpe gate; here the position is sized proportionally to |z|
(cap 2x) and taker fees are charged per position change.

Strategies (frozen at sprint-time):

1. ``funding_z_sized`` — per asset in ETH/XRP/ADA (the IC-pass cohort):
   position = clip(−funding_z / 2, −2, +2) * vol_scalar, horizon 24h.
2. ``basis_carry`` — per asset in ETH/BTC: position = clip(−basis_z/2,
   −2, +2) * vol_scalar on the SPOT leg (unhedged, honest).

Costs: 10 bp per unit of turnover (taker × 2 ≈ 5bp each side plus
slippage margin), charged on |Δposition|.

Walk-forward: train (warm-up only — no fitted parameters) ≤ 2022-12-31,
test > 2022-12-31.  All thresholds identical to Sprint 1/2 gauntlet.

Outputs:
    docs/reports/edge-factory/sprint-2c.md
    docs/reports/edge-factory/sprint-2c.json

Usage:
    uv run --frozen python scripts/run_factory_sprint2c_trading.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.metrics.canonical import (  # ADR-021  # noqa: E402
    max_drawdown_from_returns,
    sharpe_ratio,
)
from scripts.run_factory_sprint2_qualification import load_funding_onto_prices  # noqa: E402
from scripts.run_factory_sprint2b_extended import perp_spot_basis  # noqa: E402

# Frozen parameters
TEST_SPLIT = pd.Timestamp("2022-12-31", tz="UTC")
COST_BPS_PER_TURNOVER: float = 10.0  # bps per unit turnover
POSITION_CAP: float = 2.0
Z_SCALE: float = 2.0  # position = z / Z_SCALE, capped
TARGET_VOL: float = 0.20  # annual, vol-targeting scalar
HORIZON_HOURS: int = 24
PERIODS_PER_YEAR_1H: int = 24 * 365
FUNDING_ASSETS = ("ETHUSDT", "XRPUSDT", "ADAUSDT")
BASIS_ASSETS = ("ETHUSDT", "BTCUSDT")
VOL_WINDOW_HOURS: int = 168  # 7d realised vol for the scalar
SIGNAL_EWM_SPAN: int = 24  # signal smoothing (hours) — cuts churn
REBAND: float = 0.25  # rebalance only when |target - current| > reband


@dataclass
class StrategyResult:
    name: str
    family: str
    asset: str
    n_test_bars: int
    trades: int
    turnover: float
    cost_drag_annual: float
    annual_return: float
    annual_vol: float
    sharpe: float
    max_drawdown: float
    monthly_mean: float
    p_monthly_geq_5pct: float
    months: int


def _vol_scalar(close: pd.Series) -> pd.Series:
    """1% target per-bar vol scalar: target_daily_vol / realised_vol(7d)."""
    ret = close.pct_change()
    rv = ret.rolling(VOL_WINDOW_HOURS, min_periods=48).std() * math.sqrt(24 * 365)
    return (TARGET_VOL / rv.replace(0.0, np.nan)).clip(upper=POSITION_CAP)


def _sized_position(factor: pd.Series, scalar: pd.Series) -> pd.Series:
    """Position = clip(smoothed factor/2, ±cap) * vol scalar, with dead-band.

    The raw factor is EWM-smoothed (span=24h) to cut churn; the executed
    position only rebalances when the target moves more than REBAND away
    from the current position (no-trade band).  Shifted 1 bar (causal).
    """
    smooth = factor.ewm(span=SIGNAL_EWM_SPAN, min_periods=SIGNAL_EWM_SPAN).mean()
    target = (smooth / Z_SCALE).clip(-POSITION_CAP, POSITION_CAP) * scalar
    target = target.shift(1)
    tgt_vals = target.to_numpy(dtype=np.float64)
    pos_vals = np.zeros(len(tgt_vals), dtype=np.float64)
    cur = 0.0
    for i in range(len(tgt_vals)):
        t = tgt_vals[i]
        if np.isfinite(t) and abs(t - cur) > REBAND:
            cur = t
        pos_vals[i] = cur if np.isfinite(t) else 0.0
    return pd.Series(pos_vals, index=target.index)


def _apply_costs(pos: pd.Series, close: pd.Series) -> tuple[pd.Series, float, int, float]:
    """Strategy returns net of bps turnover costs.

    Returns (rets, costs_total, n_trades, turnover).
    """
    ret = close.pct_change().fillna(0.0)
    turnover = pos.diff().abs().fillna(0.0)
    cost_rate = turnover * (COST_BPS_PER_TURNOVER / 10_000.0)
    strat = pos * ret - cost_rate
    trades = int((turnover > 0).sum())
    return strat, float(cost_rate.sum()), trades, float(turnover.sum())


def _monthly(returns: pd.Series) -> pd.Series:
    return returns.resample("ME").apply(lambda x: (1 + x).prod() - 1)


def _result_from_returns(
    name: str, family: str, asset: str, strat: pd.Series, costs: float, trades: int, turnover: float
) -> StrategyResult:
    strat = strat.dropna()
    monthly = _monthly(strat)
    test_mask = strat.index > TEST_SPLIT
    test = strat[test_mask]
    arr_t = test.to_numpy()
    sr = sharpe_ratio(arr_t, periods_per_year=PERIODS_PER_YEAR_1H)
    dd = max_drawdown_from_returns(arr_t)
    annual = float((1 + test).prod() ** (PERIODS_PER_YEAR_1H / max(len(test), 1)) - 1)
    return StrategyResult(
        name=name,
        family=family,
        asset=asset,
        n_test_bars=len(test),
        trades=trades,
        turnover=turnover,
        cost_drag_annual=costs / max(len(strat), 1) * PERIODS_PER_YEAR_1H,
        annual_return=annual,
        annual_vol=float(np.std(arr_t, ddof=1) * math.sqrt(PERIODS_PER_YEAR_1H)),
        sharpe=float(sr) if np.isfinite(sr) else 0.0,
        max_drawdown=float(dd),
        monthly_mean=float(monthly.mean()) if len(monthly) else 0.0,
        p_monthly_geq_5pct=float((monthly >= 0.05).mean()) if len(monthly) else 0.0,
        months=len(monthly),
    )


def funding_z_strategy(close: pd.Series, funding: pd.Series) -> pd.Series:
    z = (funding - funding.rolling(180, min_periods=90).mean()) / funding.rolling(
        180, min_periods=90
    ).std(ddof=1).replace(0.0, np.nan)
    pos = _sized_position(-z, _vol_scalar(close))
    strat, _, _, _ = _apply_costs(pos, close)
    return strat


def basis_strategy(basis: pd.Series, spot: pd.Series) -> pd.Series:
    z = (basis - basis.rolling(720, min_periods=360).mean()) / basis.rolling(
        720, min_periods=360
    ).std(ddof=1).replace(0.0, np.nan)
    pos = _sized_position(-z, _vol_scalar(spot))
    strat, _, _, _ = _apply_costs(pos, spot)
    return strat


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funding-dir", default="data/lake/raw/funding")
    parser.add_argument("--perp-dir", default="data/lake/raw/perp")
    parser.add_argument("--lake-root", default="data/lake/curated")
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    args = parser.parse_args()
    funding_dir, lake_root, perp_dir = (
        Path(args.funding_dir),
        Path(args.lake_root),
        Path(args.perp_dir),
    )
    out_dir = Path(args.out_dir)

    results: list[StrategyResult] = []
    strats: dict[str, pd.Series] = {}

    for asset in FUNDING_ASSETS:
        loaded = load_funding_onto_prices(funding_dir, lake_root, asset)
        if loaded is None:
            print(f"SKIP {asset}: funding data missing", file=sys.stderr)
            continue
        close, funding = loaded
        strat = funding_z_strategy(close, funding)
        pos = _sized_position(
            -(
                (funding - funding.rolling(180, min_periods=90).mean())
                / funding.rolling(180, min_periods=90).std(ddof=1).replace(0.0, np.nan)
            ),
            _vol_scalar(close),
        )
        _, costs, trades, turnover = _apply_costs(pos, close)
        strats[f"funding_z::{asset}"] = strat
        results.append(
            _result_from_returns(
                f"funding_z_{asset}", "funding_z_sized", asset, strat, costs, trades, turnover
            )
        )

    for asset in BASIS_ASSETS:
        basis = perp_spot_basis(perp_dir, lake_root, asset)
        if basis is None:
            print(f"SKIP {asset}: perp data missing", file=sys.stderr)
            continue
        spot = pd.read_parquet(lake_root / f"{asset}_1h.parquet", columns=["timestamp", "close"])
        spot.index = pd.to_datetime(spot["timestamp"], utc=True)
        spot = spot["close"].astype(float).sort_index()
        spot = spot[~spot.index.duplicated(keep="last")]
        strat = basis_strategy(basis, spot)
        z = (basis - basis.rolling(720, min_periods=360).mean()) / basis.rolling(
            720, min_periods=360
        ).std(ddof=1).replace(0.0, np.nan)
        pos = _sized_position(-z, _vol_scalar(spot))
        _, costs, trades, turnover = _apply_costs(pos, spot)
        strats[f"basis::{asset}"] = strat
        results.append(
            _result_from_returns(
                f"basis_{asset}", "basis_carry", asset, strat, costs, trades, turnover
            )
        )

    # Equal-weight portfolio of the available strategies (test window only)
    port: pd.Series | None = None
    if strats:
        df = pd.DataFrame(strats)
        port = df.mean(axis=1).dropna()

    for r in results:
        print(
            f"{r.name:24s} SR={r.sharpe:+.2f} ann={r.annual_return:+.2%} "
            f"DD={r.max_drawdown:.1%} trades={r.trades} costs/yr={r.cost_drag_annual:.2%} "
            f"P(m≥5%)={r.p_monthly_geq_5pct:.1%}"
        )
    if port is not None:
        pr = _result_from_returns("portfolio_ew", "portfolio", "MULTI", port, 0.0, 0, 0.0)
        results.append(pr)
        print(
            f"{pr.name:24s} SR={pr.sharpe:+.2f} ann={pr.annual_return:+.2%} "
            f"DD={pr.max_drawdown:.1%} P(m≥5%)={pr.p_monthly_geq_5pct:.1%}"
        )

    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "Edge Factory Sprint 2c — trading-strategy qualification (sized, cost-aware)",
        "parameters": {
            "test_split": str(TEST_SPLIT),
            "cost_bps_per_turnover": COST_BPS_PER_TURNOVER,
            "position_cap": POSITION_CAP,
            "target_vol": TARGET_VOL,
            "horizon_hours": HORIZON_HOURS,
        },
        "results": [asdict(r) for r in results],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sprint-2c.json").write_text(json.dumps(payload, indent=2, default=str))
    lines = [
        "# Sprint 2c — Trading-strategy qualification (funding-z & basis, sized + costs)",
        "",
        f"**Generated**: {payload['generated']}",
        "",
        f"Costs: {COST_BPS_PER_TURNOVER:.0f} bps per unit turnover; position = clip(z/{Z_SCALE:.0f}, ±{POSITION_CAP:.0f}) × vol scalar (target {TARGET_VOL:.0%}).",  # noqa: E501
        f"Test window: > {TEST_SPLIT.date()} (walk-forward).",
        "",
        "| strategy | asset | SR | ann ret | MaxDD | trades | cost/yr | P(m≥5%) | months |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.family} | {r.asset} | {r.sharpe:+.2f} | {r.annual_return:+.1%} | "
            f"{r.max_drawdown:.1%} | {r.trades} | {r.cost_drag_annual:.2%} | "
            f"{r.p_monthly_geq_5pct:.1%} | {r.months} |"
        )
    (out_dir / "sprint-2c.md").write_text("\n".join(lines) + "\n")
    print(f"\nReport → {out_dir / 'sprint-2c.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
