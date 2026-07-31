#!/usr/bin/env python3
"""Build curated continuous futures contracts from normalized partitions.

Merges all Hive partitions for each (symbol, timeframe) into a single
curated parquet: data/lake/curated/<SYMBOL>_<TF>.parquet

Continuous contract semantics: the normalized data is already a
continuous (roll-adjusted by provider, e.g. Yahoo ES=F) series. This
script consolidates + validates continuity (monotonic timestamps, no
duplicate bars, gap report).

Usage:
    uv run python scripts/build_curated_contracts.py [--tf 1h] [--symbols ES,NQ]

Symbols default to auto-discovery: every symbol present in the lake for the
requested timeframe (futures, FX and crypto alike). Gap threshold is
timeframe-aware (1m=2h, 1h=4h, 4h=8h, 1d=72h) — override with --gap-hours.
Note: for 1m FX/crypto, weekend pauses (~48h) are expected and reported as
gaps; they are informational, not failures.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LAKE = Path("data/lake/normalized")
CURATED = Path("data/lake/curated")

GAP_HOURS_DEFAULT: dict[str, int] = {"1m": 2, "1h": 4, "4h": 8, "1d": 72}


def discover_symbols(tf: str) -> list[str]:
    """All symbols in the lake with partitions for this timeframe."""
    syms = []
    for d in sorted(LAKE.glob("symbol=*")):
        if (d / f"tf={tf}").exists():
            syms.append(d.name.removeprefix("symbol="))
    return syms


def build_contract(symbol: str, tf: str, gap_hours: int) -> dict[str, Any]:
    """Merge partitions for one (symbol, tf) into curated. Returns stats."""
    parts = sorted((LAKE / f"symbol={symbol}" / f"tf={tf}").glob("year=*/*.parquet"))
    if not parts:
        return {"symbol": symbol, "tf": tf, "status": "NO_DATA"}
    df = pl.concat([pl.read_parquet(p) for p in parts])
    df = df.unique(subset=["timestamp"], keep="last").sort("timestamp")

    # Continuity checks
    n_before = len(df)
    dupes = n_before - df.unique(subset=["timestamp"]).height
    ts = df["timestamp"]
    gap_s = gap_hours * 3600
    gaps = (ts.diff().dt.total_seconds() > gap_s).sum() if len(df) > 1 else 0

    CURATED.mkdir(parents=True, exist_ok=True)
    out = CURATED / f"{symbol}_{tf}.parquet"
    df.write_parquet(out)
    return {
        "symbol": symbol,
        "tf": tf,
        "status": "OK",
        "rows": len(df),
        "dupes_removed": dupes,
        "gaps_gt_threshold": int(gaps),
        "earliest": str(ts[0])[:10],
        "latest": str(ts[-1])[:10],
        "file": str(out),
        "size_mb": round(out.stat().st_size / 1e6, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build curated continuous contracts")
    parser.add_argument("--tf", default="1h", help="Timeframe to build (default: 1h)")
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated symbols (default: all symbols present in the lake)",
    )
    parser.add_argument(
        "--gap-hours",
        type=int,
        default=None,
        help="Gap threshold in hours (default: tf-aware: 1m=2h, 1h=4h, 4h=8h, 1d=72h)",
    )
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else discover_symbols(args.tf)
    gap_hours = args.gap_hours or GAP_HOURS_DEFAULT.get(args.tf, 4)
    print(
        f"Building curated {args.tf} contracts for {len(symbols)} symbols "
        f"(gap threshold: {gap_hours}h)..."
    )
    gap_label = f"Gaps>{gap_hours}h"
    header = (
        f"{'Sym':5s} {'Rows':>8s} {'Dupes':>6s} {gap_label:>10s}  {'Range':22s} {'MB':>5s}  Status"
    )
    print(header)
    total_rows = 0
    for sym in symbols:
        r = build_contract(sym, args.tf, gap_hours)
        if r["status"] == "OK":
            total_rows += r["rows"]
            print(
                f"{sym:5s} {r['rows']:>8,} {r['dupes_removed']:>6d} "
                f"{r['gaps_gt_threshold']:>10d}  {r['earliest']} → {r['latest']} "
                f"{r['size_mb']:>5.1f}  ✅"
            )
        else:
            print(f"{sym:5s} {'-':>8s} {'-':>6s} {'-':>10s}  {'':22s} {'-':>5s}  ⚠️  NO_DATA")
    print(f"\nTotal curated rows ({args.tf}): {total_rows:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
