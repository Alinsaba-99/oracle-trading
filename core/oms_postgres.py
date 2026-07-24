"""PostgreSQL OMS — durable order management with idempotent persistence.

Implements the same interface as ``InMemoryOMS`` but persists orders,
fills, and positions to PostgreSQL.  Uses ``asyncpg`` for connection pooling.

Usage::

    oms = await PostgresOMS.create(ledger=my_ledger, dsn="postgresql://...")
    order = await oms.submit_order(broker_order)
    fills = await oms.get_fills()
    await oms.close()
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from uuid import uuid4

import asyncpg

from core.ledger_postgres import PostgresLedger

logger = logging.getLogger("oracle.oms.postgres")


class PostgresOMS:
    """PostgreSQL-backed OMS with idempotent order management.

    Orders flow: pending → submitted → (filled | cancelled | rejected).
    Idempotency is enforced via client_order_id per account.
    """

    def __init__(self, ledger: PostgresLedger | None = None) -> None:
        self._pool: asyncpg.Pool | None = None
        self._ledger = ledger

    # ── Factory ─────────────────────────────────────────────────────────

    @classmethod
    async def create(
        cls,
        ledger: PostgresLedger | None = None,
        dsn: str = "postgresql://localhost:5432/oracle",
        min_size: int = 1,
        max_size: int = 5,
    ) -> PostgresOMS:
        """Create and initialize a PostgresOMS with connection pool.

        Args:
            ledger: Optional PostgresLedger instance for P&L tracking.
            dsn: PostgreSQL connection string.
            min_size: Minimum pool connections.
            max_size: Maximum pool connections.

        Returns:
            Initialized PostgresOMS instance.
        """
        self = cls(ledger=ledger)
        self._pool = await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
        await self._ensure_schema()
        logger.info(f"PostgresOMS initialized (pool {min_size}-{max_size})")
        return self

    async def _ensure_schema(self) -> None:
        """Ensure the OMS schema exists."""
        if self._pool is None:
            raise RuntimeError("Not connected")
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oms_orders (
                    order_id            TEXT PRIMARY KEY,
                    account_id          TEXT NOT NULL,
                    client_order_id     TEXT NOT NULL,
                    broker_order_id     TEXT,
                    instrument_id       TEXT NOT NULL,
                    side                TEXT NOT NULL,
                    order_type          TEXT NOT NULL DEFAULT 'market',
                    quantity            NUMERIC(20,8) NOT NULL,
                    filled_quantity     NUMERIC(20,8) NOT NULL DEFAULT 0,
                    price               NUMERIC(20,8),
                    status              TEXT NOT NULL DEFAULT 'pending',
                    strategy_id         TEXT,
                    source              TEXT NOT NULL DEFAULT 'api',
                    reject_reason       TEXT,
                    error_message       TEXT,
                    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                    submitted_at        TIMESTAMPTZ,
                    filled_at           TIMESTAMPTZ,
                    cancelled_at        TIMESTAMPTZ,
                    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                    version             INTEGER NOT NULL DEFAULT 1,
                    UNIQUE (account_id, client_order_id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oms_fills (
                    fill_id             TEXT PRIMARY KEY,
                    order_id            TEXT NOT NULL REFERENCES oms_orders(order_id),
                    account_id          TEXT NOT NULL,
                    broker_fill_id      TEXT,
                    quantity            NUMERIC(20,8) NOT NULL,
                    price               NUMERIC(20,8) NOT NULL,
                    commission          NUMERIC(20,8) NOT NULL DEFAULT 0,
                    realized_pnl        NUMERIC(20,8) NOT NULL DEFAULT 0,
                    fill_time           TIMESTAMPTZ NOT NULL DEFAULT now(),
                    idempotency_key     TEXT
                )
            """)

    # ── Order lifecycle ─────────────────────────────────────────────────

    async def submit_order(self, order: Any) -> str:
        """Submit an order and persist it.

        Idempotent: same client_order_id + account returns existing order.

        Args:
            order: BrokerOrder-like object with instrument_id, side, quantity, etc.

        Returns:
            Order ID string.
        """
        if self._pool is None:
            raise RuntimeError("Not connected")

        order_id = str(getattr(order, "order_id", uuid4()))
        account_id = getattr(order, "account_id", "default")
        client_order_id = getattr(order, "client_order_id", order_id)
        instrument_id = getattr(order, "instrument_id", "")
        side = getattr(order, "side", "buy")
        quantity = getattr(order, "quantity", Decimal("0"))
        price = getattr(order, "price", None)

        async with self._pool.acquire() as conn:
            # Check idempotency
            existing = await conn.fetchrow(
                "SELECT order_id, status FROM oms_orders WHERE account_id=$1 AND client_order_id=$2",
                account_id,
                client_order_id,
            )
            if existing:
                return existing["order_id"]

            # Insert order
            await conn.execute(
                """
                INSERT INTO oms_orders (order_id, account_id, client_order_id,
                    instrument_id, side, quantity, price, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'submitted')
                """,
                order_id,
                account_id,
                client_order_id,
                instrument_id,
                side,
                str(quantity),
                str(price) if price else None,
            )

        logger.info(f"Order {order_id} submitted ({side} {quantity} {instrument_id})")
        return order_id

    async def record_fill(
        self,
        order_id: str,
        fill_id: str | None = None,
        quantity: Decimal = Decimal("0"),
        price: Decimal = Decimal("0"),
        commission: Decimal = Decimal("0"),
    ) -> bool:
        """Record a fill for an order.

        Args:
            order_id: The order to fill.
            fill_id: Optional fill ID (auto-generated if None).
            quantity: Fill quantity.
            price: Fill price.
            commission: Commission charged.

        Returns:
            True if fill was recorded.
        """
        if self._pool is None:
            return False

        fill_id = fill_id or str(uuid4())

        async with self._pool.acquire() as conn:
            # Get current order
            order = await conn.fetchrow("SELECT * FROM oms_orders WHERE order_id=$1", order_id)
            if order is None:
                logger.warning(f"Order {order_id} not found")
                return False

            new_filled = Decimal(str(order["filled_quantity"])) + quantity
            new_status = (
                "filled" if new_filled >= Decimal(str(order["quantity"])) else "partially_filled"
            )

            # Insert fill
            await conn.execute(
                """
                INSERT INTO oms_fills (fill_id, order_id, account_id, quantity, price, commission)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (fill_id) DO NOTHING
                """,
                fill_id,
                order_id,
                order["account_id"],
                str(quantity),
                str(price),
                str(commission),
            )

            # Update order
            await conn.execute(
                """
                UPDATE oms_orders SET
                    filled_quantity = $2,
                    status = $3,
                    filled_at = CASE WHEN $3 = 'filled' THEN now() ELSE filled_at END,
                    updated_at = now(),
                    version = version + 1
                WHERE order_id = $1
                """,
                order_id,
                str(new_filled),
                new_status,
            )

            # Record in ledger if available
            if self._ledger:
                direction = order["side"]
                self._ledger.record_fill(
                    account_id=order["account_id"],
                    fill_id=fill_id,
                    order_id=order_id,
                    quantity=quantity,
                    price=price,
                    commission=commission,
                    direction=direction,
                )

        logger.info(f"Fill {fill_id}: {quantity} @ {price} for order {order_id}")
        return True

    # ── Query methods ───────────────────────────────────────────────────

    async def get_order(self, order_id: str) -> dict[str, Any] | None:
        """Get order details."""
        if self._pool is None:
            return None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM oms_orders WHERE order_id=$1", order_id)
            if row:
                return dict(row)
            return None

    async def get_orders(
        self, account_id: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        """Get orders, optionally filtered."""
        if self._pool is None:
            return []
        async with self._pool.acquire() as conn:
            if account_id and status:
                rows = await conn.fetch(
                    "SELECT * FROM oms_orders WHERE account_id=$1 AND status=$2 ORDER BY created_at DESC",
                    account_id,
                    status,
                )
            elif account_id:
                rows = await conn.fetch(
                    "SELECT * FROM oms_orders WHERE account_id=$1 ORDER BY created_at DESC",
                    account_id,
                )
            else:
                rows = await conn.fetch("SELECT * FROM oms_orders ORDER BY created_at DESC")
            return [dict(r) for r in rows]

    async def get_fills(self, order_id: str | None = None) -> list[dict[str, Any]]:
        """Get fills, optionally filtered by order."""
        if self._pool is None:
            return []
        async with self._pool.acquire() as conn:
            if order_id:
                rows = await conn.fetch(
                    "SELECT * FROM oms_fills WHERE order_id=$1 ORDER BY fill_time", order_id
                )
            else:
                rows = await conn.fetch("SELECT * FROM oms_fills ORDER BY fill_time")
            return [dict(r) for r in rows]

    async def get_open_orders(self, account_id: str | None = None) -> list[dict[str, Any]]:
        """Get orders with status 'submitted' or 'partially_filled'."""
        if self._pool is None:
            return []
        async with self._pool.acquire() as conn:
            if account_id:
                rows = await conn.fetch(
                    "SELECT * FROM oms_orders WHERE account_id=$1 AND status IN ('submitted','partially_filled') ORDER BY created_at",
                    account_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM oms_orders WHERE status IN ('submitted','partially_filled') ORDER BY created_at"
                )
            return [dict(r) for r in rows]

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgresOMS connection pool closed")
