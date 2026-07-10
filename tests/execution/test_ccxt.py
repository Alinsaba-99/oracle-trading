"""Tests for the CCXTBroker."""

from __future__ import annotations

from typing import Any

import pytest

from execution.brokers.ccxt_broker import CCXTBroker
from execution.brokers.config import BrokerConfig

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def config() -> BrokerConfig:
    return BrokerConfig()


@pytest.fixture
def broker(config: BrokerConfig) -> CCXTBroker:
    return CCXTBroker(config)


@pytest.fixture
def mock_order() -> object:
    """Minimal duck-type order for submit_order."""

    class _Order:
        instrument_id: str = "BTC/USDT"
        side: str = "buy"
        order_type: str = "market"
        quantity: float = 0.01
        price: float | None = None

    return _Order()


# =========================================================================
# CCXTBroker — initialization
# =========================================================================


class TestInit:
    """Initialization with config defaults."""

    async def test_default_config(self) -> None:
        broker = CCXTBroker()
        assert broker._config.active_broker == "paper"
        assert broker._config.ccxt_exchange == "binance"
        assert broker._config.ccxt_sandbox is True

    async def test_not_connected_after_init(self) -> None:
        broker = CCXTBroker()
        assert await broker.is_connected() is False
        assert broker._exchange is None


# =========================================================================
# CCXTBroker — connect
# =========================================================================


class TestConnect:
    """Connect lifecycle."""

    async def test_connect_calls_load_markets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        loaded = False

        class FakeExchange:
            async def load_markets(self) -> None:
                nonlocal loaded
                loaded = True

            async def close(self) -> None: ...

        fake_exchange = FakeExchange()

        def fake_binance(config: Any) -> FakeExchange:
            _ = config
            return fake_exchange

        monkeypatch.setattr("ccxt.async_support.binance", fake_binance)

        broker = CCXTBroker()
        await broker.connect()

        assert loaded is True
        assert await broker.is_connected() is True


# =========================================================================
# CCXTBroker — submit_order
# =========================================================================


class TestSubmitOrder:
    """Order submission."""

    async def test_submit_market_order(self, mock_order: object) -> None:
        created: dict[str, Any] = {}

        class FakeExchange:
            async def create_order(
                self, symbol: str, type: str, side: str, amount: float, price: float | None = None
            ) -> dict[str, Any]:
                created.update(
                    {"symbol": symbol, "type": type, "side": side, "amount": amount, "price": price}
                )
                return {"id": "ccxt12345"}

            async def close(self) -> None: ...

        broker = CCXTBroker()
        broker._exchange = FakeExchange()

        result = await broker.submit_order(mock_order)

        assert result == "ccxt12345"
        assert created["symbol"] == "BTC/USDT"
        assert created["side"] == "buy"
        assert created["type"] == "market"

    async def test_submit_limit_order(self) -> None:
        class _Order:
            instrument_id: str = "ETH/USDT"
            side: str = "sell"
            order_type: str = "limit"
            quantity: float = 1.0
            price: float = 2500.0

        created: dict[str, Any] = {}

        class FakeExchange:
            async def create_order(
                self, symbol: str, type: str, side: str, amount: float, price: float | None = None
            ) -> dict[str, Any]:
                created.update(
                    {"symbol": symbol, "type": type, "side": side, "amount": amount, "price": price}
                )
                return {"id": "ccxt67890"}

            async def close(self) -> None: ...

        broker = CCXTBroker()
        broker._exchange = FakeExchange()

        result = await broker.submit_order(_Order())

        assert result == "ccxt67890"
        assert created["type"] == "limit"
        assert created["price"] == 2500.0


# =========================================================================
# CCXTBroker — cancel_order
# =========================================================================


class TestCancelOrder:
    """Order cancellation."""

    async def test_cancel_calls_cancel_order(self) -> None:
        cancelled: list[str] = []

        class FakeExchange:
            async def cancel_order(self, order_id: str) -> dict[str, Any]:
                cancelled.append(order_id)
                return {}

            async def close(self) -> None: ...

        broker = CCXTBroker()
        broker._exchange = FakeExchange()

        result = await broker.cancel_order("ccxt12345")

        assert result is True
        assert cancelled == ["ccxt12345"]

    async def test_cancel_returns_false_on_exception(self) -> None:
        class FakeExchange:
            async def cancel_order(self, order_id: str) -> Any:
                raise ValueError("network error")

            async def close(self) -> None: ...

        broker = CCXTBroker()
        broker._exchange = FakeExchange()

        result = await broker.cancel_order("ccxt12345")
        assert result is False


# =========================================================================
# CCXTBroker — order_status
# =========================================================================


class TestOrderStatus:
    """Order status queries."""

    async def test_fetch_order_returns_status(self) -> None:
        class FakeExchange:
            async def fetch_order(self, order_id: str) -> dict[str, Any]:
                return {"id": order_id, "status": "closed"}

            async def close(self) -> None: ...

        broker = CCXTBroker()
        broker._exchange = FakeExchange()

        status = await broker.order_status("ccxt12345")
        assert status == "closed"

    async def test_fetch_order_returns_unknown_on_exception(self) -> None:
        class FakeExchange:
            async def fetch_order(self, order_id: str) -> Any:
                raise ValueError("not found")

            async def close(self) -> None: ...

        broker = CCXTBroker()
        broker._exchange = FakeExchange()

        status = await broker.order_status("ccxt12345")
        assert status == "unknown"


# =========================================================================
# CCXTBroker — disconnect
# =========================================================================


class TestDisconnect:
    """Disconnect lifecycle."""

    async def test_disconnect_calls_close(self, monkeypatch: pytest.MonkeyPatch) -> None:
        closed = False

        class FakeExchange:
            async def load_markets(self) -> None: ...

            async def close(self) -> None:
                nonlocal closed
                closed = True

        fake_exchange = FakeExchange()

        def fake_binance(config: Any) -> FakeExchange:
            _ = config
            return fake_exchange

        monkeypatch.setattr("ccxt.async_support.binance", fake_binance)

        broker = CCXTBroker()
        await broker.connect()
        assert closed is False  # not closed yet

        await broker.disconnect()
        assert closed is True
        assert await broker.is_connected() is False
