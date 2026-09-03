"""BL-729 — Durable execution store (G3: paper trading end-to-end).

SQLite-backed store for the always-on paper trading runner. Records:

- ``orders`` — every submitted order (id, broker_order_id, instrument, qty,
  price fields, status, strategy, meta).
- ``fills`` — every broker-reported fill; ``fill_id`` is the idempotency
  key (re-ingestion is a no-op).
- ``positions`` — current net position per instrument (avg price + qty +
  realised P&L).
- ``equity_snapshots`` — one row per cycle (cash + positions_value + equity).
- ``audit_log`` — heartbeats, cycle boundaries, shutdowns, fatal errors.

Design goals (BL-729 brief):

1. **Crash-safe.** WAL journal mode (``PRAGMA journal_mode=WAL``) plus
   ``synchronous=NORMAL`` lets readers run concurrently with a single
   writer and survive process kills (last committed transaction is durable;
   uncommitted changes replay safely). All writes happen inside an
   explicit ``BEGIN/COMMIT`` block.
2. **Idempotent fill ingestion.** ``append_fill`` uses
   ``INSERT OR IGNORE`` keyed on ``fill_id`` — re-ingesting the same fill
   is a silent no-op (returns ``False``).
3. **Money = ``Decimal``.** All monetary fields are persisted as TEXT and
   parsed back with :class:`decimal.Decimal`. SQLite has no native
   numeric type; storing as ``REAL`` would lose precision silently.
4. **Migration path from the JSON SlippageLedger.** :func:`import_ledger`
   reads an existing ``*.jsonl`` file produced by the legacy
   ``SlippageLedger`` and folds its rows into ``fills`` (idempotency key
   derived from the original ``timestamp`` + ``broker_order_id`` when
   the fill_id is missing).
5. **Typed, narrow API.** :class:`ExecutionStore` exposes only the
   methods the runner / replay / dashboard need (``append_order``,
   ``append_fill``, ``upsert_position``, ``snapshot_equity``,
   ``heartbeat``, ``query_*``). All Decimal values are accepted and
   returned as Decimal — never as float.

Thread-safety
-------------
A single :class:`threading.RLock` guards all writes (SQLite's own lock
provides serialisation; the RLock keeps the in-process state consistent
when ``append_order`` + ``append_fill`` are called sequentially from a
single runner thread). The store is safe to share across threads as
long as every write goes through the public API.

The store deliberately avoids a dependency on ``aiosqlite`` so it can
be opened by ``mypy --strict`` sync paths (the runner wraps it in
``asyncio.to_thread`` when needed — see :mod:`execution.runner`).
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

# =========================================================================
# Schema
# =========================================================================

SCHEMA_VERSION = 1

#: Money columns are stored as TEXT to preserve Decimal precision. Times
#: are ISO-8601 UTC strings; the runner sorts by them lexicographically,
#: which is correct for ISO-8601 with fixed-width fields.
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id           TEXT PRIMARY KEY,
    broker_order_id    TEXT,
    instrument_id      TEXT NOT NULL,
    side               TEXT NOT NULL,
    quantity           TEXT NOT NULL,
    order_type         TEXT NOT NULL,
    status             TEXT NOT NULL,
    price              TEXT,
    stop_price         TEXT,
    take_profit_price  TEXT,
    strategy           TEXT NOT NULL DEFAULT '',
    meta_json          TEXT NOT NULL DEFAULT '{}',
    submitted_at       TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_broker ON orders(broker_order_id);
CREATE INDEX IF NOT EXISTS idx_orders_instrument ON orders(instrument_id);
CREATE INDEX IF NOT EXISTS idx_orders_submitted ON orders(submitted_at);

CREATE TABLE IF NOT EXISTS fills (
    fill_id          TEXT PRIMARY KEY,
    order_id         TEXT NOT NULL,
    broker_order_id  TEXT NOT NULL,
    instrument_id    TEXT NOT NULL,
    side             TEXT NOT NULL,
    quantity         TEXT NOT NULL,
    price            TEXT NOT NULL,
    commission       TEXT NOT NULL DEFAULT '0',
    slippage_bps     INTEGER NOT NULL DEFAULT 0,
    backtest_price   TEXT,
    strategy         TEXT NOT NULL DEFAULT '',
    meta_json        TEXT NOT NULL DEFAULT '{}',
    filled_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fills_order ON fills(order_id);
CREATE INDEX IF NOT EXISTS idx_fills_instrument ON fills(instrument_id);
CREATE INDEX IF NOT EXISTS idx_fills_filled_at ON fills(filled_at);

CREATE TABLE IF NOT EXISTS positions (
    instrument_id  TEXT PRIMARY KEY,
    quantity       TEXT NOT NULL,
    avg_price      TEXT NOT NULL,
    realized_pnl   TEXT NOT NULL DEFAULT '0',
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts              TEXT PRIMARY KEY,
    cash            TEXT NOT NULL,
    positions_value TEXT NOT NULL,
    equity          TEXT NOT NULL,
    daily_pnl       TEXT NOT NULL DEFAULT '0',
    cycle_index     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_equity_ts ON equity_snapshots(ts);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    kind        TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_kind_ts ON audit_log(kind, ts);
"""


# =========================================================================
# Public dataclasses
# =========================================================================


@dataclass(frozen=True)
class OrderRecord:
    """One submitted order — what we persist on the orders table.

    All Decimal money fields are non-None (``Decimal("0")``) except the
    price-like optional fields (``price``, ``stop_price``,
    ``take_profit_price``) which are ``None`` for market orders.
    """

    order_id: str
    broker_order_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    order_type: str
    status: str
    price: Decimal | None
    stop_price: Decimal | None
    take_profit_price: Decimal | None
    strategy: str
    meta: dict[str, Any]
    submitted_at: str
    updated_at: str


@dataclass(frozen=True)
class FillRecord:
    """One broker-reported fill — idempotency key is ``fill_id``."""

    fill_id: str
    order_id: str
    broker_order_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    price: Decimal
    commission: Decimal
    slippage_bps: int
    backtest_price: Decimal | None
    strategy: str
    meta: dict[str, Any]
    filled_at: str


@dataclass(frozen=True)
class PositionRecord:
    """Current net position per instrument — refreshed on every fill."""

    instrument_id: str
    quantity: Decimal
    avg_price: Decimal
    realized_pnl: Decimal
    updated_at: str


@dataclass(frozen=True)
class EquitySnapshot:
    """One equity-curve point."""

    ts: str
    cash: Decimal
    positions_value: Decimal
    equity: Decimal
    daily_pnl: Decimal
    cycle_index: int


@dataclass(frozen=True)
class AuditEvent:
    """One row of the audit log (heartbeats, shutdown, fatal errors)."""

    id: int
    ts: str
    kind: str
    payload: dict[str, Any]


# =========================================================================
# Helpers
# =========================================================================


def _to_decimal(value: Any) -> Decimal:
    """Coerce a value to Decimal; never raise on None — return ``Decimal("0")``."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _now_iso() -> str:
    """ISO-8601 UTC timestamp with microsecond precision."""
    return datetime.now(UTC).isoformat()


# =========================================================================
# ExecutionStore
# =========================================================================


class ExecutionStore:
    """Synchronous SQLite store for the paper trading runner.

    The store is intentionally synchronous — the runner wraps calls in
    ``asyncio.to_thread`` so a long-running tick never blocks the event
    loop.  Keeping the surface sync also makes ``mypy --strict`` happy
    without contortions around aiosqlite.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # ``check_same_thread=False`` so the runner thread can hold the
        # connection across calls. The RLock below serialises writes.
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)
        # Persist the schema version on first init.
        self._conn.execute(
            "INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, ?)",
            ("version", str(SCHEMA_VERSION)),
        )
        self._conn.commit()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Close the underlying connection. Idempotent."""
        with self._lock, contextlib.suppress(sqlite3.ProgrammingError):
            self._conn.close()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Acquire the write lock and run a single transaction.

        Rolls back on any exception, commits on success. Used by every
        write method so a partial write can never leak rows.
        """
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------
    def append_order(self, record: OrderRecord) -> bool:
        """Insert an order row. Idempotent on ``order_id``.

        Returns ``True`` if a new row was inserted, ``False`` if the
        order_id was already present (e.g. a retry of the same intent).
        """
        with self._tx() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO orders (
                    order_id, broker_order_id, instrument_id, side, quantity,
                    order_type, status, price, stop_price, take_profit_price,
                    strategy, meta_json, submitted_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.order_id,
                    record.broker_order_id,
                    record.instrument_id,
                    record.side,
                    str(record.quantity),
                    record.order_type,
                    record.status,
                    str(record.price) if record.price is not None else None,
                    str(record.stop_price) if record.stop_price is not None else None,
                    (
                        str(record.take_profit_price)
                        if record.take_profit_price is not None
                        else None
                    ),
                    record.strategy,
                    json.dumps(record.meta, default=str, sort_keys=True),
                    record.submitted_at,
                    record.updated_at,
                ),
            )
            return cur.rowcount > 0

    def update_order_status(
        self,
        order_id: str,
        *,
        broker_order_id: str | None = None,
        status: str | None = None,
        updated_at: str | None = None,
    ) -> bool:
        """Update an existing order's broker id and/or status.

        Returns ``True`` if a row was updated.
        """
        sets: list[str] = []
        params: list[Any] = []
        if broker_order_id is not None:
            sets.append("broker_order_id = ?")
            params.append(broker_order_id)
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        sets.append("updated_at = ?")
        params.append(updated_at or _now_iso())
        params.append(order_id)
        with self._tx() as conn:
            cur = conn.execute(f"UPDATE orders SET {', '.join(sets)} WHERE order_id = ?", params)
            return cur.rowcount > 0

    def get_order(self, order_id: str) -> OrderRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM orders WHERE order_id = ?", (order_id,)
            ).fetchone()
        return _row_to_order(row) if row else None

    def list_orders(
        self, *, instrument_id: str | None = None, since: str | None = None, limit: int = 1000
    ) -> list[OrderRecord]:
        """Return orders, newest first. ``since`` is an ISO-8601 lower bound."""
        clauses: list[str] = []
        params: list[Any] = []
        if instrument_id is not None:
            clauses.append("instrument_id = ?")
            params.append(instrument_id)
        if since is not None:
            clauses.append("submitted_at >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM orders {where} ORDER BY submitted_at DESC LIMIT ?", params
            ).fetchall()
        return [_row_to_order(r) for r in rows]

    # ------------------------------------------------------------------
    # Fills — idempotent ingestion
    # ------------------------------------------------------------------
    def append_fill(self, record: FillRecord) -> bool:
        """Insert a fill row, idempotent on ``fill_id``.

        Returns ``True`` if a NEW row was inserted; ``False`` if the
        fill_id was already present (replay / crash recovery).
        """
        with self._tx() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO fills (
                    fill_id, order_id, broker_order_id, instrument_id, side,
                    quantity, price, commission, slippage_bps, backtest_price,
                    strategy, meta_json, filled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.fill_id,
                    record.order_id,
                    record.broker_order_id,
                    record.instrument_id,
                    record.side,
                    str(record.quantity),
                    str(record.price),
                    str(record.commission),
                    int(record.slippage_bps),
                    (str(record.backtest_price) if record.backtest_price is not None else None),
                    record.strategy,
                    json.dumps(record.meta, default=str, sort_keys=True),
                    record.filled_at,
                ),
            )
            return cur.rowcount > 0

    def get_fill(self, fill_id: str) -> FillRecord | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM fills WHERE fill_id = ?", (fill_id,)).fetchone()
        return _row_to_fill(row) if row else None

    def list_fills(
        self,
        *,
        instrument_id: str | None = None,
        order_id: str | None = None,
        since: str | None = None,
        limit: int = 1000,
    ) -> list[FillRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if instrument_id is not None:
            clauses.append("instrument_id = ?")
            params.append(instrument_id)
        if order_id is not None:
            clauses.append("order_id = ?")
            params.append(order_id)
        if since is not None:
            clauses.append("filled_at >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM fills {where} ORDER BY filled_at DESC LIMIT ?", params
            ).fetchall()
        return [_row_to_fill(r) for r in rows]

    def count_fills(self, *, instrument_id: str | None = None) -> int:
        with self._lock:
            if instrument_id is None:
                row = self._conn.execute("SELECT COUNT(*) AS n FROM fills").fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM fills WHERE instrument_id = ?", (instrument_id,)
                ).fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------
    def upsert_position(self, record: PositionRecord) -> None:
        """Replace the position row for ``instrument_id``."""
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO positions (
                    instrument_id, quantity, avg_price, realized_pnl, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(instrument_id) DO UPDATE SET
                    quantity = excluded.quantity,
                    avg_price = excluded.avg_price,
                    realized_pnl = excluded.realized_pnl,
                    updated_at = excluded.updated_at
                """,
                (
                    record.instrument_id,
                    str(record.quantity),
                    str(record.avg_price),
                    str(record.realized_pnl),
                    record.updated_at,
                ),
            )

    def get_position(self, instrument_id: str) -> PositionRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM positions WHERE instrument_id = ?", (instrument_id,)
            ).fetchone()
        return _row_to_position(row) if row else None

    def list_positions(self) -> list[PositionRecord]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM positions ORDER BY instrument_id").fetchall()
        return [_row_to_position(r) for r in rows]

    # ------------------------------------------------------------------
    # Equity snapshots
    # ------------------------------------------------------------------
    def snapshot_equity(self, record: EquitySnapshot) -> bool:
        """Record one equity-curve point. Idempotent on ``ts``."""
        with self._tx() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO equity_snapshots (
                    ts, cash, positions_value, equity, daily_pnl, cycle_index
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.ts,
                    str(record.cash),
                    str(record.positions_value),
                    str(record.equity),
                    str(record.daily_pnl),
                    int(record.cycle_index),
                ),
            )
            return cur.rowcount > 0

    def equity_curve(
        self, *, since: str | None = None, limit: int = 100_000
    ) -> list[EquitySnapshot]:
        """Return equity curve points, oldest first."""
        params: list[Any] = []
        where = ""
        if since is not None:
            where = "WHERE ts >= ?"
            params.append(since)
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM equity_snapshots {where} ORDER BY ts ASC LIMIT ?", params
            ).fetchall()
        return [_row_to_equity(r) for r in rows]

    def latest_equity(self) -> EquitySnapshot | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM equity_snapshots ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return _row_to_equity(row) if row else None

    # ------------------------------------------------------------------
    # Audit log / heartbeat
    # ------------------------------------------------------------------
    def heartbeat(self, *, cycle_index: int, payload: dict[str, Any] | None = None) -> int:
        """Record one heartbeat. Returns the inserted row id."""
        return self.append_audit(
            kind="heartbeat", payload={"cycle_index": int(cycle_index), **(payload or {})}
        )

    def append_audit(self, *, kind: str, payload: dict[str, Any] | None = None) -> int:
        """Record a generic audit event. Returns the inserted row id."""
        with self._tx() as conn:
            cur = conn.execute(
                "INSERT INTO audit_log (ts, kind, payload_json) VALUES (?, ?, ?)",
                (_now_iso(), kind, json.dumps(payload or {}, default=str, sort_keys=True)),
            )
            return int(cur.lastrowid or 0)

    def latest_heartbeat(self) -> AuditEvent | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM audit_log WHERE kind = 'heartbeat' ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return _row_to_audit(row) if row else None

    def list_audit(self, *, kind: str | None = None, limit: int = 1000) -> list[AuditEvent]:
        params: list[Any] = []
        where = ""
        if kind is not None:
            where = "WHERE kind = ?"
            params.append(kind)
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ?", params
            ).fetchall()
        return [_row_to_audit(r) for r in rows]

    # ------------------------------------------------------------------
    # Migration — import legacy JSON SlippageLedger
    # ------------------------------------------------------------------
    def import_ledger(self, jsonl_path: str | Path) -> int:
        """Import fills from a legacy SlippageLedger JSONL file.

        Each JSON line must look like the SlippageRecord serialisation
        (timestamp, instrument_id, side, quantity, backtest_price,
        paper_fill_price, slippage_bps, broker_order_id, strategy, meta).
        Missing ``fill_id`` is synthesised as
        ``sha256(timestamp|broker_order_id|price|quantity)[:32]`` so a
        re-import is idempotent.

        Returns the number of NEW fills added (duplicates are skipped).
        """
        path = Path(jsonl_path)
        if not path.exists():
            return 0
        imported = 0
        with self._lock:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                filled_at = str(row.get("timestamp") or _now_iso())
                price = _to_decimal(row.get("paper_fill_price"))
                quantity = _to_decimal(row.get("quantity"))
                side = str(row.get("side") or "")
                instrument = str(row.get("instrument_id") or "")
                broker_order_id = str(row.get("broker_order_id") or "")
                fill_id = _legacy_fill_id(filled_at, broker_order_id, price, quantity)
                backtest_price_raw = row.get("backtest_price")
                backtest_price = (
                    _to_decimal(backtest_price_raw) if backtest_price_raw is not None else None
                )
                slippage_bps = int(row.get("slippage_bps") or 0)
                strategy = str(row.get("strategy") or "")
                meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}

                fill = FillRecord(
                    fill_id=fill_id,
                    order_id=broker_order_id or fill_id,  # best-effort
                    broker_order_id=broker_order_id,
                    instrument_id=instrument,
                    side=side,
                    quantity=quantity,
                    price=price,
                    commission=Decimal("0"),
                    slippage_bps=slippage_bps,
                    backtest_price=backtest_price,
                    strategy=strategy,
                    meta=dict(meta),
                    filled_at=filled_at,
                )
                if self.append_fill(fill):
                    imported += 1
        return imported

    # ------------------------------------------------------------------
    # Stats (lightweight, used by tests + ops dashboards)
    # ------------------------------------------------------------------
    def stats(self) -> dict[str, int]:
        """Row counts for every table — used by tests and ops dashboards."""
        out: dict[str, int] = {}
        for table in ("orders", "fills", "positions", "equity_snapshots", "audit_log"):
            with self._lock:
                row = self._conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            out[table] = int(row["n"]) if row else 0
        return out


# =========================================================================
# Row → dataclass helpers
# =========================================================================


def _row_to_order(row: sqlite3.Row) -> OrderRecord:
    meta_raw = row["meta_json"] or "{}"
    try:
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else {}
    except json.JSONDecodeError:
        meta = {}
    return OrderRecord(
        order_id=str(row["order_id"]),
        broker_order_id=str(row["broker_order_id"] or ""),
        instrument_id=str(row["instrument_id"]),
        side=str(row["side"]),
        quantity=_to_decimal(row["quantity"]),
        order_type=str(row["order_type"]),
        status=str(row["status"]),
        price=_to_decimal(row["price"]) if row["price"] is not None else None,
        stop_price=_to_decimal(row["stop_price"]) if row["stop_price"] is not None else None,
        take_profit_price=(
            _to_decimal(row["take_profit_price"]) if row["take_profit_price"] is not None else None
        ),
        strategy=str(row["strategy"] or ""),
        meta=dict(meta),
        submitted_at=str(row["submitted_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_fill(row: sqlite3.Row) -> FillRecord:
    meta_raw = row["meta_json"] or "{}"
    try:
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else {}
    except json.JSONDecodeError:
        meta = {}
    return FillRecord(
        fill_id=str(row["fill_id"]),
        order_id=str(row["order_id"]),
        broker_order_id=str(row["broker_order_id"]),
        instrument_id=str(row["instrument_id"]),
        side=str(row["side"]),
        quantity=_to_decimal(row["quantity"]),
        price=_to_decimal(row["price"]),
        commission=_to_decimal(row["commission"]),
        slippage_bps=int(row["slippage_bps"] or 0),
        backtest_price=(
            _to_decimal(row["backtest_price"]) if row["backtest_price"] is not None else None
        ),
        strategy=str(row["strategy"] or ""),
        meta=dict(meta),
        filled_at=str(row["filled_at"]),
    )


def _row_to_position(row: sqlite3.Row) -> PositionRecord:
    return PositionRecord(
        instrument_id=str(row["instrument_id"]),
        quantity=_to_decimal(row["quantity"]),
        avg_price=_to_decimal(row["avg_price"]),
        realized_pnl=_to_decimal(row["realized_pnl"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_equity(row: sqlite3.Row) -> EquitySnapshot:
    return EquitySnapshot(
        ts=str(row["ts"]),
        cash=_to_decimal(row["cash"]),
        positions_value=_to_decimal(row["positions_value"]),
        equity=_to_decimal(row["equity"]),
        daily_pnl=_to_decimal(row["daily_pnl"]),
        cycle_index=int(row["cycle_index"] or 0),
    )


def _row_to_audit(row: sqlite3.Row) -> AuditEvent:
    payload_raw = row["payload_json"] or "{}"
    try:
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else {}
    except json.JSONDecodeError:
        payload = {}
    return AuditEvent(
        id=int(row["id"]), ts=str(row["ts"]), kind=str(row["kind"]), payload=dict(payload)
    )


def _legacy_fill_id(filled_at: str, broker_order_id: str, price: Decimal, quantity: Decimal) -> str:
    """Deterministic fill_id for legacy SlippageLedger rows.

    The legacy JSON did not carry a fill_id — derive one from the fields
    that uniquely identify a fill (the JSONL is append-only and a single
    order could in principle have multiple partial fills, so we include
    price + quantity too). SHA-256 hex truncated to 32 chars is short
    enough to keep indexes tight and long enough to avoid collisions.
    """
    import hashlib

    raw = f"{filled_at}|{broker_order_id}|{price}|{quantity}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


__all__ = [
    "SCHEMA_VERSION",
    "AuditEvent",
    "EquitySnapshot",
    "ExecutionStore",
    "FillRecord",
    "OrderRecord",
    "PositionRecord",
]
