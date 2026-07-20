"""PostgreSQL Ledger — durable, double-entry account persistence.

Implements the same interface as ``InMemoryLedger`` but persists state
to PostgreSQL.  Uses ``asyncpg`` for connection pooling.

Usage::

    ledger = await PostgresLedger.create(dsn="postgresql://...")
    account = ledger.create_account("paper", Decimal("100000"))
    ledger.record_fill(...)
    balance = ledger.get_balance(account.account_id)
    await ledger.close()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import asyncpg

from core.ledger import AccountEntry, LedgerEntry, _utcnow

logger = logging.getLogger("oracle.ledger.postgres")


class PostgresLedger:
    """PostgreSQL-backed ledger with double-entry accounting.

    Connection pooling via ``asyncpg.create_pool``.
    Schema is defined in ``db/schema.sql`` (accounts + fills + positions tables).
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._accounts: dict[str, AccountEntry] = {}  # local cache

    # ── Factory ─────────────────────────────────────────────────────────

    @classmethod
    async def create(
        cls,
        dsn: str = "postgresql://localhost:5432/oracle",
        min_size: int = 1,
        max_size: int = 5,
    ) -> PostgresLedger:
        """Create and initialize a PostgresLedger with connection pool.

        Args:
            dsn: PostgreSQL connection string.
            min_size: Minimum pool connections.
            max_size: Maximum pool connections.

        Returns:
            Initialized PostgresLedger instance.
        """
        self = cls()
        self._pool = await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
        await self._ensure_schema()
        await self._load_accounts()
        logger.info(f"PostgresLedger initialized (pool {min_size}-{max_size})")
        return self

    async def _ensure_schema(self) -> None:
        """Ensure the ledger schema exists."""
        if self._pool is None:
            raise RuntimeError("Not connected")
        conn = await self._pool.acquire()
        try:
            # Create accounts table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id          TEXT PRIMARY KEY,
                    account_type        TEXT NOT NULL DEFAULT 'paper',
                    mode                TEXT NOT NULL DEFAULT 'research',
                    status              TEXT NOT NULL DEFAULT 'active',
                    initial_balance     NUMERIC(20,8) NOT NULL,
                    current_balance     NUMERIC(20,8) NOT NULL,
                    currency            TEXT NOT NULL DEFAULT 'USD',
                    version             INTEGER NOT NULL DEFAULT 1,
                    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger_entries (
                    entry_id            TEXT PRIMARY KEY,
                    account_id          TEXT NOT NULL REFERENCES accounts(account_id),
                    order_id            TEXT,
                    fill_id             TEXT,
                    amount              NUMERIC(20,8) NOT NULL,
                    currency            TEXT NOT NULL DEFAULT 'USD',
                    entry_type          TEXT NOT NULL DEFAULT 'trade',
                    description         TEXT,
                    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        finally:
            await self._pool.release(conn)

    async def _load_accounts(self) -> None:
        """Load existing accounts into local cache."""
        if self._pool is None:
            return
        conn = await self._pool.acquire()
        try:
            rows = await conn.fetch("SELECT * FROM accounts")
            for row in rows:
                self._accounts[row["account_id"]] = AccountEntry(
                    account_id=row["account_id"],
                    account_type=row["account_type"],
                    mode=row["mode"],
                    initial_balance=Decimal(str(row["initial_balance"])),
                    current_balance=Decimal(str(row["current_balance"])),
                    currency=row["currency"],
                    status=row["status"],
                    version=row["version"],
                )
        finally:
            await self._pool.release(conn)

    # ── Account management ──────────────────────────────────────────────

    def create_account(
        self,
        account_type: str = "paper",
        initial_balance: Decimal = Decimal("0"),
        currency: str = "USD",
        mode: str = "research",
    ) -> AccountEntry:
        """Create a new account (in-memory + persist to DB).

        Returns:
            The created AccountEntry.
        """
        account = AccountEntry(
            account_type=account_type,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            currency=currency,
            mode=mode,
        )
        self._accounts[account.account_id] = account
        # Async persist — fire-and-forget in-memory first
        import asyncio

        asyncio.ensure_future(self._persist_account(account))
        return account

    async def _persist_account(self, account: AccountEntry) -> None:
        """Persist account to PostgreSQL."""
        if self._pool is None:
            return
        conn = await self._pool.acquire()
        try:
            await conn.execute(
                """
                INSERT INTO accounts (account_id, account_type, mode, status,
                    initial_balance, current_balance, currency, version, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
                ON CONFLICT (account_id) DO UPDATE SET
                    current_balance = EXCLUDED.current_balance,
                    version = EXCLUDED.version,
                    updated_at = EXCLUDED.updated_at
                """,
                account.account_id,
                account.account_type,
                account.mode,
                account.status,
                str(account.initial_balance),
                str(account.current_balance),
                account.currency,
                account.version,
                account.created_at,
            )
        finally:
            await self._pool.release(conn)

    def get_account(self, account_id: str) -> AccountEntry | None:
        """Get account from local cache."""
        return self._accounts.get(account_id)

    # ── Ledger entries ──────────────────────────────────────────────────

    def record_fill(
        self,
        account_id: str,
        fill_id: str,
        order_id: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal("0"),
        direction: str = "buy",
    ) -> LedgerEntry | None:
        """Record a fill and update account balance.

        Returns the created LedgerEntry, or None if account not found.
        """
        account = self._accounts.get(account_id)
        if account is None:
            logger.warning(f"Account {account_id} not found")
            return None

        # Calculate trade value (debit for buy, credit for sell)
        trade_value = price * quantity
        if direction == "buy":
            trade_value = -trade_value  # buying: money leaves the account
        # else sell: money comes in

        # Update balance
        new_balance = account.current_balance + trade_value - commission
        if new_balance < 0:
            logger.warning(f"Negative balance {new_balance} for account {account_id}")
            return None

        entry = LedgerEntry(
            order_id=order_id,
            fill_id=fill_id,
            account_id=account_id,
            amount=trade_value,
            entry_type="trade",
            description=f"{direction} {quantity} @ {price}",
        )

        # Update in-memory state
        self._accounts[account_id] = AccountEntry(
            account_id=account.account_id,
            account_type=account.account_type,
            mode=account.mode,
            initial_balance=account.initial_balance,
            current_balance=new_balance,
            currency=account.currency,
            status=account.status,
            version=account.version + 1,
            created_at=account.created_at,
        )

        # Async persist
        import asyncio

        asyncio.ensure_future(self._persist_entry(entry))
        asyncio.ensure_future(self._persist_account(self._accounts[account_id]))

        return entry

    async def _persist_entry(self, entry: LedgerEntry) -> None:
        """Persist a ledger entry to PostgreSQL."""
        if self._pool is None:
            return
        conn = await self._pool.acquire()
        try:
            await conn.execute(
                """
                INSERT INTO ledger_entries (entry_id, account_id, order_id, fill_id,
                    amount, currency, entry_type, description, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (entry_id) DO NOTHING
                """,
                entry.entry_id,
                entry.account_id,
                entry.order_id,
                entry.fill_id,
                str(entry.amount),
                entry.currency,
                entry.entry_type,
                entry.description,
                entry.created_at,
            )
        finally:
            await self._pool.release(conn)

    # ── Query methods ───────────────────────────────────────────────────

    def get_balance(self, account_id: str) -> Decimal:
        """Get current balance for an account."""
        account = self._accounts.get(account_id)
        return account.current_balance if account else Decimal("0")

    def get_entries(self, account_id: str) -> list[LedgerEntry]:
        """Get all entries for an account (from in-memory cache)."""
        return [e for e in self._accounts.values() if hasattr(e, "account_id") and e.account_id == account_id]

    async def get_all_entries(self) -> list[LedgerEntry]:
        """Get all ledger entries from PostgreSQL."""
        if self._pool is None:
            return []
        conn = await self._pool.acquire()
        try:
            rows = await conn.fetch("SELECT * FROM ledger_entries ORDER BY created_at")
            result = [
                LedgerEntry(
                    entry_id=row["entry_id"],
                    account_id=row["account_id"],
                    order_id=row["order_id"],
                    fill_id=row["fill_id"],
                    amount=Decimal(str(row["amount"])),
                    currency=row["currency"],
                    entry_type=row["entry_type"],
                    description=row["description"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
            return result
        finally:
            await self._pool.release(conn)

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgresLedger connection pool closed")
