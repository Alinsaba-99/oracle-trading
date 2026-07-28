"""BL-301 — Metadata writer + lineage tracking.

These small JSON files at ``data/lake/metadata/`` are the operational
source of truth for the data lake. They are written by the pipeline
during MERGE and read on the next DISCOVERY to compute gaps.

Files:
  coverage.json    — per (symbol, tf) the available continuous range
                     and which sources contributed to it
  lineage.json     — each (symbol, tf, partition_file) ->
                     list of raw sources that fed into it
  symbols.json     — the AssetSpec registry (manually maintained or
                     auto-discovered from first fetch)
  ingestion_state.json — orchestrator resume point
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("oracle.market.ingestion.metadata")


META_DIR = Path("data/lake/metadata")


def _read(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        logger.warning("corrupt metadata file: %s; using default", path)
        return default


def _atomic_write(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str, sort_keys=True))
    tmp.replace(path)


def load_symbols() -> dict[str, dict[str, Any]]:
    return _read(META_DIR / "symbols.json", {})


def save_symbols(symbols: dict[str, dict[str, Any]]) -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(META_DIR / "symbols.json", symbols)


def load_coverage() -> dict[str, dict[str, Any]]:
    """Coverage index. Key is "{SYMBOL}|{TF}".

    Each value is
      {"earliest": ISO date,
       "latest": ISO date or None,
       "rows": int,
       "sources": [source_name, ...],
       "version": int,
       "last_touch": ISO datetime}
    """
    return _read(META_DIR / "coverage.json", {})


def save_coverage(coverage: dict[str, dict[str, Any]]) -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(META_DIR / "coverage.json", coverage)


def load_lineage() -> dict[str, list[str]]:
    return _read(META_DIR / "lineage.json", {})


def save_lineage(lineage: dict[str, list[str]]) -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(META_DIR / "lineage.json", lineage)


def load_state() -> dict[str, Any]:
    return _read(META_DIR / "ingestion_state.json", {})


def save_state(state: dict[str, Any]) -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(META_DIR / "ingestion_state.json", state)


def coverage_key(symbol: str, timeframe: str) -> str:
    return f"{symbol}|{timeframe}"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_audit_log(
    *,
    source: str,
    symbol: str,
    timeframe: str,
    start: date,
    end: date,
    rows_in: int,
    rows_out: int,
    rows_rejected: int,
    file_sha: str | None = None,
    note: str = "",
) -> None:
    log_dir = Path("data/lake/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / "ingestion_audit.jsonl"
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "source": source,
        "symbol": symbol,
        "timeframe": timeframe,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_rejected": rows_rejected,
        "file_sha256": file_sha,
        "note": note,
    }
    with log.open("a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")
