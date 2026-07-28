"""R4 experiment store — SQLite-backed results from LLM + GA search."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from analytics.strategy.fitness import EvalMode, FitnessReport
from analytics.strategy.spec import StrategySpec

log = logging.getLogger("oracle.strategy.experiments_store")

DB_PATH = Path("experiments/r4_search.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS specs (
    id TEXT PRIMARY KEY,
    spec_name TEXT NOT NULL DEFAULT '',
    spec_json TEXT NOT NULL,
    source TEXT NOT NULL,
    mode TEXT NOT NULL,
    fitness REAL NOT NULL,
    pass_rate REAL DEFAULT 0,
    sharpe REAL DEFAULT 0,
    total_return REAL DEFAULT 0,
    max_drawdown REAL DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    wf_median_fitness REAL,
    wf_min_fitness REAL,
    wf_fold_std REAL,
    wf_oos_sharpe REAL,
    wf_oos_max_drawdown REAL,
    wf_sharpe_stability REAL,
    wf_pass_rate_consistency REAL,
    n_folds INTEGER,
    instrument TEXT,
    entry TEXT,
    timeframe TEXT,
    regime TEXT,
    is_multi_tf INTEGER DEFAULT 0,
    filter_tf TEXT,
    created_at REAL NOT NULL,
    rationale TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS wf_folds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_id TEXT NOT NULL REFERENCES specs(id),
    fold_idx INTEGER NOT NULL,
    fitness REAL NOT NULL,
    pass_rate REAL DEFAULT 0,
    sharpe REAL DEFAULT 0,
    total_return REAL DEFAULT 0,
    max_drawdown REAL DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    UNIQUE(spec_id, fold_idx)
);

CREATE INDEX IF NOT EXISTS idx_specs_fitness ON specs(fitness DESC);
CREATE INDEX IF NOT EXISTS idx_specs_mode ON specs(mode);
CREATE INDEX IF NOT EXISTS idx_specs_source ON specs(source);
CREATE INDEX IF NOT EXISTS idx_specs_instrument ON specs(instrument);
CREATE INDEX IF NOT EXISTS idx_wf_folds_spec ON wf_folds(spec_id);
"""


def _get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def _spec_id(spec: StrategySpec, mode: str) -> str:
    raw = spec.model_dump_json() + mode
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def save_spec_result(
    spec: StrategySpec, report: FitnessReport, source: str, *, db_path: Path = DB_PATH
) -> str:
    """Save a single spec evaluation result. Returns the spec ID."""
    spec_id = _spec_id(spec, str(report.mode))
    spec_json = spec.model_dump_json()
    mode = str(report.mode)

    # For FIRM mode pass_rate comes from mc_pass_rate; FREE has no MC
    pass_rate = report.mc_pass_rate if report.mode == EvalMode.FIRM else 0.0

    conn = _get_conn(db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO specs (
                id, spec_name, spec_json, source, mode,
                fitness, pass_rate, sharpe, total_return, max_drawdown, total_trades,
                instrument, entry, timeframe, regime,
                is_multi_tf, filter_tf,
                created_at, rationale
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?
            )
            """,
            (
                spec_id,
                spec.name,
                spec_json,
                source,
                mode,
                report.fitness,
                pass_rate,
                report.sharpe,
                report.total_return,
                report.max_drawdown,
                report.total_trades,
                spec.instrument,
                spec.entry,
                spec.timeframe,
                spec.regime,
                int(spec.is_multi_tf),
                spec.filter_tf,
                time.time(),
                spec.rationale,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    log.debug("saved spec %s source=%s mode=%s fitness=%.4f", spec_id, source, mode, report.fitness)
    return spec_id


def save_wf_result(
    spec_id: str,
    fold_reports: list[FitnessReport],
    wf_combined: dict[str, float],
    *,
    db_path: Path = DB_PATH,
) -> None:
    """Attach walk-forward results to an existing spec."""
    conn = _get_conn(db_path)
    try:
        conn.execute(
            """
            UPDATE specs SET
                wf_median_fitness = ?,
                wf_min_fitness = ?,
                wf_fold_std = ?,
                wf_oos_sharpe = ?,
                wf_oos_max_drawdown = ?,
                wf_sharpe_stability = ?,
                wf_pass_rate_consistency = ?,
                n_folds = ?
            WHERE id = ?
            """,
            (
                wf_combined.get("median_fitness"),
                wf_combined.get("min_fitness"),
                wf_combined.get("fold_std"),
                wf_combined.get("oos_sharpe"),
                wf_combined.get("oos_max_drawdown"),
                wf_combined.get("sharpe_stability"),
                wf_combined.get("pass_rate_consistency"),
                len(fold_reports),
                spec_id,
            ),
        )
        for idx, fr in enumerate(fold_reports):
            pass_rate = fr.mc_pass_rate if fr.mode == EvalMode.FIRM else 0.0
            conn.execute(
                """
                INSERT OR REPLACE INTO wf_folds (
                    spec_id, fold_idx, fitness, pass_rate, sharpe,
                    total_return, max_drawdown, total_trades
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    spec_id,
                    idx,
                    fr.fitness,
                    pass_rate,
                    fr.sharpe,
                    fr.total_return,
                    fr.max_drawdown,
                    fr.total_trades,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    log.debug("saved wf results for spec %s n_folds=%d", spec_id, len(fold_reports))


def top_specs(
    mode: str | None = None,
    source: str | None = None,
    limit: int = 20,
    min_fitness: float = 0.0,
    *,
    db_path: Path = DB_PATH,
) -> list[dict[str, Any]]:
    """Query top specs by fitness, optionally filtered by mode/source."""
    conditions = ["fitness >= ?"]
    params: list[Any] = [min_fitness]
    if mode is not None:
        conditions.append("mode = ?")
        params.append(mode)
    if source is not None:
        conditions.append("source = ?")
        params.append(source)

    where = " AND ".join(conditions)
    query = f"SELECT * FROM specs WHERE {where} ORDER BY fitness DESC LIMIT ?"
    params.append(limit)

    conn = _get_conn(db_path)
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    return [_row_to_dict(r) for r in rows]


def get_spec(spec_id: str, *, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    """Get one spec by ID with its WF folds."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM specs WHERE id = ?", (spec_id,)).fetchone()
        if row is None:
            return None
        result = _row_to_dict(row)
        folds = conn.execute(
            "SELECT * FROM wf_folds WHERE spec_id = ? ORDER BY fold_idx", (spec_id,)
        ).fetchall()
        result["wf_folds"] = [dict(f) for f in folds]
    finally:
        conn.close()

    return result


def all_specs(mode: str | None = None, *, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    """All specs for a given mode."""
    if mode is not None:
        query = "SELECT * FROM specs WHERE mode = ? ORDER BY fitness DESC"
        params: tuple[Any, ...] = (mode,)
    else:
        query = "SELECT * FROM specs ORDER BY fitness DESC"
        params = ()

    conn = _get_conn(db_path)
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    raw = d.get("spec_json")
    if raw:
        try:
            d["spec"] = json.loads(raw)
        except json.JSONDecodeError:
            d["spec"] = {}
    return d
