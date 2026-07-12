"""Read trade data from experiments.db."""
from __future__ import annotations

import json
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

def list_trades(
    limit: int = 20,
    offset: int = 0,
    asset: str | None = None,  # noqa: ARG001
    side: str | None = None,  # noqa: ARG001
    from_date: str | None = None,  # noqa: ARG001
    to_date: str | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """List trades from experiments.db.

    The experiments table stores JSON blobs with fold-level metrics.
    Individual trades are not yet persisted — this returns experimental
    folds as pseudo-trades.

    Args (future use — filtering not yet implemented):
        limit: max results.
        offset: pagination offset.
        asset: filter by asset (unused).
        side: filter by side (unused).
        from_date: start date filter (unused).
        to_date: end date filter (unused).
    """
    conn = _get_conn()
    if conn is None:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    try:
        cursor = conn.cursor()

        # Count
        cursor.execute("SELECT COUNT(*) FROM experiments")
        total = cursor.fetchone()[0]

        # Query rows
        cursor.execute(
            "SELECT id, parent_id, data, created_at"
            " FROM experiments ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

        items = []
        for row in cursor:
            try:
                data = json.loads(row["data"])
            except (json.JSONDecodeError, TypeError):
                data = {}

            tags = data.get("tags", {})

            items.append({
                "time": row["created_at"][:19] if row["created_at"] else "",
                "experiment_id": data.get("experiment_id", "")[:8],
                "fold": tags.get("fold", "?"),
                "engine": tags.get("engine", "?"),
                "total_return": float(tags.get("total_return", 0)),
                "sharpe_ratio": float(tags.get("sharpe_ratio", 0)),
            })

        conn.close()
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except sqlite3.Error:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}
