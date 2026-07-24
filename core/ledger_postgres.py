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
from decimal import Decimal

import asyncpg

from core.ledger import AccountEntry, LedgerEntry

logger = logging.getLogger("oracle.ledger.postgres")


class PostgresLedger:
    """PostgreSQL-backed ledger with double-entry accounting.

    Connection pooling via ``asyncpg.create_pool``.
    Schema is defined in ``db/schema.sql`` (accounts + ledger_entries tables).
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._accounts: dict[str, AccountEntry] = {}
        self._entries: list[LedgerEntry] = []

    # ── Factory ─────────────────────────────────────────────────────────

    @classmethod
    async def create(
        cls, dsn: str = "postgresql://localhost:5432/oracle", min_size: int = 1, max_size: int = 5
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
        """Ensure the ledger schema exists — compatible with ``db/schema.sql``.

        Uses ``UUID`` for ``account_id`` to match the canonical schema's
        ``accounts`` table.  The ``ledger_entries`` table is managed here
        (not in ``db/schema.sql``) because it's ledger-specific state.
        """
        if self._pool is None:
            raise RuntimeError("Not connected")
        conn = await self._pool.acquire()
        try:
            # Note: accounts table is created by db/schema.sql, but we
            # include CREATE IF NOT EXISTS here for test environments
            # where schema.sql may not have been pre-loaded.
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
                    account_id          UUID NOT NULL REFERENCES accounts(account_id),
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
                aid = str(row["account_id"])  # UUID → str for cache key
                self._accounts[aid] = AccountEntry(
                    account_id=aid,
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

    async def create_account(
        self,
        account_type: str = "paper",
        initial_balance: Decimal = Decimal("0"),
        currency: str = "USD",
        mode: str = "research",
    ) -> AccountEntry:
        """Create a new account (in-memory + persist to DB)."""
        account = AccountEntry(
            account_type=account_type,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            currency=currency,
            mode=mode,
        )
        self._accounts[account.account_id] = account
        # Persist to PostgreSQL
        if self._pool:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO accounts (account_id, account_type, mode, status,
                        initial_balance, current_balance, currency, version)
                       VALUES ($1, $2, $3, 'active', $4, $5, $6, 1)""",
                    account.account_id,
                    account.account_type,
                    account.mode,
                    str(account.initial_balance),
                    str(account.current_balance),
                    account.currency,
                )
        return account

    def get_account(self, account_id: str) -> AccountEntry | None:
        return self._accounts.get(account_id)

    # ── Ledger entries ──────────────────────────────────────────────────

    async def record_fill(
        self,
        account_id: str,
        order_id: str,
        fill_id: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal("0"),
        realized_pnl: Decimal = Decimal("0"),
        side: str = "buy",
    ) -> list[LedgerEntry]:
        """Record a fill — update balance in-memory and persist to PostgreSQL."""
        account = self.get_account(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        notional_amount = -(price * quantity) if side == "buy" else (price * quantity)
        total_impact = notional_amount + realized_pnl - commission

        written: list[LedgerEntry] = []

        notional_entry = LedgerEntry(
            account_id=account_id,
            order_id=order_id,
            fill_id=fill_id,
            amount=notional_amount,
            entry_type="notional",
            description=f"Notional {side}: {quantity} @ {price}",
        )
        self._entries.append(notional_entry)
        written.append(notional_entry)

        if realized_pnl != 0:
            pnl_entry = LedgerEntry(
                account_id=account_id,
                order_id=order_id,
                fill_id=fill_id,
                amount=realized_pnl,
                entry_type="trade",
                description=f"Fill P&L: {quantity} @ {price}",
            )
            self._entries.append(pnl_entry)
            written.append(pnl_entry)

        if commission > 0:
            comm_entry = LedgerEntry(
                account_id=account_id,
                order_id=order_id,
                fill_id=fill_id,
                amount=-commission,
                entry_type="commission",
                description=f"Commission: {commission}",
            )
            self._entries.append(comm_entry)
            written.append(comm_entry)

        # Update in-memory balance
        new_balance = account.current_balance + total_impact
        if new_balance < 0:
            raise ValueError(
                f"Insufficient balance: {account.current_balance} + {total_impact} = {new_balance}"
            )
        self._accounts[account_id] = AccountEntry(
            **{**account.__dict__, "current_balance": new_balance, "version": account.version + 1}
        )

        # Persist to PostgreSQL
        if self._pool:
            async with self._pool.acquire() as conn:
                for entry in written:
                    await conn.execute(
                        "INSERT INTO ledger_entries "
                        "(entry_id, account_id, order_id, fill_id, "
                        "amount, currency, entry_type, description) "
                        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                        entry.entry_id,
                        account_id,
                        entry.order_id,
                        entry.fill_id,
                        str(entry.amount),
                        entry.currency,
                        entry.entry_type,
                        entry.description,
                    )
                # Update account balance in DB
                await conn.execute(
                    "UPDATE accounts SET current_balance = $1, version = version + 1 "
                    "WHERE account_id = $2",
                    str(new_balance),
                    account_id,
                )

        return written

    def get_balance(self, account_id: str) -> Decimal:
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")
        return account.current_balance

    def get_entries(self, account_id: str) -> list[LedgerEntry]:
        return [e for e in self._entries if e.account_id == account_id]

    def get_all_entries(self) -> list[LedgerEntry]:
        return list(self._entries)

    # ── Persistence ─────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
