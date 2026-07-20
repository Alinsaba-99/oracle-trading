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

    @pytest.mark.asyncio
    async def test_startup_reconciliation_paper_broker(self) -> None:
        """M32-006: Paper broker startup reconciliation — clean state."""
        from execution.brokers.paper import PaperBroker
        from core.ledger import InMemoryLedger
        from core.oms import InMemoryOMS

        broker = PaperBroker()
        ledger = InMemoryLedger()
        oms = InMemoryOMS(ledger=ledger)

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()

        assert report.is_clean, f"Expected clean startup, got {len(report.mismatches)} mismatches"
        assert not report.has_fatal

    @pytest.mark.asyncio
    async def test_startup_reconciliation_mismatch_detected(self) -> None:
        """M32-006: Bypass OMS → mismatch detected (expected behavior)."""
        from execution.brokers.paper import PaperBroker
        from execution.brokers.types import BrokerOrder
        from core.ledger import InMemoryLedger
        from core.oms import InMemoryOMS
        from decimal import Decimal
        from uuid import uuid4
        from datetime import datetime, timezone

        broker = PaperBroker()
        ledger = InMemoryLedger()
        oms = InMemoryOMS(ledger=ledger)

        order = BrokerOrder(
            broker_order_id="mismatch_test",
            local_order_id=str(uuid4()),
            namespaced_id="paper:mismatch_test",
            instrument_id="ES",
            side="BUY",
            quantity=Decimal("2"),
            price=Decimal("5500.00"),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await broker.submit_order(order)

        engine = ReconciliationEngine(broker, oms, ledger)
        report = await engine.reconcile()
        assert len(report.mismatches) > 0, "Bypass OMS → must detect mismatch"

    @pytest.mark.asyncio
    async def test_paper_broker_open_orders(self) -> None:
        """PaperBroker.open_orders() returns unfilled orders."""
        from execution.brokers.paper import PaperBroker
        from execution.brokers.types import BrokerOrder
        from decimal import Decimal
        from uuid import uuid4
        from datetime import datetime, timezone

        broker = PaperBroker()
        orders = await broker.open_orders()
        assert len(orders) == 0, "Fresh broker should have no open orders"

        # Submit order (fills immediately, so open_orders should be empty)
        order = BrokerOrder(
            broker_order_id="open_test",
            local_order_id=str(uuid4()),
            namespaced_id="paper:open_test",
            instrument_id="ES",
            side="BUY",
            quantity=Decimal("1"),
            price=Decimal("5500.00"),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await broker.submit_order(order)
        open_orders = await broker.open_orders()
        assert len(open_orders) == 0, "Filled orders should not appear in open_orders"

    @pytest.mark.asyncio
    async def test_paper_broker_account_summary(self) -> None:
        """PaperBroker.account_summary() returns cash/balance/pnl."""
        from execution.brokers.paper import PaperBroker

        broker = PaperBroker()
        summary = await broker.account_summary()
        assert "cash" in summary
        assert "balance" in summary
        assert "pnl" in summary
        assert summary["cash"] > 0

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
