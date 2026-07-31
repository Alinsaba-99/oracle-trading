#!/usr/bin/env python3
"""Backfill 1m for all CME futures — last 30 days (yfinance max depth).

Yahoo serves 1m only within the last 30 days (server-side limit, proven
empirically 2026-07-31). This script paginates 5-day windows inside the
30-day horizon and merges into the lake via the standard pipeline.

Usage:
    uv run python scripts/backfill_1m_30d.py            # all 35 futures
    uv run python scripts/backfill_1m_30d.py --symbols ES,NQ
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market.ingestion.orchestrator import BackfillEntry, run_plan

FUTURES = [
    "ES",
    "NQ",
    "YM",
    "RTY",
    "MES",
    "MNQ",
    "MYM",
    "CL",
    "NG",
    "RB",
    "HO",
    "MCL",
    "GC",
    "SI",
    "HG",
    "PL",
    "PA",
    "MGC",
    "ZN",
    "ZB",
    "ZF",
    "ZT",
    "ZC",
    "ZW",
    "ZS",
    "ZM",
    "ZL",
    "6E",
    "6J",
    "6B",
    "6A",
    "6C",
    "6N",
    "6S",
    "M6E",
]

WINDOW_DAYS = 5  # yfinance 1m windows smaller than 7d are safest
MAX_BACK_DAYS = 30


def build_entries(symbols: list[str]) -> list[BackfillEntry]:
    """Build 5-day paginated 1m entries within the 30-day horizon."""
    today = date.today()
    entries: list[BackfillEntry] = []
    end = today
    while (today - end).days < MAX_BACK_DAYS:
        start = end - timedelta(days=WINDOW_DAYS)
        for sym in symbols:
            entries.append(BackfillEntry(sym, "1m", "yahoo", start, end))
        end = start - timedelta(days=1)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill 1m futures (30 days max)")
    parser.add_argument("--symbols", default=None, help="Comma-separated subset")
    parser.add_argument("--days", type=int, default=MAX_BACK_DAYS)
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else FUTURES
    entries = build_entries(symbols)
    print(
        f"Backfilling 1m for {len(symbols)} symbols × {args.days}d windows = {len(entries)} fetches"
    )
    rc = run_plan(entries, max_runtime_s=3600, pause_between_s=0.2)
    print(f"Exit code: {rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
