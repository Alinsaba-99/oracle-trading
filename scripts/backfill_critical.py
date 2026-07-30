#!/usr/bin/env python3
"""Targeted backfill — fetch critical missing data for the strategy sweep.

Fills gaps that were identified during the BL-301 data lake audit.

Usage:
    uv run --frozen python scripts/backfill_critical.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market.ingestion.pipeline import Pipeline
from market.ingestion.types import SourceId


async def main() -> int:
    pipe = Pipeline()
    today = date.today()

    backfill_plan = [
        # ES futures 1h via yfinance (~2 years of 1h bars)
        ("ES", "1h", SourceId.YAHOO, date(2024, 7, 28), today),
        # SPY daily via yfinance (1993→today for long-term equity backtests)
        ("SPY", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
        # NQ futures daily for cross-asset sweep
        ("NQ", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
        # GC (Gold) daily for commodity futures
        ("GC", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
        # CL (Crude) daily for commodity futures
        ("CL", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
        # EURUSD daily from yfinance (backup source for cross-validation)
        ("EURUSD", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
    ]

    print(f"Targeted backfill: {len(backfill_plan)} items")
    print(f"{'=' * 60}")

    success = 0
    failed = 0
    for symbol, tf, source, start, end in backfill_plan:
        print(f"  [{symbol} {tf} via {source.value}] ", end="", flush=True)
        report = pipe.fetch(symbol, tf, source, start=start, end=end)
        if report.note.startswith("FAILED"):
            print(f"❌ {report.note}")
            failed += 1
        else:
            print(
                f"✅ {report.rows_in} in → {report.rows_out} out "
                f"({report.rows_rejected} rejected) in {report.duration_s:.1f}s"
            )
            success += 1

    print(f"{'=' * 60}")
    print(f"Done: {success} succeeded, {failed} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
