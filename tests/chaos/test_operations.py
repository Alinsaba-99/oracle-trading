"""Chaos tests — disconnect, delayed fill, duplicate event, clock drift.

These tests verify that the system remains safe under adverse conditions.
They simulate real-world failure modes that the paper/shadow path must
survive (G6 requirement).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.kill import KillSwitch
from core.oms import Fill, InMemoryOMS, Order
from execution.brokers.paper import PaperBroker
from execution.brokers.types import BrokerOrder


class TestKillSwitch:
    """Emergency stop tests."""

    @pytest.mark.asyncio
    async def test_flatten_all_cancels_orders(self) -> None:
        """Kill switch cancels open orders."""
        broker = MagicMock()
        broker.cancel_all_orders = AsyncMock(return_value=3)
        broker.positions = AsyncMock(return_value=[])

        kill = KillSwitch(broker)
        result = await kill.flatten_all()
        assert result["open_orders_cancelled"] == 3
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_flatten_positions(self) -> None:
        """Kill switch flattens all positions."""
        broker = MagicMock()
        broker.cancel_all_orders = AsyncMock(return_value=0)
        broker.positions = AsyncMock(
            return_value=[
                {"instrument_id": "ES", "side": "long", "quantity": 2},
                {"instrument_id": "NQ", "side": "short", "quantity": 1},
            ]
        )
        broker.submit_order = AsyncMock(return_value={"order_id": "test"})

        kill = KillSwitch(broker)
        result = await kill.flatten_all()
        assert result["positions_flattened"] == 2
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_broker_error_does_not_crash(self) -> None:
        """Kill switch handles broker errors gracefully."""
        broker = MagicMock()
        broker.cancel_all_orders = AsyncMock(side_effect=Exception("Connection lost"))
        broker.positions = AsyncMock(return_value=[])

        kill = KillSwitch(broker)
        result = await kill.flatten_all()
        assert isinstance(result, dict)
        assert "errors" in result

    @pytest.mark.asyncio
    async def test_real_paper_broker_is_verified_flat(self) -> None:
        broker = PaperBroker()
        await broker.submit_order(
            BrokerOrder(
                broker_order_id="entry",
                local_order_id="entry",
                namespaced_id="test:entry",
                instrument_id="ES",
                side="buy",
                quantity=Decimal("1"),
                order_type="market",
            )
        )

        result = await KillSwitch(broker).flatten_all()

        assert result["success"] is True
        assert await broker.positions() == []


class TestDuplicateFill:
    """Duplicate fill detection under chaos."""

    def test_duplicate_fill_idempotent(self) -> None:
        """Duplicate broker_fill_id does not double-count."""
        oms = InMemoryOMS()
        order = Order(account_id="a1", client_order_id="c1", quantity=Decimal("10"))
        created = oms.create_order(order)

        fill1 = Fill(
            order_id=created.order_id,
            account_id="a1",
            quantity=Decimal("10"),
            price=Decimal("5000"),
            broker_fill_id="bf-1",
        )
        oms.record_fill(fill1)

        # Same fill again (duplicate from broker)
        oms.record_fill(fill1)

        updated = oms.get_order(created.order_id)
        assert updated is not None
        assert updated.filled_quantity == Decimal("10")  # Not 20

    def test_out_of_order_fill(self) -> None:
        """Out-of-order fills are handled correctly."""
        oms = InMemoryOMS()
        order = Order(account_id="a1", client_order_id="c1", quantity=Decimal("10"))
        created = oms.create_order(order)

        # Fill comes in before order is submitted
        oms.record_fill(
            Fill(
                order_id=created.order_id,
                account_id="a1",
                quantity=Decimal("5"),
                price=Decimal("5000"),
            )
        )
        # Partial recorded
        updated = oms.get_order(created.order_id)
        assert updated is not None
        assert updated.filled_quantity == Decimal("5")
        assert updated.status == "partially_filled"
