#!/usr/bin/env python3
"""BL-736 — Portfolio SR-max discovery: combined multi-family portfolio.

Objective (user goal 2026-09-04): minimum target 5%/month net portfolio
return.  Honest method: no alpha inflation — build the highest-Sharpe
portfolio from the *already qualified* orthogonal edges, apply leverage
in multiples, and measure what P(m >= 5%) is actually reachable.

Legs (all previously qualified, no new fitting):
  - Lane A daily ensemble legs (run_multi_strategy_ensemble DEFAULT_LEGS):
    trend/breakout/mean-reversion/alpha101 on ES/SPY/BTC/ETH/EURUSD 1d.
  - Crypto microstructure 1h legs (Sprint 2c): funding_z sized on
    ETH/XRP/ADA, basis carry on ETH/BTC — smoothed, rebanded, cost-aware.

Method (frozen):
  - Each leg: vol-targeted, costs 10 bps/turnover, walk-forward
    test window > 2022-12-31.
  - Portfolio: equal-weight across legs on the common daily index.
  - Leverage grid: 1.0, 1.5, 2.0, 3.0, 4.0 applied to the *net* portfolio
    returns (borrow cost ignored for crypto spot; documented).
  - Report: per-leg Sharpe, portfolio Sharpe, P(m >= 5%) per leverage,
    and the honest gap to the 5%/month target.

Outputs:
    docs/reports/edge-factory/portfolio-sr-max.md
    docs/reports/edge-factory/portfolio-sr-max.json

Usage:
    uv run --frozen python scripts/run_portfolio_sr_max.py
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
sys.path.insert(0, str(ROOT / "scripts"))

from run_factory_sprint2_qualification import load_funding_onto_prices  # noqa: E402
from run_factory_sprint2b_extended import perp_spot_basis  # noqa: E402
from run_factory_sprint2c_trading import (  # noqa: E402
    BASIS_ASSETS,
    FUNDING_ASSETS,
    basis_strategy,
    funding_z_strategy,
)
from run_multi_strategy_ensemble import DEFAULT_LEGS, backtest_leg, load_asset_1d  # noqa: E402

from analytics.metrics.canonical import (  # ADR-021  # noqa: E402
    max_drawdown_from_returns,
    sharpe_ratio,
)

TEST_SPLIT = pd.Timestamp("2022-12-31", tz="UTC")
PERIODS_PER_YEAR_1D = 252
LEVERAGE_GRID = (1.0, 1.5, 2.0, 3.0, 4.0)
MONTHLY_TARGET = 0.05


@dataclass
class LeveragePoint:
    leverage: float
    annual_return: float
    annual_vol: float
    sharpe: float
    max_drawdown: float
    monthly_mean: float
    p_monthly_geq_5pct: float
    months_positive: int
    months_total: int


def _hourly_to_daily(strat: pd.Series) -> pd.Series:
    """Aggregate an hourly strategy return stream to daily returns (naive UTC)."""
    s = strat.copy()
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    return (1.0 + s).resample("1D").prod() - 1.0


def _load_daily_legs() -> dict[str, pd.Series]:
    """Backtest the Lane A daily legs (same engine as the ensemble report)."""
    legs: dict[str, pd.Series] = {}
    start, end = datetime(2020, 1, 1), datetime(2025, 12, 31)
    for leg in DEFAULT_LEGS:
        try:
            df = load_asset_1d(leg["asset"], start, end)
        except FileNotFoundError:
            print(f"SKIP daily leg {leg['name']}: no lake data")
            continue
        res, _pos = backtest_leg(
            df,
            leg["signal"],
            leg["name"],
            leg["family"],
            leg["asset"],
            datetime(2022, 12, 31),
            target_vol=0.12,
        )
        rets = np.asarray(res.daily_returns, dtype=np.float64)
        idx = pd.to_datetime(df["timestamp"].to_list()[-len(rets) :])
        legs[leg["name"]] = pd.Series(rets, index=idx, name=leg["name"])
    return legs


def _load_crypto_1h_legs(args: argparse.Namespace) -> dict[str, pd.Series]:
    """Backtest the Sprint 2c crypto 1h legs, aggregated to daily."""
    funding_dir, lake_root, perp_dir = (
        Path(args.funding_dir),
        Path(args.lake_root),
        Path(args.perp_dir),
    )
    legs: dict[str, pd.Series] = {}
    for asset in FUNDING_ASSETS:
        loaded = load_funding_onto_prices(funding_dir, lake_root, asset)
        if loaded is None:
            continue
        close, funding = loaded
        legs[f"funding_z_{asset}"] = _hourly_to_daily(funding_z_strategy(close, funding))
    for asset in BASIS_ASSETS:
        basis = perp_spot_basis(perp_dir, lake_root, asset)
        if basis is None:
            continue
        spot = pd.read_parquet(lake_root / f"{asset}_1h.parquet", columns=["timestamp", "close"])
        spot.index = pd.to_datetime(spot["timestamp"], utc=True)
        spot = spot["close"].astype(float).sort_index()
        spot = spot[~spot.index.duplicated(keep="last")]
        legs[f"basis_{asset}"] = _hourly_to_daily(basis_strategy(basis, spot))
    return legs


def _portfolio_ew(legs: dict[str, pd.Series]) -> pd.Series:
    df = pd.DataFrame(legs)
    common = df.dropna(how="all").fillna(0.0)
    return common.mean(axis=1)


def _leverage_metrics(port: pd.Series, lev: float) -> LeveragePoint:
    rets = port * lev
    arr = rets.to_numpy()
    monthly = rets.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    sr = sharpe_ratio(arr, periods_per_year=PERIODS_PER_YEAR_1D)
    return LeveragePoint(
        leverage=lev,
        annual_return=float((1 + rets).prod() ** (252 / max(len(rets), 1)) - 1),
        annual_vol=float(np.std(arr, ddof=1) * math.sqrt(252)),
        sharpe=float(sr) if np.isfinite(sr) else 0.0,
        max_drawdown=float(max_drawdown_from_returns(arr)),
        monthly_mean=float(monthly.mean()),
        p_monthly_geq_5pct=float((monthly >= MONTHLY_TARGET).mean()),
        months_positive=int((monthly > 0).sum()),
        months_total=len(monthly),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--funding-dir", default="data/lake/raw/funding")
    parser.add_argument("--perp-dir", default="data/lake/raw/perp")
    parser.add_argument("--lake-root", default="data/lake/curated")
    parser.add_argument("--out-dir", default="docs/reports/edge-factory")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)

    daily = _load_daily_legs()
    print(f"daily legs loaded: {len(daily)}")
    crypto = _load_crypto_1h_legs(args)
    print(f"crypto 1h legs loaded: {len(crypto)}")
    all_legs = {**daily, **crypto}

    # walk-forward test window only; drop degenerate legs (tz-normalised)
    cut = TEST_SPLIT.tz_localize(None)
    all_legs = {k: v[v.index.tz_localize(None) > cut] for k, v in all_legs.items()}
    all_legs = {
        k: v for k, v in all_legs.items() if len(v) > 100 and float(np.std(v.to_numpy())) > 0
    }

    per_leg: list[dict[str, Any]] = []
    for name, s in sorted(all_legs.items()):
        arr = s.to_numpy()
        sr = sharpe_ratio(arr, periods_per_year=PERIODS_PER_YEAR_1D)
        per_leg.append(
            {
                "name": name,
                "sharpe": float(sr) if np.isfinite(sr) else 0.0,
                "annual_return": float((1 + s).prod() ** (252 / len(s)) - 1),
                "vol": float(np.std(arr, ddof=1) * math.sqrt(252)),
            }
        )

    port = _portfolio_ew(all_legs)
    rows = [_leverage_metrics(port, lev) for lev in LEVERAGE_GRID]

    print(
        f"\nPortfolio equal-weight across qualified legs (test > 2022-12-31), {len(all_legs)} legs:"
    )
    print(
        f"{'lev':>4} {'ann ret':>9} {'vol':>7} {'SR':>6} {'MaxDD':>7} {'m-mean':>7} {'P(m≥5%)':>8}"
    )
    for r in rows:
        print(
            f"{r.leverage:>4.1f} {r.annual_return:>9.2%} {r.annual_vol:>7.2%} "
            f"{r.sharpe:>6.2f} {r.max_drawdown:>7.1%} {r.monthly_mean:>7.2%} "
            f"{r.p_monthly_geq_5pct:>8.1%}"
        )

    payload: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(),
        "framework": "BL-736 portfolio SR-max — combined multi-family portfolio",
        "legs": sorted(all_legs),
        "per_leg": per_leg,
        "leverage_grid": list(LEVERAGE_GRID),
        "leverage_points": [asdict(r) for r in rows],
        "honest_note": (
            "5%/month net requires SR ~4 at 20% vol; leverage scales return "
            "AND drawdown — this report measures the true gap without inflation."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "portfolio-sr-max.json").write_text(json.dumps(payload, indent=2, default=str))

    lines = [
        "# BL-736 — Portfolio SR-max (combined qualified edges)",
        "",
        f"**Generated**: {payload['generated']}",
        "",
        f"{len(all_legs)} legs, equal-weight, walk-forward test > 2022-12-31, "
        "costs included per-leg (10 bps/turnover).",
        "",
        "## Per-leg (test window)",
        "",
        "| leg | SR | ann ret | vol |",
        "|---|---|---|---|",
    ]
    for leginfo in per_leg:
        lines.append(
            f"| {leginfo['name']} | {leginfo['sharpe']:+.2f} | "
            f"{leginfo['annual_return']:+.1%} | {leginfo['vol']:.1%} |"
        )
    lines += [
        "",
        "## Leverage ladder",
        "",
        "| lev | ann ret | vol | SR | MaxDD | m-mean | P(m≥5%) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.leverage:.1f}× | {r.annual_return:+.1%} | {r.annual_vol:.1%} | "
            f"{r.sharpe:+.2f} | {r.max_drawdown:.1%} | {r.monthly_mean:+.2%} | "
            f"{r.p_monthly_geq_5pct:.1%} |"
        )
    lines += ["", "## Honest note", "", payload["honest_note"], ""]
    (out_dir / "portfolio-sr-max.md").write_text("\n".join(lines) + "\n")
    print(f"\nReport → {out_dir / 'portfolio-sr-max.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
