"""Crypto broker via CCXT (async support)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from execution.brokers.base import BaseBroker
from execution.brokers.config import BrokerConfig


class CCXTBroker(BaseBroker):
    """Crypto broker via CCXT.

    Wraps ccxt async support behind BrokerProtocol.
    Supports 100+ exchanges (Binance, Coinbase, Kraken, etc.).
    """

    def __init__(self, config: BrokerConfig | None = None) -> None:
        super().__init__(config)
        self._exchange: Any = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    async def _do_connect(self) -> None:
        import ccxt.async_support as ccxt

        exchange_class = getattr(ccxt, self._config.ccxt_exchange, ccxt.binance)
        self._exchange = exchange_class(
            {
                "apiKey": self._config.ccxt_api_key,
                "secret": self._config.ccxt_secret,
                "sandbox": self._config.ccxt_sandbox,
            }
        )
        await self._exchange.load_markets()

    async def _do_disconnect(self) -> None:
        if self._exchange is not None:
            await self._exchange.close()

    # ------------------------------------------------------------------
    # Order lifecycle
    # ------------------------------------------------------------------
    async def submit_order(self, order: Any) -> str:
        """Submit an order via CCXT create_order."""
        symbol = order.instrument_id
        side = order.side.lower()
        amount = float(order.quantity)
        price = float(order.price) if order.price else None

        order_type = "market" if order.order_type == "market" else "limit"

        result = await self._exchange.create_order(
            symbol=symbol, type=order_type, side=side, amount=amount, price=price
        )
        return str(result.get("id", ""))

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order by its exchange-assigned id."""
        try:
            await self._exchange.cancel_order(broker_order_id)
            return True
        except Exception:
            return False

    async def amend_order(self, _broker_order_id: str, **changes: Any) -> bool:
        """Modify an existing order (connected check only for stub)."""
        _ = changes
        return self._exchange is not None

    async def order_status(self, broker_order_id: str) -> str:
        """Fetch the current status of an order."""
        try:
            order = await self._exchange.fetch_order(broker_order_id)
            return str(order.get("status", "unknown"))
        except Exception:
            return "unknown"

    # ------------------------------------------------------------------
    # Positions & streaming
    # ------------------------------------------------------------------
    async def positions(self) -> list[Any]:
        """Return current positions from the exchange."""
        try:
            return list(await self._exchange.fetch_positions())
        except Exception:
            return []

    async def stream_orders(self) -> AsyncGenerator[Any, None]:
        """Stream order updates (stub for protocol compliance)."""
        if False:
            yield  # pragma: no cover

    async def stream_positions(self) -> AsyncGenerator[Any, None]:
        """Stream position updates (stub for protocol compliance)."""
        if False:
            yield  # pragma: no cover
