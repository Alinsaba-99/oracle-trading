"""Tests for the OrderManager — deterministic fill/risk/broker flow."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.domain.enums import OrderSide, OrderStatus, OrderType
from core.domain.order import Order
from execution.order_manager.errors import InvalidOrderError
from execution.order_manager.manager import OrderManager
from execution.order_manager.types import FillReport, OrderRequest

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_broker() -> MagicMock:
    """Return a broker with async submit_order and cancel_order."""
    broker = MagicMock()
    broker.submit_order = AsyncMock(return_value="broker-abc-123")
    broker.cancel_order = AsyncMock(return_value=True)
    return broker


@pytest.fixture
def mock_risk() -> MagicMock:
    """Return a risk manager with async check_order (default: pass)."""
    risk = MagicMock()
    risk.check_order = AsyncMock(return_value=True)
    return risk


@pytest.fixture
def manager(mock_broker: MagicMock) -> OrderManager:
    """Return an OrderManager with a clean mock broker and no risk manager."""
    return OrderManager(broker=mock_broker, risk_manager=None)


@pytest.fixture
def manager_with_risk(mock_broker: MagicMock, mock_risk: MagicMock) -> OrderManager:
    """Return an OrderManager with both broker and risk manager wired."""
    return OrderManager(broker=mock_broker, risk_manager=mock_risk)


@pytest.fixture
def buy_request() -> OrderRequest:
    """Standard market buy order."""
    return OrderRequest(
        instrument_id="AAPL",
        side="buy",
        quantity=Decimal("100"),
        order_type="market",
        time_in_force="day",
    )


# =========================================================================
# submit — happy path
# =========================================================================


class TestSubmitHappy:
    """Order submission with no errors."""

    @pytest.mark.asyncio
    async def test_creates_order_with_correct_fields(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """Submit returns OrderResult with submitted status and populates internal state."""
        result = await manager.submit(buy_request)

        assert result.status == "submitted"
        assert result.request_id == buy_request.request_id
        assert result.broker_order_id == "broker-abc-123"
        assert result.order_id != ""

        order = manager.get_order(result.order_id)
        assert order is not None
        assert order.instrument_id == "AAPL"
        assert order.side == OrderSide.buy
        assert order.order_type == OrderType.market
        assert order.quantity == Decimal("100")
        assert order.status == OrderStatus.submitted

    @pytest.mark.asyncio
    async def test_creates_limit_order_with_price(self, manager: OrderManager) -> None:
        """Limit order preserves price and uses limit order type."""
        req = OrderRequest(
            instrument_id="MSFT",
            side="sell",
            quantity=Decimal("50"),
            order_type="limit",
            price=Decimal("450.00"),
            time_in_force="day",
        )
        result = await manager.submit(req)
        order = manager.get_order(result.order_id)
        assert order is not None
        assert order.order_type == OrderType.limit
        assert order.price == Decimal("450.00")
        assert result.status == "submitted"


# =========================================================================
# submit — validation errors
# =========================================================================


class TestSubmitValidation:
    """Order validation fails gracefully."""

    @pytest.mark.asyncio
    async def test_raises_on_zero_quantity(self, manager: OrderManager) -> None:
        """Zero quantity raises InvalidOrderError."""
        req = OrderRequest(instrument_id="AAPL", side="buy", quantity=Decimal("0"))
        with pytest.raises(InvalidOrderError, match="Quantity must be positive"):
            await manager.submit(req)

    @pytest.mark.asyncio
    async def test_raises_on_negative_quantity(self, manager: OrderManager) -> None:
        """Negative quantity raises InvalidOrderError."""
        req = OrderRequest(instrument_id="AAPL", side="buy", quantity=Decimal("-10"))
        with pytest.raises(InvalidOrderError, match="Quantity must be positive"):
            await manager.submit(req)


# =========================================================================
# submit — risk gate rejection
# =========================================================================


class TestSubmitRiskGate:
    """Risk gate #2 blocks submission."""

    @pytest.mark.asyncio
    async def test_risk_gate_rejection_returns_rejected_status(
        self, manager_with_risk: OrderManager, buy_request: OrderRequest
    ) -> None:
        """When risk gate returns False, result has status rejected."""
        manager_with_risk._risk.check_order = AsyncMock(return_value=False)
        result = await manager_with_risk.submit(buy_request)
        assert result.status == "rejected"
        assert result.error == "Risk gate #2 rejected"

    @pytest.mark.asyncio
    async def test_risk_gate_not_configured_passes_through(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """When risk_manager is None, submission proceeds without risk check."""
        result = await manager.submit(buy_request)
        assert result.status == "submitted"

    @pytest.mark.asyncio
    async def test_no_order_stored_on_risk_rejection(
        self, manager_with_risk: OrderManager, buy_request: OrderRequest
    ) -> None:
        """Risk-rejected orders are not stored in internal state."""
        manager_with_risk._risk.check_order = AsyncMock(return_value=False)
        result = await manager_with_risk.submit(buy_request)
        assert result.status == "rejected"
        assert len(manager_with_risk._orders) == 0


# =========================================================================
# submit — broker errors
# =========================================================================


class TestSubmitBrokerError:
    """Broker exception handling."""

    @pytest.mark.asyncio
    async def test_broker_exception_returns_rejected(
        self, manager: OrderManager, buy_request: OrderRequest, mock_broker: MagicMock
    ) -> None:
        """When broker.submit_order raises, result is rejected and order stored as rejected."""
        mock_broker.submit_order = AsyncMock(side_effect=TimeoutError("broker timeout"))
        result = await manager.submit(buy_request)
        assert result.status == "rejected"
        assert "broker timeout" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_broker_exception_stores_order_as_rejected(
        self, manager: OrderManager, buy_request: OrderRequest, mock_broker: MagicMock
    ) -> None:
        """When broker.submit_order raises, the order is stored with rejected status."""
        mock_broker.submit_order = AsyncMock(side_effect=TimeoutError("broker timeout"))
        result = await manager.submit(buy_request)
        order = manager.get_order(result.order_id)
        assert order is not None
        assert order.status == OrderStatus.rejected
        assert order.error


# =========================================================================
# cancel
# =========================================================================


class TestCancel:
    """Order cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_returns_true_on_success(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """Cancel a submitted order returns True."""
        result = await manager.submit(buy_request)
        cancelled = await manager.cancel(result.order_id)
        assert cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_unknown_order_returns_false(self, manager: OrderManager) -> None:
        """Cancel with non-existent order ID returns False."""
        cancelled = await manager.cancel("nonexistent")
        assert cancelled is False

    @pytest.mark.asyncio
    async def test_cancel_without_broker_id_returns_false(self, manager: OrderManager) -> None:
        """Cancel an order that has no broker_order_id returns False."""
        order = Order(
            instrument_id="AAPL",
            quantity=Decimal("100"),
            side=OrderSide.buy,
            order_type=OrderType.market,
            portfolio_id="",
        )
        manager._orders[order.order_id] = order
        cancelled = await manager.cancel(order.order_id)
        assert cancelled is False


# =========================================================================
# get_order
# =========================================================================


class TestGetOrder:
    """Lookup by order ID."""

    def test_returns_none_for_unknown_id(self, manager: OrderManager) -> None:
        """get_order returns None when order_id is not tracked."""
        assert manager.get_order("unknown-id") is None

    @pytest.mark.asyncio
    async def test_returns_order_after_submit(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """get_order returns the stored order after successful submit."""
        result = await manager.submit(buy_request)
        order = manager.get_order(result.order_id)
        assert order is not None
        assert order.order_id == result.order_id


# =========================================================================
# open_orders
# =========================================================================


class TestOpenOrders:
    """Filtering open orders."""

    @pytest.mark.asyncio
    async def test_open_orders_filters_by_is_open(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """open_orders only returns orders with an open status."""
        await manager.submit(buy_request)
        assert len(manager.open_orders()) == 1

        # Manually mark the order as filled
        order = next(iter(manager._orders.values()))
        order.status = OrderStatus.filled
        assert len(manager.open_orders()) == 0

    def test_open_orders_empty_initially(self, manager: OrderManager) -> None:
        """New manager has no open orders."""
        assert manager.open_orders() == []


# =========================================================================
# kill_all
# =========================================================================


class TestKillAll:
    """Cancel all open orders."""

    @pytest.mark.asyncio
    async def test_kill_all_cancels_open_orders(
        self, manager: OrderManager, buy_request: OrderRequest, mock_broker: MagicMock
    ) -> None:
        """kill_all cancels every open order and returns the count."""
        await manager.submit(buy_request)
        await manager.submit(
            OrderRequest(instrument_id="MSFT", side="sell", quantity=Decimal("50"))
        )

        count = await manager.kill_all()
        assert count == 2
        assert mock_broker.cancel_order.call_count == 2

    @pytest.mark.asyncio
    async def test_kill_all_with_no_open_orders(self, manager: OrderManager) -> None:
        """kill_all returns 0 when there are no open orders."""
        count = await manager.kill_all()
        assert count == 0

    @pytest.mark.asyncio
    async def test_kill_all_does_not_cancel_filled_orders(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """kill_all skips orders that have no broker_order_id or are not open."""
        await manager.submit(buy_request)
        order = next(iter(manager._orders.values()))
        order.status = OrderStatus.filled

        count = await manager.kill_all()
        assert count == 0


# =========================================================================
# on_fill
# =========================================================================


class TestOnFill:
    """Fill callback updates order state."""

    @pytest.mark.asyncio
    async def test_on_fill_updates_filled_quantity(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """Partial fill increments filled_quantity and sets partially_filled status."""
        result = await manager.submit(buy_request)
        fill = FillReport(
            order_id=result.order_id,
            broker_order_id="broker-abc-123",
            fill_id="fill-001",
            quantity=Decimal("40"),
            price=Decimal("150.00"),
        )
        await manager.on_fill(fill)

        order = manager.get_order(result.order_id)
        assert order is not None
        assert order.filled_quantity == Decimal("40")
        assert order.status == OrderStatus.partially_filled

    @pytest.mark.asyncio
    async def test_on_fill_completes_order(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """Full fill sets status to filled."""
        result = await manager.submit(buy_request)
        fill = FillReport(
            order_id=result.order_id,
            broker_order_id="broker-abc-123",
            fill_id="fill-001",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
        )
        await manager.on_fill(fill)

        order = manager.get_order(result.order_id)
        assert order is not None
        assert order.filled_quantity == Decimal("100")
        assert order.status == OrderStatus.filled

    @pytest.mark.asyncio
    async def test_on_fill_unknown_order_is_noop(self, manager: OrderManager) -> None:
        """on_fill with an unknown order_id does nothing (no crash)."""
        fill = FillReport(
            order_id="unknown",
            broker_order_id="broker-xyz",
            fill_id="fill-999",
            quantity=Decimal("10"),
            price=Decimal("100.00"),
        )
        # Should not raise
        await manager.on_fill(fill)

    @pytest.mark.asyncio
    async def test_on_fill_updates_inventory(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """Fill updates inventory tracker with the position."""
        result = await manager.submit(buy_request)
        fill = FillReport(
            order_id=result.order_id,
            broker_order_id="broker-abc-123",
            fill_id="fill-001",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
        )
        await manager.on_fill(fill)
        pos = manager._inventory.position("AAPL")
        assert pos == Decimal("100")


# =========================================================================
# Duplicate / edge cases
# =========================================================================


class TestEdgeCases:
    """Edge cases and duplicate handling."""

    @pytest.mark.asyncio
    async def test_multiple_orders_tracked_separately(self, manager: OrderManager) -> None:
        """Multiple submit calls track separate orders."""
        req1 = OrderRequest(instrument_id="AAPL", side="buy", quantity=Decimal("100"))
        req2 = OrderRequest(instrument_id="MSFT", side="sell", quantity=Decimal("50"))
        r1 = await manager.submit(req1)
        r2 = await manager.submit(req2)

        assert r1.order_id != r2.order_id
        assert len(manager._orders) == 2

    @pytest.mark.asyncio
    async def test_on_fill_accumulative(
        self, manager: OrderManager, buy_request: OrderRequest
    ) -> None:
        """Multiple fills on the same order accumulate correctly."""
        result = await manager.submit(buy_request)
        fill1 = FillReport(
            order_id=result.order_id,
            broker_order_id="broker-abc-123",
            fill_id="fill-001",
            quantity=Decimal("30"),
            price=Decimal("150.00"),
        )
        fill2 = FillReport(
            order_id=result.order_id,
            broker_order_id="broker-abc-123",
            fill_id="fill-002",
            quantity=Decimal("70"),
            price=Decimal("151.00"),
        )
        await manager.on_fill(fill1)
        await manager.on_fill(fill2)

        order = manager.get_order(result.order_id)
        assert order is not None
        assert order.filled_quantity == Decimal("100")
        assert order.status == OrderStatus.filled
        assert order.avg_fill_price == Decimal("151.00")  # last fill price
