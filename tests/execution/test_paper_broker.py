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

    async def test_cancel_returns_true_for_resting_limit(self, broker: PaperBroker) -> None:
        """A resting limit order (not yet marketable) can be cancelled."""
        await broker.on_price_update(Decimal("100"))

        class _Limit:
            order_id = "lim-1"
            instrument_id = "AAPL"
            side = "buy"
            quantity = Decimal("10")
            price = Decimal("90")  # below market → rests
            order_type = "limit"

        broker_id = await broker.submit_order(_Limit())
        assert await broker.order_status(broker_id) == "submitted"
        result = await broker.cancel_order(broker_id)
        assert result is True

    async def test_cancel_returns_false_for_filled_market(
        self, broker: PaperBroker, mock_order: object
    ) -> None:
        """Market orders fill immediately — cancel returns False."""
        broker_id = await broker.submit_order(mock_order)
        assert await broker.order_status(broker_id) == "filled"
        result = await broker.cancel_order(broker_id)
        assert result is False

    async def test_cancel_returns_false_for_unknown(self, broker: PaperBroker) -> None:
        result = await broker.cancel_order("nonexistent")
        assert result is False

    async def test_cancel_changes_status(self, broker: PaperBroker) -> None:
        """After cancel the resting order reports ``cancelled``."""
        await broker.on_price_update(Decimal("100"))

        class _Limit:
            order_id = "lim-2"
            instrument_id = "AAPL"
            side = "buy"
            quantity = Decimal("10")
            price = Decimal("90")
            order_type = "limit"

        broker_id = await broker.submit_order(_Limit())
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

    async def test_amend_resting_limit(self, broker: PaperBroker) -> None:
        """Amend on a resting limit order succeeds and mutates price."""
        await broker.on_price_update(Decimal("100"))

        class _Limit:
            order_id = "lim-3"
            instrument_id = "AAPL"
            side = "buy"
            quantity = Decimal("10")
            price = Decimal("90")
            order_type = "limit"

        broker_id = await broker.submit_order(_Limit())
        result = await broker.amend_order(broker_id, price=Decimal("85"))
        assert result is True

    async def test_amend_filled_market_returns_false(
        self, broker: PaperBroker, mock_order: object
    ) -> None:
        """Amend on a filled market order returns False."""
        broker_id = await broker.submit_order(mock_order)
        result = await broker.amend_order(broker_id, price=Decimal("150"))
        assert result is False

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
        assert cfg.paper_spread_bps == 0
        assert cfg.paper_slippage_bps == 50
        assert cfg.paper_partial_fill_prob == 0.0
        assert cfg.paper_latency_ms == 0
        assert cfg.paper_commission_per_contract == 0.0


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


# =========================================================================
# M32-010 — Stop & bracket orders
# =========================================================================


class _LimitOrder:
    """Reusable duck-typed limit order."""

    def __init__(
        self,
        instrument_id: str = "ES",
        side: str = "buy",
        quantity: Decimal = Decimal("1"),
        price: Decimal = Decimal("100"),
    ) -> None:
        self.order_id = None
        self.instrument_id = instrument_id
        self.side = side
        self.quantity = quantity
        self.price = price
        self.order_type = "limit"


class _StopOrder:
    """Reusable duck-typed stop order."""

    def __init__(
        self,
        instrument_id: str = "ES",
        side: str = "sell",
        quantity: Decimal = Decimal("1"),
        stop_price: Decimal = Decimal("95"),
    ) -> None:
        self.order_id = None
        self.instrument_id = instrument_id
        self.side = side
        self.quantity = quantity
        self.price = None
        self.order_type = "stop"
        self.stop_price = stop_price


class _BracketEntry:
    """Market entry with attached stop + take-profit."""

    def __init__(
        self,
        instrument_id: str = "ES",
        side: str = "buy",
        quantity: Decimal = Decimal("1"),
        stop_price: Decimal = Decimal("95"),
        take_profit_price: Decimal = Decimal("110"),
    ) -> None:
        self.order_id = None
        self.instrument_id = instrument_id
        self.side = side
        self.quantity = quantity
        self.price = None
        self.order_type = "market"
        self.stop_price = stop_price
        self.take_profit_price = take_profit_price


class TestStopOrders:
    """M32-010: stop order semantics."""

    async def test_stop_rests_until_trigger(self, broker: PaperBroker) -> None:
        """A sell-stop at 95 rests while price stays above, then triggers."""
        await broker.on_price_update(Decimal("100"))
        stop_id = await broker.submit_order(_StopOrder(stop_price=Decimal("95")))
        assert await broker.order_status(stop_id) == "submitted"

        # Tick above the stop → still resting.
        fills = await broker.on_price_update(Decimal("98"))
        assert fills == []
        assert await broker.order_status(stop_id) == "submitted"

        # Tick through the stop → fills.
        fills = await broker.on_price_update(Decimal("94"))
        assert len(fills) == 1
        assert fills[0].broker_order_id == stop_id
        assert await broker.order_status(stop_id) == "filled"

    async def test_stop_immediate_if_already_through(self, broker: PaperBroker) -> None:
        """A sell-stop submitted while price is already below triggers immediately."""
        await broker.on_price_update(Decimal("94"))
        stop_id = await broker.submit_order(_StopOrder(stop_price=Decimal("95")))
        assert await broker.order_status(stop_id) == "filled"

    async def test_buy_stop_triggers_on_rally(self, broker: PaperBroker) -> None:
        """A buy-stop fires when price rallies through."""
        await broker.on_price_update(Decimal("100"))
        stop_id = await broker.submit_order(_StopOrder(side="buy", stop_price=Decimal("105")))
        assert await broker.order_status(stop_id) == "submitted"
        fills = await broker.on_price_update(Decimal("106"))
        assert len(fills) == 1
        assert await broker.order_status(stop_id) == "filled"


class TestLimitOrders:
    """M32-010: limit order semantics."""

    async def test_buy_limit_rests_above_limit(self, broker: PaperBroker) -> None:
        await broker.on_price_update(Decimal("100"))
        limit_id = await broker.submit_order(_LimitOrder(price=Decimal("95")))
        assert await broker.order_status(limit_id) == "submitted"

    async def test_buy_limit_fills_at_limit(self, broker: PaperBroker) -> None:
        await broker.on_price_update(Decimal("100"))
        limit_id = await broker.submit_order(_LimitOrder(price=Decimal("95")))
        fills = await broker.on_price_update(Decimal("95"))
        assert len(fills) == 1
        assert fills[0].broker_order_id == limit_id
        assert await broker.order_status(limit_id) == "filled"

    async def test_sell_limit_fills_on_rally(self, broker: PaperBroker) -> None:
        await broker.on_price_update(Decimal("100"))
        limit_id = await broker.submit_order(_LimitOrder(side="sell", price=Decimal("105")))
        fills = await broker.on_price_update(Decimal("106"))
        assert len(fills) == 1
        assert await broker.order_status(limit_id) == "filled"


class TestBracketOrders:
    """M32-010: bracket entry (stop + take-profit) semantics."""

    async def test_bracket_children_created_on_entry_fill(self, broker: PaperBroker) -> None:
        """Market entry fills → two children (stop + tp) rest as submitted."""
        await broker.on_price_update(Decimal("100"))
        entry_id = await broker.submit_order(_BracketEntry())
        assert await broker.order_status(entry_id) == "filled"

        children = broker._bracket_children.get(entry_id, {})
        assert "stop" in children
        assert "tp" in children
        assert await broker.order_status(children["stop"]) == "submitted"
        assert await broker.order_status(children["tp"]) == "submitted"

    async def test_bracket_stop_triggers_and_cancels_tp(self, broker: PaperBroker) -> None:
        """When the stop triggers, the take-profit is cancelled (OCO)."""
        await broker.on_price_update(Decimal("100"))
        entry_id = await broker.submit_order(
            _BracketEntry(stop_price=Decimal("95"), take_profit_price=Decimal("110"))
        )
        children = broker._bracket_children[entry_id]

        fills = await broker.on_price_update(Decimal("94"))
        assert len(fills) == 1
        assert fills[0].broker_order_id == children["stop"]
        assert await broker.order_status(children["stop"]) == "filled"
        assert await broker.order_status(children["tp"]) == "cancelled"

    async def test_bracket_tp_triggers_and_cancels_stop(self, broker: PaperBroker) -> None:
        """When the take-profit triggers, the stop is cancelled (OCO)."""
        await broker.on_price_update(Decimal("100"))
        entry_id = await broker.submit_order(
            _BracketEntry(stop_price=Decimal("95"), take_profit_price=Decimal("110"))
        )
        children = broker._bracket_children[entry_id]

        fills = await broker.on_price_update(Decimal("111"))
        assert len(fills) == 1
        assert fills[0].broker_order_id == children["tp"]
        assert await broker.order_status(children["tp"]) == "filled"
        assert await broker.order_status(children["stop"]) == "cancelled"

    async def test_bracket_position_closed_after_stop(self, broker: PaperBroker) -> None:
        """After the stop fires the net position returns to zero."""
        await broker.on_price_update(Decimal("100"))
        await broker.submit_order(
            _BracketEntry(stop_price=Decimal("95"), take_profit_price=Decimal("110"))
        )
        positions = await broker.positions()
        assert len(positions) == 1
        assert positions[0].quantity == Decimal("1")

        await broker.on_price_update(Decimal("94"))
        positions = await broker.positions()
        assert positions == []


# =========================================================================
# M32-011 — Session flatten
# =========================================================================


class TestSessionFlatten:
    """M32-011: cancel pendings + close all positions at market."""

    async def test_flatten_empty_broker_is_noop(self, broker: PaperBroker) -> None:
        result = await broker.flatten_all()
        assert result["success"] is True
        assert result["open_orders_cancelled"] == 0
        assert result["positions_flattened"] == 0
        assert result["errors"] == []

    async def test_flatten_cancels_resting_orders(self, broker: PaperBroker) -> None:
        """Resting limit/stop orders are cancelled; no fills generated."""
        await broker.on_price_update(Decimal("100"))
        await broker.submit_order(_LimitOrder(price=Decimal("95")))
        await broker.submit_order(_StopOrder(stop_price=Decimal("90")))
        open_before = await broker.open_orders()
        assert len(open_before) == 2

        result = await broker.flatten_all()
        assert result["open_orders_cancelled"] == 2
        assert result["positions_flattened"] == 0
        assert await broker.open_orders() == []

    async def test_flatten_closes_long_position(self, broker: PaperBroker) -> None:
        """A long position is closed via a market sell."""
        await broker.on_price_update(Decimal("100"))

        class _Entry:
            order_id = None
            instrument_id = "ES"
            side = "buy"
            quantity = Decimal("2")
            price = None
            order_type = "market"

        await broker.submit_order(_Entry())
        assert len(await broker.positions()) == 1

        result = await broker.flatten_all()
        assert result["success"] is True
        assert result["positions_flattened"] == 1
        assert await broker.positions() == []

    async def test_flatten_closes_short_position(self, broker: PaperBroker) -> None:
        """A short position is closed via a market buy."""
        await broker.on_price_update(Decimal("100"))

        class _Entry:
            order_id = None
            instrument_id = "ES"
            side = "sell"
            quantity = Decimal("1")
            price = None
            order_type = "market"

        await broker.submit_order(_Entry())
        positions = await broker.positions()
        assert len(positions) == 1
        assert positions[0].quantity == Decimal("-1")

        result = await broker.flatten_all()
        assert result["positions_flattened"] == 1
        assert await broker.positions() == []

    async def test_flatten_cancels_bracket_children_too(self, broker: PaperBroker) -> None:
        """Bracket children (resting stop/tp) are cancelled, position closed."""
        await broker.on_price_update(Decimal("100"))
        entry_id = await broker.submit_order(
            _BracketEntry(stop_price=Decimal("95"), take_profit_price=Decimal("110"))
        )
        children = broker._bracket_children[entry_id]
        assert await broker.order_status(children["stop"]) == "submitted"
        assert await broker.order_status(children["tp"]) == "submitted"

        result = await broker.flatten_all()
        assert result["open_orders_cancelled"] == 2  # both bracket legs
        assert result["positions_flattened"] == 1
        assert await broker.positions() == []
        assert await broker.order_status(children["stop"]) == "cancelled"
        assert await broker.order_status(children["tp"]) == "cancelled"

    async def test_flatten_multiple_instruments(self, broker: PaperBroker) -> None:
        """Two positions in different instruments both close."""
        await broker.on_price_update(Decimal("100"))

        class _ES:
            order_id = None
            instrument_id = "ES"
            side = "buy"
            quantity = Decimal("1")
            price = None
            order_type = "market"

        class _NQ:
            order_id = None
            instrument_id = "NQ"
            side = "buy"
            quantity = Decimal("3")
            price = None
            order_type = "market"

        await broker.submit_order(_ES())
        await broker.submit_order(_NQ())
        assert len(await broker.positions()) == 2

        result = await broker.flatten_all()
        assert result["positions_flattened"] == 2
        assert await broker.positions() == []


# =========================================================================
# M32-012 — Daily rollover
# =========================================================================


class TestDailyRollover:
    """M32-012: session-date advance + daily-counter reset."""

    async def test_rollover_sets_new_date(self, broker: PaperBroker) -> None:
        from datetime import date

        result = await broker.rollover(date(2026, 7, 21))
        assert result["new_date"] == "2026-07-21"
        assert result["previous_date"] is None
        state = await broker.daily_state()
        assert state["session_date"] == "2026-07-21"

    async def test_rollover_resets_counters(self, broker: PaperBroker) -> None:
        """Daily pnl and trade count are zeroed on rollover."""
        from datetime import date

        broker._daily_pnl = Decimal("-1500")
        broker._daily_trade_count = 7
        await broker.rollover(date(2026, 7, 21))
        state = await broker.daily_state()
        assert state["daily_pnl"] == 0.0
        assert state["daily_trade_count"] == 0

    async def test_rollover_the5ers_keeps_position(self, broker: PaperBroker) -> None:
        """The5ers-style: overnight positions carry; only counters reset."""
        from datetime import date

        await broker.on_price_update(Decimal("100"))

        class _Entry:
            order_id = None
            instrument_id = "ES"
            side = "buy"
            quantity = Decimal("1")
            price = None
            order_type = "market"

        await broker.submit_order(_Entry())
        assert len(await broker.positions()) == 1

        result = await broker.rollover(date(2026, 7, 21), auto_flatten=False)
        assert result["auto_flatten"] is False
        assert result["flatten"]["positions_flattened"] == 0
        assert len(await broker.positions()) == 1

    async def test_rollover_lucid_flattens_position(self, broker: PaperBroker) -> None:
        """Lucid-style (intraday-only): rollover auto-flattens at EOD."""
        from datetime import date

        await broker.on_price_update(Decimal("100"))

        class _Entry:
            order_id = None
            instrument_id = "ES"
            side = "buy"
            quantity = Decimal("1")
            price = None
            order_type = "market"

        await broker.submit_order(_Entry())
        assert len(await broker.positions()) == 1

        result = await broker.rollover(date(2026, 7, 21), auto_flatten=True)
        assert result["auto_flatten"] is True
        assert result["flatten"]["positions_flattened"] == 1
        assert await broker.positions() == []

    async def test_rollover_lucid_cancels_pendings(self, broker: PaperBroker) -> None:
        """Lucid rollover also cancels resting stop/limit orders."""
        from datetime import date

        await broker.on_price_update(Decimal("100"))
        await broker.submit_order(_LimitOrder(price=Decimal("95")))
        await broker.submit_order(_StopOrder(stop_price=Decimal("90")))
        assert len(await broker.open_orders()) == 2

        result = await broker.rollover(date(2026, 7, 21), auto_flatten=True)
        assert result["flatten"]["open_orders_cancelled"] == 2
        assert await broker.open_orders() == []


# =========================================================================
# M32-013 — Restart recovery (snapshot / restore)
# =========================================================================


class TestRestartRecovery:
    """M32-013: snapshot mid-session, kill, restore, verify state matches."""

    async def test_snapshot_empty_broker(self, broker: PaperBroker) -> None:
        snap = broker.snapshot()
        assert snap["order_counter"] == 0
        assert snap["orders"] == []
        assert snap["fills"] == []

    async def test_restore_empty_snapshot_roundtrip(self, broker: PaperBroker) -> None:
        snap = broker.snapshot()
        restored = PaperBroker.restore(snap)
        assert await restored.positions() == []
        assert await restored.open_orders() == []

    async def test_restore_preserves_positions(self, broker: PaperBroker) -> None:
        """Open positions survive the kill+restore cycle."""
        await broker.on_price_update(Decimal("100"))

        class _Entry:
            order_id = None
            instrument_id = "ES"
            side = "buy"
            quantity = Decimal("2")
            price = None
            order_type = "market"

        await broker.submit_order(_Entry())
        snap = broker.snapshot()

        restored = PaperBroker.restore(snap)
        positions = await restored.positions()
        assert len(positions) == 1
        assert positions[0].instrument_id == "ES"
        assert positions[0].quantity == Decimal("2")

    async def test_restore_preserves_resting_orders(self, broker: PaperBroker) -> None:
        """Resting limit/stop orders remain resting after restore."""
        await broker.on_price_update(Decimal("100"))
        limit_id = await broker.submit_order(_LimitOrder(price=Decimal("95")))
        stop_id = await broker.submit_order(_StopOrder(stop_price=Decimal("90")))

        snap = broker.snapshot()
        restored = PaperBroker.restore(snap)

        assert await restored.order_status(limit_id) == "submitted"
        assert await restored.order_status(stop_id) == "submitted"
        open_orders = await restored.open_orders()
        assert len(open_orders) == 2

    async def test_restore_preserves_bracket_linkage(self, broker: PaperBroker) -> None:
        """Bracket parent→children mapping survives; OCO still fires."""
        await broker.on_price_update(Decimal("100"))
        entry_id = await broker.submit_order(
            _BracketEntry(stop_price=Decimal("95"), take_profit_price=Decimal("110"))
        )
        children_before = broker._bracket_children[entry_id]

        snap = broker.snapshot()
        restored = PaperBroker.restore(snap)

        children_after = restored._bracket_children[entry_id]
        assert children_after == children_before

        # Drive restored broker through stop → OCO still works.
        fills = await restored.on_price_update(Decimal("94"))
        assert len(fills) == 1
        assert fills[0].broker_order_id == children_after["stop"]
        assert await restored.order_status(children_after["tp"]) == "cancelled"

    async def test_restore_continues_order_counter(self, broker: PaperBroker) -> None:
        """Order IDs don't collide after restore (counter is preserved)."""
        await broker.on_price_update(Decimal("100"))
        await broker.submit_order(_LimitOrder(price=Decimal("95")))
        counter_before = broker._order_counter

        snap = broker.snapshot()
        restored = PaperBroker.restore(snap)
        assert restored._order_counter == counter_before

        new_id = await restored.submit_order(_LimitOrder(price=Decimal("96")))
        assert int(new_id.split("_")[1]) == counter_before + 1

    async def test_restore_preserves_daily_state(self, broker: PaperBroker) -> None:
        """Daily session date/counters survive."""
        from datetime import date

        await broker.rollover(date(2026, 7, 20))
        broker._daily_pnl = Decimal("-250")
        broker._daily_trade_count = 3

        snap = broker.snapshot()
        restored = PaperBroker.restore(snap)
        state = await restored.daily_state()
        assert state["session_date"] == "2026-07-20"
        assert state["daily_pnl"] == -250.0
        assert state["daily_trade_count"] == 3

    async def test_restore_idempotent(self, broker: PaperBroker) -> None:
        """Restoring the same snapshot twice yields equivalent state."""
        await broker.on_price_update(Decimal("100"))
        await broker.submit_order(_LimitOrder(price=Decimal("95")))
        snap = broker.snapshot()

        r1 = PaperBroker.restore(snap)
        r2 = PaperBroker.restore(snap)
        assert (await r1.open_orders())[0].broker_order_id == (await r2.open_orders())[
            0
        ].broker_order_id


# =========================================================================
# M32-014 — Feed reconnect (disconnect → backfill → no duplicate orders)
# =========================================================================


class _ScriptedFeed:
    """Test feed that can disconnect, drop ticks, and reconnect with backfill.

    Mimics the PolygonWebSocketFeed semantics: ticks stream via an async
    iterator; a ``disconnect()`` call drops the stream; ``reconnect()``
    resumes from a backfill of missed ticks.
    """

    def __init__(self, prices: list[Decimal]) -> None:
        self._prices = list(prices)
        self._cursor = 0
        self._connected = True
        self.dropped: list[Decimal] = []

    def disconnect(self) -> None:
        self._connected = False

    def reconnect(self) -> list[Decimal]:
        """Reconnect and return the backfill of ticks dropped while down."""
        self._connected = True
        backfill = list(self.dropped)
        self.dropped.clear()
        return backfill

    def tick(self) -> Decimal | None:
        """Advance one tick. If disconnected, drop it (recorded)."""
        if self._cursor >= len(self._prices):
            return None
        price = self._prices[self._cursor]
        self._cursor += 1
        if not self._connected:
            self.dropped.append(price)
            return None
        return price


class TestFeedReconnect:
    """M32-014: reconnect after a drop must not duplicate orders."""

    async def test_disconnect_drops_ticks(self) -> None:
        """Feed records dropped ticks for later backfill."""
        feed = _ScriptedFeed([Decimal("100"), Decimal("101"), Decimal("102")])
        assert feed.tick() == Decimal("100")
        feed.disconnect()
        assert feed.tick() is None
        assert feed.tick() is None
        assert feed.dropped == [Decimal("101"), Decimal("102")]

    async def test_reconnect_backfills_dropped(self) -> None:
        feed = _ScriptedFeed([Decimal("100"), Decimal("101"), Decimal("102")])
        feed.tick()
        feed.disconnect()
        feed.tick()
        feed.tick()
        backfill = feed.reconnect()
        assert backfill == [Decimal("101"), Decimal("102")]
        assert feed.dropped == []

    async def test_backfill_triggers_resting_stop_once(self, broker: PaperBroker) -> None:
        """After backfill, a stop that *would* have triggered fires exactly
        once — not once per backfilled tick.
        """
        await broker.on_price_update(Decimal("100"))
        stop_id = await broker.submit_order(_StopOrder(stop_price=Decimal("95")))

        # Simulate feed disconnect during which price dropped through stop.
        feed = _ScriptedFeed([Decimal("98"), Decimal("94"), Decimal("93")])
        feed.tick()  # consumed, price 98 (no trigger)
        feed.disconnect()
        feed.tick()  # dropped: 94 (would have triggered)
        feed.tick()  # dropped: 93
        backfill = feed.reconnect()

        # Apply backfill in order. Stop triggers on 94; 93 must not double-fire.
        all_fills = []
        for price in backfill:
            all_fills.extend(await broker.on_price_update(price))
        assert len(all_fills) == 1
        assert all_fills[0].broker_order_id == stop_id
        assert await broker.order_status(stop_id) == "filled"

    async def test_reconnect_does_not_duplicate_orders(self, broker: PaperBroker) -> None:
        """A strategy that reacts to reconnect backfill must not submit
        duplicate orders (idempotent submitter pattern).
        """
        await broker.on_price_update(Decimal("100"))

        submitted_signals: set[str] = set()

        async def maybe_submit(signal_id: str, side: str) -> str | None:
            """Idempotent: same signal_id never re-submits."""
            if signal_id in submitted_signals:
                return None
            submitted_signals.add(signal_id)

            class _Entry:
                order_id = None
                instrument_id = "ES"
                quantity = Decimal("1")
                price = None
                order_type = "market"

            # bind loop-local
            _Entry.side = side  # type: ignore[attr-defined]
            return await broker.submit_order(_Entry())

        # First pass — submit.
        oid1 = await maybe_submit("sig_42", "buy")
        assert oid1 is not None

        # Feed drops + reconnects; strategy replays the same signal.
        feed = _ScriptedFeed([Decimal("101"), Decimal("102")])
        feed.disconnect()
        feed.tick()
        backfill = feed.reconnect()
        assert backfill == [Decimal("101")]

        # Same signal → no duplicate.
        oid2 = await maybe_submit("sig_42", "buy")
        assert oid2 is None

        # Only one position was opened.
        positions = await broker.positions()
        assert len(positions) == 1
        assert positions[0].quantity == Decimal("1")

    async def test_broker_state_unchanged_by_disconnect(self, broker: PaperBroker) -> None:
        """Disconnect by itself doesn't mutate broker state; only backfill does."""
        await broker.on_price_update(Decimal("100"))

        class _Entry:
            order_id = None
            instrument_id = "ES"
            side = "buy"
            quantity = Decimal("1")
            price = None
            order_type = "market"

        await broker.submit_order(_Entry())
        positions_before = await broker.positions()
        open_before = await broker.open_orders()

        feed = _ScriptedFeed([Decimal("101")])
        feed.disconnect()
        feed.tick()  # drop, no price update applied
        feed.reconnect()

        # No broker.on_price_update called → state identical.
        assert await broker.positions() == positions_before
        assert await broker.open_orders() == open_before
