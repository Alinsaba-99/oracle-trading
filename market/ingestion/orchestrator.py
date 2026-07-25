"""BL-301 — Multi-source backfill orchestrator.

Reads a YAML plan (``data/lake/plans/backfill.yaml``) listing
``(symbol, tf, source, start, end)`` targets and runs them in series.
Idempotent: resume from ``ingestion_state.json`` if interrupted.
Records per-line audit in ``logs/ingestion_audit.jsonl``.

Usage:

  python -m market.ingestion.orchestrator run
  python -m market.ingestion.orchestrator status
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timezone

UTC = UTC, timezone
UTC = timezone.utc
from pathlib import Path

from market.ingestion import metadata_io as meta
from market.ingestion.pipeline import FetchReport, Pipeline
from market.ingestion.types import SourceId

logger = logging.getLogger("oracle.market.ingestion.orchestrator")

PLAN_PATH = Path("data/lake/plans/backfill.yaml")


@dataclass
class BackfillEntry:
    symbol: str
    timeframe: str
    source: str
    start: date
    end: date | None = None


def _state_key(entry: BackfillEntry) -> str:
    end = entry.end or date.today()
    return f"{entry.symbol}|{entry.timeframe}|{entry.source}|{end.isoformat()}"


def _load_plan_yaml() -> list[BackfillEntry]:
    """Tiny YAML-less loader: we accept line-by-line entries to avoid a
    PyYAML dependency on the data lake hot path."""
    if not PLAN_PATH.exists():
        return []
    entries: list[BackfillEntry] = []
    for raw in PLAN_PATH.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            logger.warning("skip malformed line: %s", line)
            continue
        sym, tf, src, start = parts[:4]
        end = parts[4] if len(parts) > 4 else None
        try:
            entries.append(
                BackfillEntry(
                    symbol=sym,
                    timeframe=tf,
                    source=src,
                    start=date.fromisoformat(start),
                    end=date.fromisoformat(end) if end else None,
                )
            )
        except ValueError as exc:
            logger.warning("skip unparseable: %s (%s)", line, exc)
    return entries


def write_default_plan() -> None:
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PLAN_PATH.exists():
        return
    PLAN_PATH.write_text(
        "# BL-301 default plan — repo-pinned sources only (no API key)\n"
        "# Format: SYMBOL|TIMEFRAME|SOURCE|START_DATE|END_DATE(optional)\n"
        "# Available sources: binance_rest, cryptodata, histdata, stooq, databento\n"
        "BTCUSDT|1d|cryptodata|2014-01-01\n"
        "BTCUSDT|1m|binance_rest|2017-08-17\n"
        "BTCUSDT|1h|binance_rest|2017-08-17\n"
        "ETHUSDT|1m|binance_rest|2017-08-17\n"
        "EURUSD|1m|histdata|2000-01-01\n"
        "ES|1d|stooq|1990-01-01\n"
    )


def run_plan(entries: list[BackfillEntry] | None = None) -> int:
    write_default_plan()
    entries = entries or _load_plan_yaml()
    state = meta.load_state()
    pipeline = Pipeline()
    completed: set[str] = set(state.get("completed", []))
    started_at = datetime.now(UTC).isoformat()
    logger.info("orchestrator: starting %d entries at %s", len(entries), started_at)
    t0 = time.monotonic()
    for entry in entries:
        key = _state_key(entry)
        if key in completed:
            logger.info("skip (already done): %s", key)
            continue
        try:
            report: FetchReport = pipeline.fetch(
                entry.symbol,
                entry.timeframe,
                SourceId(entry.source),
                start=entry.start,
                end=entry.end,
            )
        except Exception as exc:
            logger.exception("entry failed: %s — %s", key, exc)
            continue
        if report.note.startswith("FAILED"):
            logger.error("entry FAILED: %s", key)
            completed.add(key)
            meta.save_state({"started_at": started_at, "completed": sorted(completed), "last_error": report.note})
            return 1
        completed.add(key)
        meta.save_state({"started_at": started_at, "completed": sorted(completed)})
        logger.info(
            "completed %s/%s: in=%d out=%d rej=%d",
            len(completed),
            len(entries),
            report.rows_in,
            report.rows_out,
            report.rows_rejected,
        )
    duration = round(time.monotonic() - t0, 2)
    summary = {
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "entries_total": len(entries),
        "entries_completed": len(completed),
        "duration_s": duration,
    }
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    (log_dir / "orchestrator_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    logger.info("orchestrator done: %s", summary)
    return 0
