"""Tests for reconciliation engine — broker vs OMS vs ledger."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.reconciliation import MismatchSeverity, MismatchType, ReconciliationEngine


class TestReconciliation:
    """Reconciliation engine tests."""

    @pytest.mark.asyncio
    async def test_clean_reconciliation(self) -> None:
        """No mismatches → clean report."""
        broker = MagicMock()
        broker.positions = AsyncMock(return_value=[])
        broker.open_orders = AsyncMock(return_value=[])

        oms = MagicMock()
        oms._orders = {}

        ledger = MagicMock()
        ledger._accounts = {}

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()
        assert report.is_clean
        assert report.mismatches == []

    @pytest.mark.asyncio
    async def test_typed_broker_position_is_reconciled(self) -> None:
        from execution.brokers.types import BrokerPosition

        broker = MagicMock()
        broker.positions = AsyncMock(
            return_value=[
                BrokerPosition(instrument_id="ES", quantity=Decimal("1"), avg_price=Decimal("5000"))
            ]
        )
        broker.open_orders = AsyncMock(return_value=[])

        oms = MagicMock()
        oms._orders = {}

        ledger = MagicMock()
        ledger._accounts = {}

        report = await ReconciliationEngine(broker, oms, ledger).reconcile()

        assert not report.is_clean
        assert report.mismatches[0].mismatch_type == MismatchType.POSITION

    @pytest.mark.asyncio
    async def test_position_mismatch_detected(self) -> None:
        """Different position sizes → mismatch."""
        broker = MagicMock()
        broker.positions = AsyncMock(
            return_value=[{"instrument_id": "ES", "side": "long", "quantity": 5}]
        )
        broker.open_orders = AsyncMock(return_value=[])

        # OMS has order for 2 ES contracts
        oms = MagicMock()
        oms._orders = {
            "order1": MagicMock(
                instrument_id="ES", side="buy", filled_quantity=2, broker_order_id="brk1"
            )
        }

        ledger = MagicMock()
        ledger._accounts = {}
        ledger._entries = []

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()

        assert not report.is_clean
        assert len(report.mismatches) == 1
        assert report.mismatches[0].mismatch_type == MismatchType.POSITION

    @pytest.mark.asyncio
    async def test_orphan_broker_order(self) -> None:
        """Order in broker but not in OMS → mismatch."""
        broker = MagicMock()
        broker.positions = AsyncMock(return_value=[])
        broker.open_orders = AsyncMock(return_value=[MagicMock(broker_order_id="orphan-1")])

        oms = MagicMock()
        oms._orders = {}

        ledger = MagicMock()
        ledger._accounts = {}

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()

        assert len(report.mismatches) > 0
        assert report.mismatches[0].mismatch_type == MismatchType.ORDER

    @pytest.mark.asyncio
    async def test_fatal_position_mismatch_blocks(self) -> None:
        """Large position mismatch → fatal → blocks new orders."""
        broker = MagicMock()
        broker.positions = AsyncMock(
            return_value=[{"instrument_id": "ES", "side": "long", "quantity": 100}]
        )
        broker.open_orders = AsyncMock(return_value=[])

        oms = MagicMock()
        oms._orders = {}

        ledger = MagicMock()
        ledger._accounts = {}

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()

        assert report.has_fatal
        assert engine.is_blocked()

    @pytest.mark.asyncio
    async def test_blocked_prevents_trading(self) -> None:
        """When blocked, new orders should be prevented."""
        broker = MagicMock()
        broker.positions = AsyncMock(
            return_value=[{"instrument_id": "ES", "side": "long", "quantity": 100}]
        )
        broker.open_orders = AsyncMock(return_value=[])

        oms = MagicMock()
        oms._orders = {}

        ledger = MagicMock()
        ledger._accounts = {}

        engine = ReconciliationEngine(broker, oms, ledger)
        await engine.reconcile()
        assert engine.is_blocked()

        # Unblock after operator review
        engine.unblock()
        assert not engine.is_blocked()

    @pytest.mark.asyncio
    async def test_broker_disconnected(self) -> None:
        """Broker disconnect should not crash reconciliation."""
        broker = MagicMock()
        broker.positions = AsyncMock(side_effect=Exception("Connection refused"))
        broker.open_orders = AsyncMock(side_effect=Exception("Connection refused"))

        oms = MagicMock()
        oms._orders = {}

        ledger = MagicMock()
        ledger._accounts = {}

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()

        # Methods catch exceptions individually, report stays clean
        assert report.is_clean
        assert report.is_clean  # No mismatches if broker is down

    @pytest.mark.asyncio
    async def test_cash_mismatch(self) -> None:
        """Cash balance mismatch between broker and ledger."""
        broker = MagicMock()
        broker.positions = AsyncMock(return_value=[])
        broker.open_orders = AsyncMock(return_value=[])
        broker.account_summary = AsyncMock(return_value={"cash": 100000})

        oms = MagicMock()
        oms._orders = {}

        ledger = MagicMock()
        ledger._accounts = {"acct1": MagicMock(current_balance=95000)}

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()

        cash_mismatches = [m for m in report.mismatches if m.mismatch_type == MismatchType.CASH]
        assert len(cash_mismatches) == 1
        assert cash_mismatches[0].severity == MismatchSeverity.FATAL  # $5k diff > $100 threshold
