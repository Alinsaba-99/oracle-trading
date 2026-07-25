"""BL-301 — CLI entry-point for the data lake pipeline.

Examples:
  python -m market.ingestion.cli status
  python -m market.ingestion.cli fetch BTCUSDT 1d cryptodata --full
  python -m market.ingestion.cli fetch ES 1d stooq
  python -m market.ingestion.cli run-plan
"""
from __future__ import annotations

import argparse
import logging

from market.ingestion.orchestrator import run_plan
from market.ingestion.pipeline import cli_fetch, cli_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Data lake CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="Show coverage report")

    f = sub.add_parser("fetch", help="Fetch a single (symbol, tf, source)")
    f.add_argument("symbol")
    f.add_argument("timeframe")
    f.add_argument("source")
    f.add_argument("--start")
    f.add_argument("--end")
    f.add_argument("--full", action="store_true")

    sub.add_parser("run-plan", help="Run the YAML backfill plan")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.cmd == "status":
        return cli_status()
    if args.cmd == "fetch":
        return cli_fetch(
            args.symbol,
            args.timeframe,
            args.source,
            start=args.start,
            end=args.end,
            full=args.full,
        )
    if args.cmd == "run-plan":
        return run_plan()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
