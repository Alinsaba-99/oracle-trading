"""IBKR live broker via ib_insync."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from execution.brokers.base import BaseBroker
from execution.brokers.config import BrokerConfig


class IBKRBroker(BaseBroker):
    """IBKR live broker via ib_insync.

    Wraps ib_insync's IB class behind BrokerProtocol.
    Uses ib_insync's asyncio-compatible event loop.
    """

    def __init__(self, config: BrokerConfig | None = None) -> None:
        super().__init__(config)
        self._ib: Any = None  # ib_insync.IB

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    async def _do_connect(self) -> None:
        from ib_insync import IB

        self._ib = IB()
        self._ib.connect(
            host=self._config.ibkr_host,
            port=self._config.ibkr_port,
            clientId=self._config.ibkr_client_id,
        )

    async def _do_disconnect(self) -> None:
        if self._ib is not None:
            self._ib.disconnect()

    # ------------------------------------------------------------------
    # Order lifecycle
    # ------------------------------------------------------------------
    async def submit_order(self, order: Any) -> str:
        """Submit an order via ib_insync.

        Converts the generic order to ib_insync Order / Contract types.
        """
        from ib_insync import LimitOrder, MarketOrder

        if order.order_type == "market":
            ib_order = MarketOrder(action=order.side.upper(), totalQuantity=float(order.quantity))
        elif order.order_type == "limit":
            ib_order = LimitOrder(
                action=order.side.upper(),
                totalQuantity=float(order.quantity),
                lmtPrice=float(order.price) if order.price else 0.0,
            )
        else:
            ib_order = MarketOrder(action=order.side.upper(), totalQuantity=float(order.quantity))

        contract = self._ib.Stock(order.instrument_id, "SMART", "USD")
        trade = self._ib.placeOrder(contract, ib_order)
        return str(trade.order.orderId) if trade else ""

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order by its broker-assigned order id."""
        if self._ib is None:
            return False
        self._ib.cancelOrder(int(broker_order_id))
        return True

    async def amend_order(self, _broker_order_id: str, **changes: Any) -> bool:
        """Modify an existing order (connected check only for stub)."""
        _ = changes
        return self._ib is not None

    async def order_status(self, broker_order_id: str) -> str:
        """Query the current status of an order."""
        if self._ib is None:
            return "unknown"
        trades = self._ib.trades()
        for t in trades:
            if str(t.order.orderId) == broker_order_id:
                return str(t.orderStatus.status)
        return "unknown"

    # ------------------------------------------------------------------
    # Positions & streaming
    # ------------------------------------------------------------------
    async def positions(self) -> list[Any]:
        """Return current positions from IBKR."""
        if self._ib is None:
            return []
        return list(self._ib.positions())

    async def stream_orders(self) -> AsyncGenerator[Any, None]:
        """Stream order updates (stub for protocol compliance)."""
        if False:
            yield  # pragma: no cover

    async def stream_positions(self) -> AsyncGenerator[Any, None]:
        """Stream position updates (stub for protocol compliance)."""
        if False:
            yield  # pragma: no cover
