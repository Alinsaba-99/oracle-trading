"""Tests for the IBKRBroker."""

from __future__ import annotations

from typing import Any

import pytest

from execution.brokers.config import BrokerConfig
from execution.brokers.ibkr import IBKRBroker

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def config() -> BrokerConfig:
    return BrokerConfig()


@pytest.fixture
def broker(config: BrokerConfig) -> IBKRBroker:
    return IBKRBroker(config)


@pytest.fixture
def mock_order() -> object:
    """Minimal duck-type order for submit_order."""

    class _Order:
        instrument_id: str = "AAPL"
        side: str = "buy"
        order_type: str = "market"
        quantity: float = 100.0
        price: float | None = None

    return _Order()


# =========================================================================
# IBKRBroker — initialization
# =========================================================================


class TestInit:
    """Initialization with config defaults."""

    async def test_default_config(self) -> None:
        broker = IBKRBroker()
        assert broker._config.active_broker == "paper"
        assert broker._config.ibkr_host == "127.0.0.1"
        assert broker._config.ibkr_port == 7497
        assert broker._config.ibkr_client_id == 1

    async def test_not_connected_after_init(self) -> None:
        broker = IBKRBroker()
        assert await broker.is_connected() is False
        assert broker._ib is None


# =========================================================================
# IBKRBroker — connect
# =========================================================================


class TestConnect:
    """Connect lifecycle."""

    async def test_connect_calls_ib_with_correct_params(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        connect_args: dict[str, Any] = {}

        class FakeIB:
            def connect(  # type: ignore[unused-ignore,misc]
                self, host: str, port: int, clientId: int
            ) -> None:
                connect_args["host"] = host
                connect_args["port"] = port
                connect_args["clientId"] = clientId

            def disconnect(self) -> None: ...

        monkeypatch.setattr("ib_insync.IB", lambda: FakeIB())

        broker = IBKRBroker()
        await broker.connect()

        assert connect_args["host"] == "127.0.0.1"
        assert connect_args["port"] == 7497
        assert connect_args["clientId"] == 1
        assert await broker.is_connected() is True


# =========================================================================
# IBKRBroker — submit_order
# =========================================================================


class TestSubmitOrder:
    """Order submission."""

    async def test_submit_market_order(self, mock_order: object) -> None:
        class FakeOrder:
            orderId: int = 42

        class FakeTrade:
            order: FakeOrder = FakeOrder()

        placed: list[Any] = []

        class FakeIB:
            connected = True

            def Stock(self, symbol: str, exchange: str, currency: str) -> Any:
                return {"symbol": symbol, "exchange": exchange, "currency": currency}

            def placeOrder(self, contract: Any, order: Any) -> FakeTrade:
                placed.append((contract, order))
                return FakeTrade()

            def disconnect(self) -> None: ...

        broker = IBKRBroker()
        broker._ib = FakeIB()
        broker._connected = True

        result = await broker.submit_order(mock_order)

        assert result == "42"
        assert len(placed) == 1
        contract, order = placed[0]
        assert contract["symbol"] == "AAPL"
        assert order.action == "BUY"

    async def test_submit_limit_order(self) -> None:
        class _Order:
            instrument_id: str = "MSFT"
            side: str = "sell"
            order_type: str = "limit"
            quantity: float = 50.0
            price: float = 300.0

        class FakeOrder:
            orderId: int = 99

        class FakeTrade:
            order: FakeOrder = FakeOrder()

        placed: list[Any] = []

        class FakeIB:
            def Stock(self, symbol: str, exchange: str, currency: str) -> Any:
                return {"symbol": symbol, "exchange": exchange, "currency": currency}

            def placeOrder(self, contract: Any, order: Any) -> FakeTrade:
                placed.append((contract, order))
                return FakeTrade()

            def disconnect(self) -> None: ...

        broker = IBKRBroker()
        broker._ib = FakeIB()
        broker._connected = True

        result = await broker.submit_order(_Order())

        assert result == "99"
        assert len(placed) == 1
        _, order = placed[0]
        assert order.action == "SELL"


# =========================================================================
# IBKRBroker — cancel_order
# =========================================================================


class TestCancelOrder:
    """Order cancellation."""

    async def test_cancel_calls_cancel_order_with_correct_id(self) -> None:
        cancelled_ids: list[int] = []

        class FakeIB:
            def cancelOrder(self, order_id: int) -> None:
                cancelled_ids.append(order_id)

            def disconnect(self) -> None: ...

        broker = IBKRBroker()
        broker._ib = FakeIB()
        broker._connected = True

        result = await broker.cancel_order("42")

        assert result is True
        assert cancelled_ids == [42]

    async def test_cancel_returns_false_when_not_connected(self) -> None:
        broker = IBKRBroker()
        result = await broker.cancel_order("42")
        assert result is False


# =========================================================================
# IBKRBroker — order_status
# =========================================================================


class TestOrderStatus:
    """Order status queries."""

    async def test_order_status_returns_status_from_trades(self) -> None:
        class FakeOrderStatus:
            status: str = "Filled"

        class FakeTrade:
            order: Any
            orderStatus: FakeOrderStatus = FakeOrderStatus()

            def __init__(self) -> None:
                self.order = type("o", (), {"orderId": 42})()

        class FakeIB:
            def trades(self) -> list[FakeTrade]:
                return [FakeTrade()]

            def disconnect(self) -> None: ...

        broker = IBKRBroker()
        broker._ib = FakeIB()

        status = await broker.order_status("42")
        assert status == "Filled"

    async def test_order_status_unknown_when_not_found(self) -> None:
        class FakeIB:
            def trades(self) -> list[Any]:
                return []

            def disconnect(self) -> None: ...

        broker = IBKRBroker()
        broker._ib = FakeIB()

        status = await broker.order_status("999")
        assert status == "unknown"

    async def test_order_status_unknown_when_not_connected(self) -> None:
        broker = IBKRBroker()
        status = await broker.order_status("42")
        assert status == "unknown"


# =========================================================================
# IBKRBroker — is_connected
# =========================================================================


class TestIsConnected:
    """Connection state."""

    async def test_returns_false_after_init(self) -> None:
        broker = IBKRBroker()
        assert await broker.is_connected() is False

    async def test_returns_true_after_connect(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeIB:
            def connect(  # type: ignore[unused-ignore,misc]
                self, host: str, port: int, clientId: int
            ) -> None: ...

            def disconnect(self) -> None: ...

        monkeypatch.setattr("ib_insync.IB", lambda: FakeIB())

        broker = IBKRBroker()
        await broker.connect()
        assert await broker.is_connected() is True
