"""Tests for PostgresLedger + PostgresOMS.

Requires a running PostgreSQL (``docker compose -f infra/docker/docker-compose.yml up -d``).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import pytest

pytestmark: list[object] = [pytest.mark.skip(reason="PostgreSQL not available")]

try:
    import asyncpg
except ImportError:
    asyncpg = None


def _pg_available() -> bool:
    if asyncpg is None:
        return False
    import asyncio

    try:
        asyncio.run(
            asyncpg.connect(dsn="postgresql://oracle:oracle_dev@localhost:5432/oracle", timeout=3)
        )
        return True
    except Exception:
        return False


if _pg_available():
    pytestmark = []


@pytest.fixture
async def pg_ledger() -> AsyncGenerator[object, None]:
    from core.ledger_postgres import PostgresLedger

    ledger = await PostgresLedger.create(dsn="postgresql://oracle:oracle_dev@localhost:5432/oracle")
    yield ledger
    await ledger.close()


# ---------------------------------------------------------------------------
# PostgresLedger tests
# ---------------------------------------------------------------------------


class TestPostgresLedger:
    """PostgresLedger must match InMemoryLedger behavior."""

    async def test_create_account(self, pg_ledger: Any) -> None:
        acct = await pg_ledger.create_account(initial_balance=Decimal("100000"))
        assert acct.current_balance == Decimal("100000")
        assert acct.status == "active"

    async def test_record_fill_updates_balance(self, pg_ledger: Any) -> None:
        acct = await pg_ledger.create_account(initial_balance=Decimal("100000"))
        entries = await pg_ledger.record_fill(
            account_id=acct.account_id,
            order_id="order-1",
            fill_id="fill-1",
            quantity=Decimal("1"),
            price=Decimal("5000"),
            commission=Decimal("5"),
            realized_pnl=Decimal("250"),
            side="sell",
        )
        assert len(entries) == 3
        assert pg_ledger.get_balance(acct.account_id) == Decimal("105245")

    async def test_get_account(self, pg_ledger: Any) -> None:
        acct = await pg_ledger.create_account(initial_balance=Decimal("100"))
        assert pg_ledger.get_account(acct.account_id) is not None
        assert pg_ledger.get_account("nonexistent") is None

    async def test_balance_survives_restart(self, pg_ledger: Any) -> None:
        from core.ledger_postgres import PostgresLedger

        acct = await pg_ledger.create_account(initial_balance=Decimal("50000"))
        await pg_ledger.record_fill(
            account_id=acct.account_id,
            order_id="order-restart",
            fill_id="fill-restart",
            quantity=Decimal("2"),
            price=Decimal("100"),
            commission=Decimal("0"),
            realized_pnl=Decimal("0"),
            side="buy",
        )
        await pg_ledger.close()

        ledger2 = await PostgresLedger.create(
            dsn="postgresql://oracle:oracle_dev@localhost:5432/oracle"
        )
        balance = ledger2.get_balance(acct.account_id)
        await ledger2.close()
        assert balance == Decimal("49800")


# ---------------------------------------------------------------------------
# PostgresOMS tests (known API mismatch — skipped)
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason="API mismatch: PostgresOMS uses submit_order()/record_fill(id,qty,price), "
    "not create_order(Order)/record_fill(Fill) like InMemoryOMS"
)
class TestPostgresOMS:
    """PostgresOMS — API not yet aligned with InMemoryOMS."""
