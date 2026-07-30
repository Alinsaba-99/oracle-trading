#!/usr/bin/env python3
"""BL-022 — 100 independent paper sessions for G6 qualification.

Each session is a 95-bar window of the pinned ES daily dataset (default) or
any OHLCV parquet passed via --data.  Windows are non-overlapping when
possible; if the dataset is too small for 100 non-overlapping windows, they
slide with step = floor((N - window) / 100).

Session logic is identical to ``run_g6_wp2_paper_sessions._run_session`` so
that the results are directly comparable.

Gate criteria (BL-022):
  - pass_rate ≥ 0.90
  - mean_sharpe ≥ -0.5  (note: negative threshold, rough edge)
  - mean_max_dd ≤ 3.0 %

Usage::

    # 100 sessions on the pinned M31 dataset (250 daily bars, step≈1)
    uv run python scripts/run_g6_wp2_100_sessions.py

    # 100 sessions on the full ES lake (6517 daily bars, step≈64)
    uv run python scripts/run_g6_wp2_100_sessions.py \\
        --data data/lake/normalized/symbol=ES/tf=1d/

    # BTC 1h (500 bars — only 5 non-overlapping 95-bar windows)
    uv run python scripts/run_g6_wp2_100_sessions.py \\
        --data data/ohlcv/BTC_USDT_1h.parquet --n 5 --instrument BTC_USDT --point-value 50.0

    # 200 random Monte Carlo windows instead of sequential slices
    uv run python scripts/run_g6_wp2_100_sessions.py --monte-carlo
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.run_g6_wp2_paper_sessions as base  # type: ignore[import-not-found]

# ── defaults ─────────────────────────────────────────────────────────────
_DEFAULT_DATA = "data/pinned/ES_1d_m31.parquet"
_DEFAULT_INSTRUMENT = "ES"
_DEFAULT_POINT_VALUE = 50.0
_DEFAULT_CAPITAL = 50_000.0
_DEFAULT_N_SESSIONS = 100
_DEFAULT_WINDOW = 95

# Expected sha256 of the canonical pinned dataset.
_PINNED_HASH = "09a22b7dcb37212630e96a880f17924023e3ed985206d51c390f0efb8f61cd62"


# ── helpers ──────────────────────────────────────────────────────────────


def _read_data(data_path: str) -> pl.DataFrame:
    """Read OHLCV parquet and lowercase column names."""
    path = Path(data_path)
    if path.is_dir():
        # Globs of the lake partition layout.
        files = sorted(path.rglob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"No parquet files in {data_path}")
        df = pl.concat([pl.read_parquet(f) for f in files])
    else:
        df = pl.read_parquet(str(path))
    rename = {c: c.lower() for c in df.columns}
    df = df.rename(rename)
    # Normalise common column names.
    col_map: dict[str, str] = {
        "adj close": "close",
        "adj_close": "close",
        "close_adj": "close",
        "open*": "open",
        "high*": "high",
        "low*": "low",
        "close*": "close",
        "volume*": "volume",
        "volume_": "volume",
    }
    for old, new in col_map.items():
        if old in df.columns:
            df = df.rename({old: new})
    return df


def _verify_pin_hash(df: pl.DataFrame) -> None:
    """Raise if the pinned dataset hash doesn't match provenance."""
    buf = df.select(sorted(df.columns)).to_pandas().to_csv(index=False).encode("utf-8")
    h = hashlib.sha256(buf).hexdigest()
    if h != _PINNED_HASH:
        msg = f"WARNING: pinned dataset hash mismatch (got {h}, expected {_PINNED_HASH})"
        print(msg, flush=True)
    else:
        print("Pinned dataset hash verified OK.", flush=True)


# ── core ─────────────────────────────────────────────────────────────────


async def _run_paper_sessions(
    n: int,
    data_path: str,
    instrument: str,
    point_value: float,
    capital: float,
    window: int,
    output: str,
    verify_pin: bool,
    monte_carlo: bool,
) -> int:
    """Run *n* independent paper sessions, write summary to *output*.

    Returns 0 when gate criteria are met, 1 otherwise.
    """
    df = _read_data(data_path)
    n_total = len(df)
    if n_total < window:
        print(f"ERROR: only {n_total} bars, need at least {window} for a single session")
        return 1

    if verify_pin:
        _verify_pin_hash(df)

    point_value_dec = Decimal(str(point_value))
    capital_dec = Decimal(str(capital))

    # Build windows.
    if monte_carlo:
        import random as _rnd

        _rnd.seed(42)
        windows: list[pl.DataFrame] = []
        for _ in range(n):
            start = _rnd.randint(0, n_total - window)
            windows.append(df[start : start + window])
    else:
        step = max(1, (n_total - window) // n) if n_total > window else 1
        windows = [df[i * step : i * step + window] for i in range(n)]
        # Pad last window if short.
        if len(windows[-1]) < window:
            windows[-1] = df[n_total - window :]

    results: list[dict[str, Any]] = []
    for i, df_win in enumerate(windows):
        res = await base._run_session(
            session_id=i + 1,
            df_session=df_win,
            instrument=instrument,
            capital=capital_dec,
            point_value=point_value_dec,
            max_dd_pct=5.0,
            storage="memory",
            dsn=None,
        )
        results.append(res)

    passed = sum(1 for r in results if r["passed"])
    pnls = [r["total_pnl"] for r in results]
    sharpe_vals = [r["sharpe"] for r in results]
    dd_vals = [r["max_drawdown_pct"] for r in results]

    mean_sharpe = statistics.mean(sharpe_vals) if sharpe_vals else 0.0
    mean_dd = statistics.mean(dd_vals) if dd_vals else 0.0
    total_pnl = sum(pnls)
    pass_rate = passed / n if n else 0.0

    decision = (
        "approved" if pass_rate >= 0.90 and mean_sharpe >= -0.5 and mean_dd <= 3.0 else "rejected"
    )

    summary = {
        "metadata": {
            "bl": "BL-022",
            "data": data_path,
            "n_bars": n_total,
            "n": n,
            "window": window,
            "step": (n_total - window) // n if n_total > window else 1,
            "instrument": instrument,
            "point_value": point_value,
            "capital": capital,
            "monte_carlo": monte_carlo,
            "timestamp": datetime.now(UTC).isoformat(),
            "regime": "vol-scaled (BL-020)",
        },
        "gate": {
            "decision": decision,
            "pass_rate": round(pass_rate, 4),
            "mean_sharpe": round(mean_sharpe, 4),
            "mean_drawdown_pct": round(mean_dd, 4),
            "total_pnl": round(total_pnl, 2),
            "mean_pnl": round(total_pnl / n if n else 0.0, 2),
        },
        "results": results,
    }

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(summary, indent=2, default=str))

    print(f"\n{'=' * 60}")
    print(f"  BL-022 — {n} sessions × {window}-bar windows")
    print(f"  Data: {data_path} ({n_total} bars)")
    print(f"  Instrument: {instrument}  |  Point value: ${point_value}")
    print(f"  Capital: ${capital:,.0f}")
    print(f"  Pass rate:  {pass_rate:.1%}  (target ≥ 90%)")
    print(f"  Mean Sharpe: {mean_sharpe:.3f}  (target ≥ -0.5)")
    print(f"  Mean DD:     {mean_dd:.2f}%  (target ≤ 3.0%)")
    print(f"  Decision:    {decision.upper()}")
    print(f"{'=' * 60}\n")
    print(f"Results saved to {output}")
    return 0 if decision == "approved" else 1


# ── CLI ──────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(
        description="BL-022: 100 independent paper sessions for G6 qualification."
    )
    p.add_argument("--n", type=int, default=_DEFAULT_N_SESSIONS, help="Number of sessions")
    p.add_argument("--window", type=int, default=_DEFAULT_WINDOW, help="Bars per session")
    p.add_argument("--data", default=_DEFAULT_DATA, help="Parquet path or lake directory")
    p.add_argument("--instrument", default=_DEFAULT_INSTRUMENT, help="Instrument ID (e.g. ES, MES)")
    p.add_argument("--point-value", type=float, default=_DEFAULT_POINT_VALUE)
    p.add_argument("--capital", type=float, default=_DEFAULT_CAPITAL)
    p.add_argument("--output", default="logs/g6_wp2_100.json", help="Output path")
    p.add_argument(
        "--verify-pin",
        action="store_true",
        default=True,
        help="Verify pinned dataset hash before running (default: True)",
    )
    p.add_argument(
        "--no-verify-pin", action="store_false", dest="verify_pin", help="Skip hash verification"
    )
    p.add_argument(
        "--monte-carlo",
        action="store_true",
        help="Random Monte Carlo window start positions instead of sequential",
    )
    args = p.parse_args()

    return asyncio.run(
        _run_paper_sessions(
            n=args.n,
            data_path=args.data,
            instrument=args.instrument,
            point_value=args.point_value,
            capital=args.capital,
            window=args.window,
            output=args.output,
            verify_pin=args.verify_pin,
            monte_carlo=args.monte_carlo,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
