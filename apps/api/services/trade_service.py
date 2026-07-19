"""Read trade data from experiments.db with filtering."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

_DB_PATH = Path(__file__).resolve().parents[3] / "experiments" / "experiments.db"


def _get_conn() -> sqlite3.Connection | None:
    if not _DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def _safe_float(val: str | float | int | None, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        v = float(val)
        if math.isinf(v) or math.isnan(v):
            return default
        return v
    except (ValueError, TypeError):
        return default


def _build_where(
    engine: str | None, fold: str | None, from_date: str | None, to_date: str | None
) -> tuple[str, list[str | int]]:
    """Build WHERE clause and params from filters.

    Engine/fold live inside the JSON ``data`` column as ``tags.engine``
    and ``tags.fold`` — use json_extract at the SQL level so filtering
    happens in the database, not in Python.
    """
    clauses: list[str] = []
    params: list[str | int] = []

    if engine:
        clauses.append("json_extract(data, '$.tags.engine') = ?")
        params.append(engine)

    if fold is not None:
        clauses.append("json_extract(data, '$.tags.fold') = ?")
        params.append(str(fold))

    if from_date:
        clauses.append("created_at >= ?")
        params.append(from_date)

    if to_date:
        # Include the whole ``to_date`` day
        clauses.append("created_at <= ?")
        params.append(f"{to_date}T23:59:59")

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    return where, params


def list_trades(
    limit: int = 20,
    offset: int = 0,
    engine: str | None = None,
    fold: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    """List trade-like records from experiments.db with optional filters.

    Each row in the experiments table represents a fold-level backtest
    result stored as a JSON blob.  ``engine`` and ``fold`` are extracted
    from ``tags`` inside the blob via ``json_extract`` at the SQL level.
    """
    conn = _get_conn()
    if conn is None:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    try:
        cursor = conn.cursor()
        where, params = _build_where(engine, fold, from_date, to_date)

        # Count
        cursor.execute(f"SELECT COUNT(*) FROM experiments {where}", params)
        total = cursor.fetchone()[0]

        # Query rows
        cursor.execute(
            f"SELECT id, parent_id, data, created_at"
            f" FROM experiments {where}"
            f" ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )

        items = []
        for row in cursor:
            try:
                data = json.loads(row["data"])
            except (json.JSONDecodeError, TypeError):
                data = {}

            tags = data.get("tags", {})

            items.append(
                {
                    "time": row["created_at"][:19] if row["created_at"] else "",
                    "experiment_id": data.get("experiment_id", "")[:8],
                    "fold": tags.get("fold", "?"),
                    "engine": tags.get("engine", "?"),
                    "total_return": _safe_float(tags.get("total_return")),
                    "sharpe_ratio": _safe_float(tags.get("sharpe_ratio")),
                }
            )

        conn.close()
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except sqlite3.Error:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}
