#!/usr/bin/env python3
"""BL-738 — FX orthogonal legs: TSMOM + cross-sectional momentum on spot 1h.

The BL-737 universe scan showed SR(N) saturating at 1.2-1.5 because all
legs are trend/reversion on the same price dimension.  This runner adds
genuinely different families on the Dukascopy FX spot 1h lake (2003→):

1. **TSMOM** (Moskowitz-Ooi-Pedersen 2012): per pair, long/short by the
   sign of the past 30d/90d/180d return; vol-targeted; 1h bars, daily
   rebalance proxy (signal on bar close, executed next bar).
2. **XSMOM** (cross-sectional rank): per week, rank pairs by past 30d
   return; long top tercile, short bottom tercile, dollar-neutral.

Both families are frozen (no fitted parameters; windows from literature),
evaluated walk-forward on the same test split as all sprints
(> 2022-12-31).  FX costs: 1.5 bps per unit turnover (half-spread +
slippage on majors/liquid crosses, conservative).

Outputs:
    docs/reports/edge-factory/fx-orthogonal-legs.md|.json

Usage:
    uv run --frozen python scripts/run_fx_orthogonal_legs.py
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

from analytics.metrics.canonical import max_drawdown_from_returns, sharpe_ratio  # noqa: E402

TEST_SPLIT = pd.Timestamp("2022-12-31", tz="UTC")
PERIODS_PER_YEAR_1H = 24 * 365
COST_BPS_PER_TURNOVER: float = 1.5  # FX half-spread + slippage on majors
TARGET_VOL: float = 0.10  # per-pair leg vol target
VOL_WINDOW_HOURS: int = 720  # 30d realised vol
TSMOM_WINDOWS_DAYS = (30, 90, 180)
XS_LOOKBACK_DAYS = 30
FX_PAIRS = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "USDCAD",
    "AUDUSD",
    "NZDUSD",
    "EURGBP",
    "EURJPY",
    "EURCHF",
    "EURAUD",
    "EURCAD",
    "EURNZD",
    "GBPJPY",
    "GBPCHF",
    "GBPAUD",
    "GBPCAD",
    "GBPCHF",
    "AUDJPY",
    "AUDNZD",
    "AUDCAD",
    "AUDCHF",
    "NZDJPY",
    "CADJPY",
    "CHFJPY",
    "CADCHF",
)


def load_fx_1h(lake_root: Path, pair: str) -> pd.Series | None:
    p = lake_root / f"{pair}_1h.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p, columns=["timestamp", "close"]).dropna()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    s = df.set_index("timestamp")["close"].astype(float).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if len(s) < 50_000:  # need ~6y of 1h for warm-up + test
        return None
    return s


def _vol_scalar(close: pd.Series) -> pd.Series:
    ret = close.pct_change()
    rv = ret.rolling(VOL_WINDOW_HOURS, min_periods=168).std() * math.sqrt(PERIODS_PER_YEAR_1H)
    return (TARGET_VOL / rv.replace(0.0, np.nan)).clip(upper=3.0)


def _apply_costs(pos: pd.Series, close: pd.Series) -> pd.Series:
    ret = close.pct_change().fillna(0.0)
    turnover = pos.diff().abs().fillna(0.0)
    return pos * ret - turnover * (COST_BPS_PER_TURNOVER / 10_000.0)


def tsmom_leg(close: pd.Series, window_days: int) -> pd.Series:
    """Long/short by sign of past N-day return; vol-targeted; causal."""
    n = window_days * 24
    mom = close / close.shift(n) - 1.0
    sig = np.sign(mom).fillna(0.0)
    pos = (sig * _vol_scalar(close)).shift(1).fillna(0.0)
    return _apply_costs(pos, close)


def xsmom_family(lake_root: Path) -> pd.Series | None:
    """Cross-sectional FX momentum: rank pairs by 30d return weekly."""
    rets = {}
    for pair in set(FX_PAIRS):
        s = load_fx_1h(lake_root, pair)
        if s is not None:
            rets[pair] = s
    if len(rets) < 9:
        return None
    mom = pd.DataFrame({k: v / v.shift(XS_LOOKBACK_DAYS * 24) - 1.0 for k, v in rets.items()})
    close = pd.DataFrame(rets)
    # weekly signal: last bar of each ISO week
    mom_w = mom.resample("W").last()
    rank = mom_w.rank(axis=1, pct=True)
    # tercile positions: +1 top third, -1 bottom third, 0 middle
    pos_w = pd.DataFrame(
        np.select([rank >= 2 / 3, rank <= 1 / 3], [1.0, -1.0], default=0.0),
        index=rank.index,
        columns=rank.columns,
    )
    # forward-fill weekly positions onto the 1h grid (causal: this week's
    # position is known at last bar of PRIOR week).  reindex with method
    # fills from the most recent weekly label <= each 1h bar.
    pos = pos_w.shift(1).reindex(close.index, method="ffill").fillna(0.0)
    ret = close.pct_change().fillna(0.0)
    per_pair = pos * ret
    port = per_pair.mean(axis=1)  # dollar-neutral equal weight
    # costs on position changes (weekly rebalance only)
    turnover_cost = (pos.diff().abs().fillna(0.0) / len(rets)).sum(axis=1) * (
        COST_BPS_PER_TURNOVER / 10_000.0
    )
    return port - turnover_cost


def _monthly(s: pd.Series) -> pd.Series:
    return s.resample("ME").apply(lambda x: (1 + x).prod() - 1)


def _metrics(name: str, strat: pd.Series) -> dict[str, Any]:
    test = strat[strat.index > TEST_SPLIT].dropna()
    arr = test.to_numpy()
    monthly = _monthly(test)
    sr = sharpe_ratio(arr, periods_per_year=PERIODS_PER_YEAR_1H)
    return {
        "name": name,
        "sharpe": float(sr) if np.isfinite(sr) else 0.0,
        "annual_return": float((1 + test).prod() ** (PERIODS_PER_YEAR_1H / max(len(test), 1)) - 1),
        "vol": float(np.std(arr, ddof=1) * math.sqrt(PERIODS_PER_YEAR_1H)),
        "max_drawdown": float(max_drawdown_from_returns(arr)),
        "monthly_mean": float(monthly.mean()) if len(monthly) else 0.0,
        "p_monthly_geq_5pct": float((monthly >= 0.05).mean()) if len(monthly) else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake-root", default="data/lake/curated")
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    args = parser.parse_args()
    lake_root = Path(args.lake_root)
    out_dir = Path(args.out_dir)

    results: list[dict[str, Any]] = []
    strats: dict[str, pd.Series] = {}
    pairs_loaded = 0
    for pair in sorted(set(FX_PAIRS)):
        s = load_fx_1h(lake_root, pair)
        if s is None:
            continue
        pairs_loaded += 1
        for w in TSMOM_WINDOWS_DAYS:
            leg = tsmom_leg(s, w)
            strats[f"tsmom{w}_{pair}"] = leg

    print(f"FX pairs loaded: {pairs_loaded}")
    xs = xsmom_family(lake_root)
    if xs is not None:
        strats["xsmom_fx_30d"] = xs
    print(f"legs built: {len(strats)}")

    df = pd.DataFrame(strats)
    # combined portfolio: mean of TSMOM legs per window + xs family
    port = df.mean(axis=1)

    family_keys = {
        "xsmom_fx_30d": ["xsmom_fx_30d"],
        "tsmom30": [c for c in df.columns if c.startswith("tsmom30_")],
        "tsmom90": [c for c in df.columns if c.startswith("tsmom90_")],
        "tsmom180": [c for c in df.columns if c.startswith("tsmom180_")],
    }
    for name, cols in family_keys.items():
        if cols:
            fam = df[cols]
            results.append(_metrics(name, fam.mean(axis=1)))
    results.append(_metrics("portfolio_fx_ew", port))

    print(f"{'leg':<24} {'SR':>6} {'ann ret':>9} {'vol':>7} {'MaxDD':>7} {'P(m≥5%)':>8}")
    for r in results:
        print(
            f"{r['name']:<24} {r['sharpe']:>6.2f} {r['annual_return']:>9.2%} "
            f"{r['vol']:>7.2%} {r['max_drawdown']:>7.1%} {r['p_monthly_geq_5pct']:>8.1%}"
        )

    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "BL-738 FX orthogonal legs — TSMOM + XSMOM on Dukascopy spot 1h",
        "n_pairs": pairs_loaded,
        "n_legs": len(strats),
        "parameters": {
            "test_split": str(TEST_SPLIT),
            "tsmom_windows_days": list(TSMOM_WINDOWS_DAYS),
            "xs_lookback_days": XS_LOOKBACK_DAYS,
            "cost_bps_per_turnover": COST_BPS_PER_TURNOVER,
            "target_vol": TARGET_VOL,
        },
        "results": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fx-orthogonal-legs.json").write_text(json.dumps(payload, indent=2, default=str))
    lines = [
        "# BL-738 — FX orthogonal legs (TSMOM + XSMOM, spot 1h Dukascopy)",
        "",
        f"**Generated**: {payload['generated']}",
        "",
        f"{pairs_loaded} pairs, {len(strats)} legs, walk-forward > {TEST_SPLIT.date()}, "
        f"costs {COST_BPS_PER_TURNOVER} bps/turnover.",
        "",
        "| leg | SR | ann ret | vol | MaxDD | P(m≥5%) |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['sharpe']:+.2f} | {r['annual_return']:+.1%} | "
            f"{r['vol']:.1%} | {r['max_drawdown']:.1%} | {r['p_monthly_geq_5pct']:.1%} |"
        )
    (out_dir / "fx-orthogonal-legs.md").write_text("\n".join(lines) + "\n")
    print(f"\nReport → {out_dir / 'fx-orthogonal-legs.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
