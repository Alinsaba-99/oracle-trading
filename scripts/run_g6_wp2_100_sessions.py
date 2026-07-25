"""BL-020 — 100 paper sessions independent su piu' asset (cross-asset).

Comportamento:
- Default: 30 sessioni non-overlapping ES 1d pinned (BL-022)
- Con --btc: 30 sessioni non-overlapping BTC/USDT 1h
- Con --n 100 + --bars: catena 100 finestre di 95 bar da 1h intraday

Output: logs/<tag>.json con per-session + summary.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

import scripts.run_g6_wp2_paper_sessions as base  # type: ignore[import-not-found]


DEFAULT_INSTRUMENT_BY_DATA = {
    "data/ohlcv/ES_1d.parquet": ("ES", 50.0),
    "data/ohlcv/BTC_USDT_1h.parquet": ("BTC_USDT", 50.0),
}


async def _run_paper(
    n: int, data_path: str, instrument: str | None, point_value: float | None, capital: float, output: str
) -> int:
    df = pl.read_parquet(data_path).rename({c: c.lower() for c in pl.read_parquet(data_path).columns})
    n_total = len(df)
    n_per_session = n_total // n
    if n_per_session < 5:
        print(f"ERROR: not enough bars ({n_total}) for {n} sessions at {data_path}")
        return 1

    if instrument is None:
        instrument = DEFAULT_INSTRUMENT_BY_DATA.get(data_path, ("ES", 50.0))[0]
    if point_value is None:
        point_value = DEFAULT_INSTRUMENT_BY_DATA.get(data_path, ("ES", 50.0))[1]

    point_value_dec = Decimal(str(point_value))
    capital_dec = Decimal(str(capital))

    window = 100  # minimum for regime heuristic
    step = max(1, (n_total - window) // n) if n_total > window else 1
    results: list[dict] = []
    for i in range(n):
        start = i * step
        df_session = df[start : start + window]
        if len(df_session) < window:
            df_session = df[max(0, n_total - window) :]
        res = await base._run_session(
            session_id=i + 1,
            df_session=df_session,
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
    shs = [r["sharpe"] for r in results]
    dds = [r["max_drawdown_pct"] for r in results]

    summary = {
        "metadata": {
            "data": data_path,
            "n_bars": n_total,
            "n": n,
            "instrument": instrument,
            "point_value": point_value,
            "capital": capital,
            "timestamp": datetime.now(UTC).isoformat(),
            "bl": "BL-020",
        },
        "gate": {
            "decision": "approved" if passed / n >= 0.9 and statistics.mean(shs) >= -0.5 and statistics.mean(dds) <= 3 else "rejected",
            "pass_rate": round(passed / n, 4),
            "mean_sharpe": round(statistics.mean(shs), 4),
            "mean_drawdown_pct": round(statistics.mean(dds), 4),
        },
        "results": results,
    }

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(summary, indent=2, default=str))
    print(f"\n  {n} sessions on {data_path}")
    print(f"  Pass rate: {passed / n:.0%} (target >= 90%)")
    print(f"  Mean Sharpe: {statistics.mean(shs):.4f} (target >= -0.5)")
    print(f"  Mean DD: {statistics.mean(dds):.2f}% (target <= 3%)")
    print(f"  Decision: {summary['gate']['decision']}")
    print(f"  Saved to {output}")
    return 0 if summary["gate"]["decision"] == "approved" else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--data", default="data/ohlcv/ES_1d.parquet")
    p.add_argument("--instrument", default=None)
    p.add_argument("--point-value", type=float, default=None)
    p.add_argument("--capital", type=float, default=100_000.0)
    p.add_argument("--output", default="logs/g6_wp2_30_default.json")
    args = p.parse_args()
    return asyncio.run(
        _run_paper(
            args.n, args.data, args.instrument, args.point_value, args.capital, args.output
        )
    )


if __name__ == "__main__":
    sys.exit(main())