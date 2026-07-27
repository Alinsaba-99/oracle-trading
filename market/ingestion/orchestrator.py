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
from datetime import UTC, date, datetime
from pathlib import Path

from market.ingestion import metadata_io as meta
from market.ingestion.pipeline import FetchReport, Pipeline
from market.ingestion.types import SourceId

logger = logging.getLogger("oracle.market.ingestion.orchestrator")

PLAN_PATH = Path("data/lake/plans/backfill.conf")


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
        "# Available sources: binance_rest, cryptodata, histdata, stooq, databento, dukascopy\n"
        "BTCUSDT|1d|cryptodata|2014-01-01\n"
        "BTCUSDT|1m|binance_rest|2017-08-17\n"
        "BTCUSDT|1h|binance_rest|2017-08-17\n"
        "ETHUSDT|1m|binance_rest|2017-08-17\n"
        "EURUSD|1m|dukascopy|2003-05-04\n"
        "EURUSD|1h|dukascopy|2003-05-04\n"
        "ES|1d|stooq|1990-01-01\n"
    )


def run_plan(
    entries: list[BackfillEntry] | None = None,
    *,
    max_runtime_s: float | None = None,
    pause_between_s: float = 0.0,
) -> int:
    """Run the backfill plan in series. Resumable across restarts.

    Args:
        entries: explicit list; default reads the YAML plan.
        max_runtime_s: if set, the loop exits cleanly after this many
            seconds. Use for laptop-aware batching.
        pause_between_s: delay between entries (gives the source rate
            limit a moment to recover).
    """
    write_default_plan()
    entries = entries or _load_plan_yaml()
    state = meta.load_state()
    pipeline = Pipeline()
    completed: set[str] = set(state.get("completed", []))
    failed: dict[str, str] = dict(state.get("failed", {}))
    started_at = state.get("started_at", datetime.now(UTC).isoformat())
    runtime_start = time.monotonic()
    logger.info(
        "orchestrator: %d entries, done=%d, failed=%d", len(entries), len(completed), len(failed)
    )
    t0 = time.monotonic()
    for entry in entries:
        key = _state_key(entry)
        if key in completed:
            logger.info("skip (done): %s", key)
            continue
        if max_runtime_s is not None and (time.monotonic() - runtime_start) > max_runtime_s:
            pending = sum(1 for e in entries if _state_key(e) not in completed)
            logger.info(
                "max-runtime %.0fs reached; pending %d entries for next run", max_runtime_s, pending
            )
            break
        last_attempt = datetime.now(UTC)
        try:
            report: FetchReport = pipeline.fetch(
                entry.symbol,
                entry.timeframe,
                SourceId(entry.source),
                start=entry.start,
                end=entry.end,
            )
        except Exception as exc:
            logger.exception("entry raised: %s - %s", key, exc)
            failed[key] = f"{type(exc).__name__}: {exc}"
            meta.save_state(
                {
                    "started_at": started_at,
                    "completed": sorted(completed),
                    "failed": failed,
                    "last_error": f"{key} :: {failed[key]}",
                    "last_attempt": last_attempt.isoformat(),
                }
            )
            continue
        if report.note.startswith("FAILED"):
            logger.error("entry FAILED: %s (%s)", key, report.note)
            failed[key] = report.note
            meta.save_state(
                {
                    "started_at": started_at,
                    "completed": sorted(completed),
                    "failed": failed,
                    "last_error": f"{key} :: {report.note}",
                    "last_attempt": last_attempt.isoformat(),
                }
            )
            continue
        completed.add(key)
        failed.pop(key, None)
        meta.save_state(
            {
                "started_at": started_at,
                "completed": sorted(completed),
                "failed": failed,
                "last_attempt": last_attempt.isoformat(),
                "last_entry_summary": {
                    "key": key,
                    "rows_in": report.rows_in,
                    "rows_out": report.rows_out,
                    "rows_rejected": report.rows_rejected,
                    "duration_s": report.duration_s,
                },
            }
        )
        logger.info(
            "completed %s/%s [%s %s %s]: in=%d out=%d rej=%d %.1fs",
            len(completed),
            len(entries),
            entry.source,
            entry.symbol,
            entry.timeframe,
            report.rows_in,
            report.rows_out,
            report.rows_rejected,
            report.duration_s,
        )
        if pause_between_s > 0:
            time.sleep(pause_between_s)
    duration = round(time.monotonic() - t0, 2)
    summary = {
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "entries_total": len(entries),
        "entries_completed": len(completed),
        "entries_failed": len(failed),
        "duration_s": duration,
        "max_runtime_s": max_runtime_s,
    }
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    (log_dir / "orchestrator_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (Path("data/lake/metadata") / "orchestrator_summary.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )
    logger.info(
        "orchestrator: completed=%d failed=%d duration=%.1fs", len(completed), len(failed), duration
    )
    return 0 if not failed else 1


def status() -> dict:
    """Return current state of the orchestrator: completed, failed, last error."""
    s = meta.load_state()
    return {
        "started_at": s.get("started_at"),
        "completed": s.get("completed", []),
        "failed": s.get("failed", {}),
        "last_attempt": s.get("last_attempt"),
        "last_entry_summary": s.get("last_entry_summary", {}),
        "last_error": s.get("last_error"),
    }
