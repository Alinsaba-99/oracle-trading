#!/usr/bin/env python3
"""Backfill — scarica TUTTI i dati ancora mancanti dal piano.

Esegue ogni entry del piano che non è già coperta nel lake.

Usage:
    uv run --frozen python scripts/backfill_all.py           # lento, tutto
    uv run --frozen python scripts/backfill_all.py --fast    # solo critici
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from market.ingestion.orchestrator import run_plan, write_default_plan
from market.ingestion.pipeline import Pipeline


async def main() -> int:
    fast = "--fast" in sys.argv

    if fast:
        print("⚡ Backfill veloce — solo asset critici già configurati\n")
        pipe = Pipeline()
        from datetime import date

        from market.ingestion.types import SourceId

        today = date.today()

        # Solo ciò che è DAVVERO mancante e veloce da scaricare
        missing = [
            # Futures 1h da yfinance (espande copertura ES 1h esistente)
            ("NQ", "1h", SourceId.YAHOO, date(2024, 7, 28), today),
            ("GC", "1h", SourceId.YAHOO, date(2024, 7, 28), today),
            ("CL", "1h", SourceId.YAHOO, date(2024, 7, 28), today),
            # FX daily da yfinance (backup cross-validation)
            ("GBPUSD", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
            ("USDJPY", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
            ("XAUUSD", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
            # Indici
            ("QQQ", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
            ("IWM", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
            ("DIA", "1d", SourceId.YAHOO, date(2000, 1, 1), today),
            # Crypto aggiuntivi
            ("SOLUSDT", "1h", SourceId.BINANCE_REST, date(2020, 1, 1), today),
            ("SOLUSDT", "1d", SourceId.BINANCE_REST, date(2020, 1, 1), today),
            ("BNBUSDT", "1h", SourceId.BINANCE_REST, date(2017, 11, 1), today),
            ("BNBUSDT", "1d", SourceId.BINANCE_REST, date(2017, 11, 1), today),
        ]

        success = 0
        failed = 0
        for sym, tf, source, start, end in missing:
            print(f"  [{sym} {tf} via {source.value}] ", end="", flush=True)
            report = pipe.fetch(sym, tf, source, start=start, end=end)
            if report.note.startswith("FAILED"):
                print(f"❌ {report.note}")
                failed += 1
            else:
                print(
                    f"✅ {report.rows_in} in → {report.rows_out} out "
                    f"({report.rows_rejected} rej) in {report.duration_s:.1f}s"
                )
                success += 1

        print(f"\nDone: {success} ok, {failed} fail")
    else:
        print("🐢 Backfill completo — tutto il piano\n")
        write_default_plan()
        rc = run_plan(max_runtime_s=3600, pause_between_s=2.0)
        print(f"\nDone: exit code {rc}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
