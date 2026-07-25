"""Tests for PostgresLedger — durable PostgreSQL-backed ledger.

Uses a mock asyncpg pool (fake_pg fixture) so no real PostgreSQL needed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.ledger_postgres import PostgresLedger


class TestPostgresLedger:
    @pytest.mark.asyncio
    async def test_create(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create("postgresql://test:5432/oracle")
        assert ledger._pool is not None
        await ledger.close()

    @pytest.mark.asyncio
    async def test_create_account(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        account = await ledger.create_account("paper", Decimal("50000"))
        assert account.account_type == "paper"
        assert account.initial_balance == Decimal("50000")
        assert account.current_balance == Decimal("50000")
        cached = ledger.get_account(account.account_id)
        assert cached is not None
        await ledger.close()

    @pytest.mark.asyncio
    async def test_record_fill(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        account = await ledger.create_account("paper", Decimal("100000"))
        entries = await ledger.record_fill(
            account_id=account.account_id,
            fill_id="f1",
            order_id="o1",
            quantity=Decimal("2"),
            price=Decimal("5000"),
            commission=Decimal("5"),
            realized_pnl=Decimal("0"),
            side="buy",
        )
        assert len(entries) > 0
        new_bal = ledger.get_balance(account.account_id)
        assert new_bal == Decimal("89995")  # 100000 - 10000 - 5
        await ledger.close()

    @pytest.mark.asyncio
    async def test_negative_balance_rejected(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        account = await ledger.create_account("paper", Decimal("1000"))
        with pytest.raises(ValueError, match="Insufficient balance"):
            await ledger.record_fill(
                account_id=account.account_id,
                fill_id="f_bad",
                order_id="o_bad",
                quantity=Decimal("10"),
                price=Decimal("200"),
                side="buy",
            )
        await ledger.close()

    @pytest.mark.asyncio
    async def test_get_balance_unknown(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        with pytest.raises(ValueError, match=r"Account .* not found"):
            ledger.get_balance("nonexistent")
        await ledger.close()

    @pytest.mark.asyncio
    async def test_record_fill_no_account(self, fake_pg: object) -> None:
        ledger = await PostgresLedger.create()
        with pytest.raises(ValueError, match=r"Account .* not found"):
            await ledger.record_fill(
                account_id="bad",
                fill_id="f",
                order_id="o",
                quantity=Decimal("1"),
                price=Decimal("10"),
                side="buy",
            )
        await ledger.close()
