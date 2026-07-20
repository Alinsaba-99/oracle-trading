"""Tests for PostgresLedger — durable PostgreSQL-backed ledger."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from core.ledger_postgres import PostgresLedger


class TestPostgresLedger:

    @pytest.mark.asyncio
    async def test_create(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create("postgresql://test:5432/oracle")
        assert ledger._pool is not None

    @pytest.mark.asyncio
    async def test_create_account(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        account = ledger.create_account("paper", Decimal("50000"))
        assert account.account_type == "paper"
        assert account.initial_balance == Decimal("50000")
        assert account.current_balance == Decimal("50000")
        cached = ledger.get_account(account.account_id)
        assert cached is not None

    @pytest.mark.asyncio
    async def test_record_fill(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        account = ledger.create_account("paper", Decimal("100000"))
        entry = ledger.record_fill(
            account_id=account.account_id, fill_id="f1",
            order_id="o1", quantity=Decimal("2"),
            price=Decimal("5000"), commission=Decimal("5"),
            direction="buy",
        )
        assert entry is not None
        assert entry.entry_type == "trade"
        new_bal = ledger.get_balance(account.account_id)
        assert new_bal == Decimal("89995")  # 100000 - 10000 - 5

    @pytest.mark.asyncio
    async def test_negative_balance_rejected(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        account = ledger.create_account("paper", Decimal("1000"))
        entry = ledger.record_fill(
            account_id=account.account_id, fill_id="f_bad",
            order_id="o_bad", quantity=Decimal("10"),
            price=Decimal("200"), direction="buy",
        )
        assert entry is None

    @pytest.mark.asyncio
    async def test_get_balance_unknown(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        assert ledger.get_balance("nonexistent") == Decimal("0")

    @pytest.mark.asyncio
    async def test_close(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        await ledger.close()
        assert ledger._pool is None
