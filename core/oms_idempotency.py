"""Durable idempotency store for OMS — survives process restarts.

The ``InMemoryOMS`` keeps its idempotency map (client_order_id →
order_id) in a Python dict.  That dict is lost across CLI invocations
or service restarts, which means the same client_order_id can be
submitted twice with two different order_ids, reaching the broker and
producing duplicate fills.

This module provides a durable plug-in for that map.  The minimal
implementation uses SQLite (file-backed, no server required).  A
PostgreSQL implementation is straightforward and intentionally omitted
here to avoid duplicating the surface area of ``core/oms_postgres``.

Usage::

    from core.oms import InMemoryOMS
    from core.oms_idempotency import SQLiteIdempotencyStore

    store = SQLiteIdempotencyStore("/path/to/idempotency.db")
    oms = InMemoryOMS(idempotency_store=store)
"""

from __future__ import annotations

import sqlite3
from typing import Protocol


class IdempotencyStore(Protocol):
    """Minimal contract for a durable idempotency store."""

    def get(self, client_order_id: str) -> str | None:
        """Return the stored ``order_id`` for the given ``client_order_id``,
        or ``None`` if the key has never been recorded."""

    def put(self, client_order_id: str, order_id: str) -> None:
        """Record the ``(client_order_id, order_id)`` mapping durably."""

    def close(self) -> None:
        """Release any underlying resources (optional)."""


class InMemoryIdempotencyStore:
    """Reference implementation: a plain dict.  Loses state on restart."""

    def __init__(self) -> None:
        self._mapping: dict[str, str] = {}

    def get(self, client_order_id: str) -> str | None:
        return self._mapping.get(client_order_id)

    def put(self, client_order_id: str, order_id: str) -> None:
        self._mapping[client_order_id] = order_id

    def close(self) -> None:
        pass


class SQLiteIdempotencyStore:
    """SQLite-backed idempotency store, safe across process restarts.

    Thread-safety: SQLite connections are used with ``check_same_thread=False``
    so the store can be shared across CLI invocations.  Writes are
    serialized via a simple lock to avoid "database is locked" errors
    under contention.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency (
                client_order_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def get(self, client_order_id: str) -> str | None:
        cur = self._conn.execute(
            "SELECT order_id FROM idempotency WHERE client_order_id = ?", (client_order_id,)
        )
        row = cur.fetchone()
        return row[0] if row else None

    def put(self, client_order_id: str, order_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO idempotency (client_order_id, order_id) VALUES (?, ?)",
            (client_order_id, order_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
