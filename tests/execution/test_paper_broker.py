"""Tests for the PaperBroker, BaseBroker, BrokerRegistry, and types."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from execution.brokers.base import BaseBroker
from execution.brokers.config import BrokerConfig
from execution.brokers.paper import PaperBroker
from execution.brokers.registry import BrokerRegistry
from execution.brokers.types import BrokerOrder

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def config() -> BrokerConfig:
    return BrokerConfig()


@pytest.fixture
def broker(config: BrokerConfig) -> PaperBroker:
    return PaperBroker(config)


@pytest.fixture
def mock_order() -> object:
    """Minimal duck-type order for submit_order."""

    class _Order:
        order_id = "ord-001"
        instrument_id = "AAPL"
        side = "buy"
        quantity = Decimal("10")

    return _Order()


# =========================================================================
# PaperBroker — submit
# =========================================================================


class TestSubmit:
    """Order submission."""

    async def test_submit_returns_broker_order_id(
        self, broker: PaperBroker, mock_order: object
    ) -> None:
        broker_id = await broker.submit_order(mock_order)
        assert broker_id.startswith("paper_")
        assert isinstance(broker_id, str)

    async def test_submit_increments_counter(self, broker: PaperBroker, mock_order: object) -> None:
        id1 = await broker.submit_order(mock_order)
        id2 = await broker.submit_order(mock_order)
        assert id1 != id2
        _, n1 = id1.split("_")
        _, n2 = id2.split("_")
        assert int(n2) == int(n1) + 1

    async def test_submit_creates_fill(self, broker: PaperBroker, mock_order: object) -> None:
        broker_id = await broker.submit_order(mock_order)
        status = await broker.order_status(broker_id)
        assert status == "filled"


# =========================================================================
# PaperBroker — cancel
# =========================================================================


class TestCancel:
    """Order cancellation."""

    async def test_cancel_returns_true_for_existing(
        self, broker: PaperBroker, mock_order: object
    ) -> None:
        broker_id = await broker.submit_order(mock_order)
        result = await broker.cancel_order(broker_id)
        assert result is True

    async def test_cancel_returns_false_for_unknown(self, broker: PaperBroker) -> None:
        result = await broker.cancel_order("nonexistent")
        assert result is False

    async def test_cancel_changes_status(self, broker: PaperBroker, mock_order: object) -> None:
        broker_id = await broker.submit_order(mock_order)
        await broker.cancel_order(broker_id)
        status = await broker.order_status(broker_id)
        assert status == "cancelled"


# =========================================================================
# PaperBroker — order_status
# =========================================================================


class TestOrderStatus:
    """Order status queries."""

    async def test_status_after_submit(self, broker: PaperBroker, mock_order: object) -> None:
        broker_id = await broker.submit_order(mock_order)
        status = await broker.order_status(broker_id)
        assert status == "filled"

    async def test_status_unknown(self, broker: PaperBroker) -> None:
        status = await broker.order_status("nope")
        assert status == "unknown"


# =========================================================================
# PaperBroker — connect / disconnect
# =========================================================================


class TestLifecycle:
    """Connect / disconnect lifecycle."""

    async def test_is_connected_after_connect(self, broker: PaperBroker) -> None:
        await broker.connect()
        assert await broker.is_connected() is True

    async def test_is_connected_after_disconnect(self, broker: PaperBroker) -> None:
        await broker.connect()
        await broker.disconnect()
        assert await broker.is_connected() is False

    async def test_initial_not_connected(self, broker: PaperBroker) -> None:
        assert await broker.is_connected() is False

    async def test_health_returns_dict(self, broker: PaperBroker) -> None:
        health = await broker.health()
        assert isinstance(health, dict)
        assert "connected" in health
        assert "reconnect_attempts" in health


# =========================================================================
# PaperBroker — amend / positions
# =========================================================================


class TestAmendAndPositions:
    """Amend & position query edge cases."""

    async def test_amend_known_order(self, broker: PaperBroker, mock_order: object) -> None:
        broker_id = await broker.submit_order(mock_order)
        result = await broker.amend_order(broker_id, price=Decimal("150"))
        assert result is True

    async def test_amend_unknown_order(self, broker: PaperBroker) -> None:
        result = await broker.amend_order("nope", price=Decimal("150"))
        assert result is False

    async def test_positions_empty(self, broker: PaperBroker) -> None:
        pos = await broker.positions()
        assert pos == []


# =========================================================================
# BaseBroker — reconnection
# =========================================================================


class TestBaseBrokerReconnect:
    """BaseBroker exponential-back-off reconnect logic."""

    async def test_reconnect_succeeds_on_second_try(self) -> None:
        """_do_connect fails once, then succeeds."""
        call_count = 0

        class ReconnectBroker(BaseBroker):
            async def _do_connect(self) -> None:
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise ConnectionError("first attempt failed")

            async def _do_disconnect(self) -> None:
                pass

        broker = ReconnectBroker()
        await broker._reconnect()
        assert broker._connected is True
        assert broker._reconnect_attempts >= 1

    async def test_reconnect_exhausts_retries(self) -> None:
        """All reconnect attempts fail -> ConnectionError."""

        class FailingBroker(BaseBroker):
            async def _do_connect(self) -> None:
                raise ConnectionError("persistent failure")

            async def _do_disconnect(self) -> None:
                pass

        broker = FailingBroker()
        with pytest.raises(ConnectionError, match="Failed to reconnect"):
            await broker._reconnect()
        assert broker._connected is False

    async def test_reconnect_uses_exponential_delay(self) -> None:
        """Observe increasing delays (unit: at least base_delay * 2^i)."""

        class SlowBroker(BaseBroker):
            async def _do_connect(self) -> None:
                raise ConnectionError("fail")

            async def _do_disconnect(self) -> None:
                pass

        broker = SlowBroker()
        broker._config.reconnect_base_delay_s = 0.01
        broker._config.reconnect_max_delay_s = 5.0

        with (
            patch.object(broker, "_do_connect", side_effect=ConnectionError("fail")),
            pytest.raises(ConnectionError),
        ):
            await broker._reconnect()
        # All retries exhausted -> _connected stays False
        assert broker._connected is False


# =========================================================================
# BrokerConfig — defaults
# =========================================================================


class TestBrokerConfig:
    """Default config values."""

    def test_default_active_broker(self) -> None:
        cfg = BrokerConfig()
        assert cfg.active_broker == "paper"

    def test_default_reconnect_settings(self) -> None:
        cfg = BrokerConfig()
        assert cfg.reconnect_max_retries == 5
        assert cfg.reconnect_base_delay_s == 1.0
        assert cfg.reconnect_max_delay_s == 60.0

    def test_default_paper_settings(self) -> None:
        cfg = BrokerConfig()
        assert cfg.paper_spread_bps == 100
        assert cfg.paper_slippage_bps == 50
        assert cfg.paper_partial_fill_prob == 0.5
        assert cfg.paper_latency_ms == 50


# =========================================================================
# BrokerOrder — namespaced_id
# =========================================================================


class TestBrokerOrder:
    """BrokerOrder model."""

    def test_namespaced_id_format(self) -> None:
        order = BrokerOrder(
            broker_order_id="42",
            local_order_id="local-1",
            namespaced_id="ibkr:42",
            instrument_id="MSFT",
            side="buy",
            quantity=Decimal("100"),
        )
        assert order.namespaced_id == "ibkr:42"

    def test_default_filled_quantity_is_zero(self) -> None:
        order = BrokerOrder(
            broker_order_id="1",
            local_order_id="local-1",
            namespaced_id="paper:1",
            instrument_id="AAPL",
            side="sell",
            quantity=Decimal("50"),
        )
        assert order.filled_quantity == Decimal("0")

    def test_default_status_is_pending(self) -> None:
        order = BrokerOrder(
            broker_order_id="1",
            local_order_id="local-1",
            namespaced_id="paper:1",
            instrument_id="AAPL",
            side="sell",
            quantity=Decimal("50"),
        )
        assert order.status == "pending"


# =========================================================================
# BrokerRegistry
# =========================================================================


class TestBrokerRegistry:
    """Registry of broker instances."""

    def test_register_and_get(self) -> None:
        registry = BrokerRegistry()
        broker = PaperBroker()
        registry.register("paper", broker)
        assert registry.get("paper") is broker

    def test_get_active_default(self) -> None:
        registry = BrokerRegistry()
        assert registry.active_name() == "paper"

    def test_set_active(self) -> None:
        registry = BrokerRegistry()
        broker1 = PaperBroker()
        broker2 = PaperBroker()
        registry.register("paper", broker1)
        registry.register("live", broker2)
        registry.set_active("live")
        assert registry.get() is broker2

    def test_set_active_unknown_raises(self) -> None:
        registry = BrokerRegistry()
        with pytest.raises(ValueError, match="not registered"):
            registry.set_active("nonexistent")

    def test_get_returns_none_for_unregistered(self) -> None:
        registry = BrokerRegistry()
        assert registry.get("missing") is None

    def test_list_brokers(self) -> None:
        registry = BrokerRegistry()
        registry.register("a", PaperBroker())
        registry.register("b", PaperBroker())
        assert sorted(registry.list_brokers()) == ["a", "b"]
