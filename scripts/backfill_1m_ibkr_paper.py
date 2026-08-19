"""Step 6 Opzione C — IBKR paper 1m backfill cron (going forward).

Daily cron that fetches the last 24h of 1m bars for ES/NQ/GC/CL via
the IBKRHistorical adapter, merges into the lake via the standard
pipeline. Going-forward accumulation only — does NOT backfill pre-2025
history (IBKR API gives only ~6-12 months via reqHistoricalData).

Systemd timer (cron-style):
    ~/.config/systemd/user/oracle-ibkr-backfill.service
    ~/.config/systemd/user/oracle-ibkr-backfill.timer

Run once for testing:
    uv run python scripts/backfill_1m_ibkr_paper.py
    uv run python scripts/backfill_1m_ibkr_paper.py --symbols SPY,AAPL
    uv run python scripts/backfill_1m_ibkr_paper.py --days 7

Prerequisite: ib-gateway container running on port 4002 (paper alinsaba99).
Note (2026-08-17 smoke test): IB Gateway container is in Read-Only mode
AND futures contract resolution requires explicit expiry/localSymbol —
the IBKRHistorical adapter passes a generic ES FUT contract without
expiry, IBKR rejects with "Please enter a local symbol or an expiry".
Equities (SPY/AAPL/MSFT/QQQ) work without this complication. So the
default symbol set here is US equities; futures are commented until the
adapter supports expiry resolution (TODO BL-OPC-6-followup).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Equities work with IBKR paper Read-Only + generic SMART contract.
# Futures need explicit expiry (TODO adapter followup).
DEFAULT_SYMBOLS = ("SPY", "QQQ", "AAPL", "MSFT")
DEFAULT_PORT = "4002"  # IB Gateway paper mode (not 7497)


def main() -> int:
    parser = argparse.ArgumentParser(description="IBKR paper 1m backfill (going forward)")
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help=f"Comma-separated futures symbols (default: {','.join(DEFAULT_SYMBOLS)})",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Days to backfill (default 1 = last 24h; IBKR gives ~6-12m max)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("IBKR_PORT", DEFAULT_PORT)),
        help="IB Gateway port (default 4002 paper; 7497 = TWS live). Env: IBKR_PORT",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("IBKR_HOST", "127.0.0.1"),
        help="IB Gateway host (default 127.0.0.1). Env: IBKR_HOST",
    )
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    end = date.today()
    start = end - timedelta(days=args.days)

    print(f"\n{'=' * 70}")
    print("IBKR paper 1m backfill — going forward")
    print(f"{'=' * 70}")
    print(f"Symbols: {symbols}")
    print(f"Range:   {start} → {end} ({args.days} day(s))")
    print(f"Gateway: {args.host}:{args.port}")
    print()

    # Lazy import — ib_insync + market.ingestion pull many subdeps.
    # Patch IBKRHistorical port: adapter default is 7497 (TWS live); we
    # use 4002 (IB Gateway paper mode). Override via the IBKRHistorical
    # constructor before run_plan so the orchestrator picks the right port.
    # Must patch BOTH the SOURCES registry (used by pipeline.get_source)
    # AND run_plan's direct lookup path.
    from market.ingestion import sources as src_mod
    from market.ingestion.orchestrator import BackfillEntry, run_plan
    from market.ingestion.types import SourceId

    # Swap the IBKR singleton bound into SOURCES registry with our port.
    bound = src_mod.IBKRHistorical(host=args.host, port=args.port)
    src_mod.SOURCES[SourceId.IBKR] = bound

    # Also patch get_source so pipeline.fetch picks up the bound instance.
    def _patched_get_source(source_id: SourceId) -> src_mod.DataSource:
        return bound if source_id == SourceId.IBKR else src_mod.SOURCES[source_id]

    src_mod.get_source = _patched_get_source

    entries = [
        BackfillEntry(symbol=sym, timeframe="1m", source="ibkr", start=start, end=end)
        for sym in symbols
    ]

    exit_code = run_plan(entries)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
