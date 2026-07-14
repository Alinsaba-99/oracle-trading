"""MetaTrader 5 broker adapter — backend-agnostic, mock-testable.

The5ers and Lucid run on MetaTrader 5 (forex / metals / indices).  This
adapter conforms to :class:`BrokerProtocol` so the existing
``OrderManager`` can route orders to MT5 exactly as it does to the paper
or IBKR broker today.

Two Linux backends are supported behind a single :class:`MT5Client`
protocol:

* **MetaApi cloud** (``metaapi-cloud-sdk``) — native Linux Python, no
  Wine; recommended for this machine.
* **mt5linux + Wine** — runs the official ``MetaTrader5`` package under
  Wine via an RPyC bridge; no cloud cost, heavier setup.

Because neither backend runs in the Linux sandbox without an account,
this module ships a :class:`MockMT5Client` so the order/position/symbol
mapping is fully unit-tested today.  The real client is injected at
construction time — wiring it is a one-liner once credentials exist.

The adapter also exposes :meth:`MetaTraderBroker.account_snapshot`,
which returns the live ``(balance, equity)`` the
:class:`~policy.prop_firm.PropFirmRiskGovernor` needs (Fase 2 wiring).
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, Protocol

import structlog

from execution.brokers.base import BaseBroker
from execution.brokers.config import BrokerConfig
from execution.brokers.types import BrokerOrder, BrokerPosition

logger = structlog.get_logger("oracle.execution.mt5")

#: MT5 trade request actions.
TRADE_ACTION_DEAL = 1  # market / pending deal
TRADE_ACTION_PENDING = 5  # place pending order

#: MT5 order types (subset).
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3

#: MT5 result codes.
RETCODE_DONE = 10009


class SymbolMapper:
    """Map internal instrument ids to broker-specific MT5 symbols.

    Prop-firm brokers append suffixes to symbols (``EURUSD`` →
    ``EURUSD.r``, ``EURUSDx``, ``EURUSD.m``).  This centralises the
    mapping so strategies use canonical ids everywhere.
    """

    def __init__(self, suffix: str = "", explicit: dict[str, str] | None = None) -> None:
        self.suffix = suffix
        self.explicit = explicit or {}

    def to_broker(self, instrument_id: str) -> str:
        """Internal id -> broker symbol (e.g. EURUSD -> EURUSD.r)."""
        if instrument_id in self.explicit:
            return self.explicit[instrument_id]
        return f"{instrument_id}{self.suffix}" if self.suffix else instrument_id

    def from_broker(self, broker_symbol: str) -> str:
        """Broker symbol -> internal id (strip known suffixes)."""
        for internal, broker in self.explicit.items():
            if broker == broker_symbol:
                return internal
        if self.suffix and broker_symbol.endswith(self.suffix):
            return broker_symbol[: -len(self.suffix)]
        return broker_symbol


class MT5Client(Protocol):
    """Minimal MT5 API surface — common to MetaApi and mt5linux."""

    def initialize(
        self,
        path: str | None = None,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
    ) -> bool: ...

    def shutdown(self) -> None: ...

    def account_info(self) -> dict[str, Any]: ...

    def symbol_info(self, symbol: str) -> dict[str, Any]: ...

    def copy_rates_range(
        self, symbol: str, timeframe: str, date_from: Any, date_to: Any
    ) -> Any: ...

    def order_send(self, request: dict[str, Any]) -> dict[str, Any]: ...

    def positions_get(self, symbol: str | None = None) -> list[dict[str, Any]]: ...


class MockMT5Client:
    """Deterministic in-memory MT5 client for tests.

    Fills market orders at an injected last price, tracks positions and
    balance/equity, and serves historical bars from an injected table.
    """

    def __init__(
        self,
        balance: float = 100_000.0,
        prices: dict[str, float] | None = None,
        rates: dict[str, Any] | None = None,
    ) -> None:
        self.balance: float = balance
        self.equity: float = balance
        self._prices: dict[str, float] = prices or {}
        self._rates: dict[str, Any] = rates or {}
        self._positions: list[dict[str, Any]] = []
        self._next_order_id: int = 1000
        self._connected: bool = False
        self._magic_seen: set[int] = set()

    def initialize(self, **_: Any) -> bool:
        self._connected = True
        return True

    def shutdown(self) -> None:
        self._connected = False

    def account_info(self) -> dict[str, Any]:
        return {
            "balance": self.balance,
            "equity": self.equity,
            "margin": 0.0,
            "currency": "USD",
            "leverage": 30,
        }

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        return {"name": symbol, "digits": 5, "trade_contract_size": 100_000.0}

    def copy_rates_range(self, symbol: str, _timeframe: str, _date_from: Any, _date_to: Any) -> Any:
        return self._rates.get(symbol, [])

    def order_send(self, request: dict[str, Any]) -> dict[str, Any]:
        symbol = request["symbol"]
        order_type = request["type"]
        volume = float(request["volume"])
        price = float(request.get("price", self._prices.get(symbol, 0.0)))

        self._next_order_id += 1
        self._positions.append(
            {
                "ticket": self._next_order_id,
                "symbol": symbol,
                "type": order_type,
                "volume": volume,
                "price_open": price,
                "sl": request.get("sl", 0.0),
                "tp": request.get("tp", 0.0),
                "magic": request.get("magic", 0),
                "comment": request.get("comment", ""),
            }
        )
        self._magic_seen.add(int(request.get("magic", 0)))
        return {"retcode": RETCODE_DONE, "order": self._next_order_id, "deal": self._next_order_id}

    def positions_get(self, symbol: str | None = None) -> list[dict[str, Any]]:
        if symbol is None:
            return list(self._positions)
        return [p for p in self._positions if p["symbol"] == symbol]

    # -- test helpers -------------------------------------------------
    def set_price(self, symbol: str, price: float) -> None:
        """Inject a market price and recompute equity from open positions."""
        self._prices[symbol] = price
        unrealized = 0.0
        for p in self._positions:
            px = self._prices.get(p["symbol"], p["price_open"])
            direction = 1 if p["type"] in (ORDER_TYPE_BUY, ORDER_TYPE_BUY_LIMIT) else -1
            unrealized += direction * (px - p["price_open"]) * p["volume"] * 100_000.0
        self.equity = self.balance + unrealized


def _magic_for(strategy_id: str) -> int:
    """Deterministic magic number from a strategy id (MT5 int32 range)."""
    h = hashlib.md5(strategy_id.encode()).hexdigest()
    return int(h[:8], 16) % 2_000_000_000


class MetaTraderBroker(BaseBroker):
    """MT5 broker adapter (BrokerProtocol) over an injected :class:`MT5Client`."""

    def __init__(
        self,
        client: MT5Client,
        config: BrokerConfig | None = None,
        symbol_mapper: SymbolMapper | None = None,
        strategy_id: str = "oracle",
    ) -> None:
        super().__init__(config)
        self._client = client
        self._mapper = symbol_mapper or SymbolMapper()
        self._strategy_id = strategy_id
        self._magic = _magic_for(strategy_id)
        self._open: dict[str, BrokerOrder] = {}

    async def _do_connect(self) -> None:
        ok = self._client.initialize()
        if not ok:
            raise RuntimeError("MT5 initialize() returned False")
        logger.info("mt5.connected", magic=self._magic)

    async def _do_disconnect(self) -> None:
        self._client.shutdown()

    # -- BrokerProtocol order API ------------------------------------
    async def submit_order(self, order: Any) -> str:
        symbol = self._mapper.to_broker(order.instrument_id)
        order_type = self._order_type(order)
        volume = float(order.quantity)
        request: dict[str, Any] = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "magic": self._magic,
            "comment": self._strategy_id,
            "deviation": 20,
        }
        # Market orders omit price; limit/stop carry it.
        if order.price is not None and getattr(order, "order_type", "") != "market":
            request["price"] = float(order.price)
        if order.stop_price is not None:
            request["sl"] = float(order.stop_price)

        result = self._client.order_send(request)
        retcode = result.get("retcode")
        if retcode != RETCODE_DONE:
            raise RuntimeError(f"MT5 order_send failed: retcode={retcode}")

        broker_order_id = str(result.get("order"))
        self._open[broker_order_id] = BrokerOrder(
            broker_order_id=broker_order_id,
            local_order_id=str(getattr(order, "order_id", "")),
            namespaced_id=f"mt5:{broker_order_id}",
            instrument_id=order.instrument_id,
            side=str(order.side),
            quantity=Decimal(str(volume)),
            price=Decimal(str(order.price)) if order.price is not None else None,
            status="submitted",
        )
        return broker_order_id

    async def cancel_order(self, broker_order_id: str) -> bool:
        self._open.pop(broker_order_id, None)
        return True

    async def amend_order(self, _broker_order_id: str, **_: Any) -> bool:
        return True

    async def order_status(self, broker_order_id: str) -> Any:
        return self._open.get(broker_order_id)

    async def positions(self) -> list[BrokerPosition]:
        raw = self._client.positions_get()
        out: list[BrokerPosition] = []
        for p in raw:
            qty = float(p["volume"])
            if p["type"] in (ORDER_TYPE_SELL, ORDER_TYPE_SELL_LIMIT):
                qty = -qty
            out.append(
                BrokerPosition(
                    instrument_id=self._mapper.from_broker(p["symbol"]),
                    quantity=Decimal(str(qty)),
                    avg_price=Decimal(str(p["price_open"])),
                )
            )
        return out

    async def stream_orders(self) -> AsyncIterator[BrokerOrder]:
        if False:  # pragma: no cover - empty async generator
            yield

    async def stream_positions(self) -> AsyncIterator[BrokerPosition]:
        if False:  # pragma: no cover - empty async generator
            yield

    # -- prop-firm wiring --------------------------------------------
    def account_snapshot(self) -> tuple[float, float]:
        """Return ``(balance, equity)`` for the PropFirmRiskGovernor."""
        info = self._client.account_info()
        return float(info["balance"]), float(info["equity"])

    # -- internals ---------------------------------------------------
    @staticmethod
    def _order_type(order: Any) -> int:
        side_buy = str(getattr(order, "side", "")).lower() == "buy"
        otype = str(getattr(order, "order_type", "market")).lower()
        if otype == "limit":
            return ORDER_TYPE_BUY_LIMIT if side_buy else ORDER_TYPE_SELL_LIMIT
        return ORDER_TYPE_BUY if side_buy else ORDER_TYPE_SELL
