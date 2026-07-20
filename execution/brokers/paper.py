"""Paper trading broker — simulates fills with configurable slippage / latency."""

from __future__ import annotations

import random
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any
from uuid import uuid4

from execution.brokers.base import BaseBroker
from execution.brokers.config import BrokerConfig
from execution.brokers.types import BrokerFill, BrokerOrder, BrokerPosition


class PaperBroker(BaseBroker):
    """Paper / simulation broker.

    Orders are filled synchronously at a synthetic price (default ~$100
    with slippage applied).  State is kept in-memory only.
    """

    def __init__(self, config: BrokerConfig | None = None) -> None:
        super().__init__(config)
        self._orders: dict[str, BrokerOrder] = {}
        self._fills: list[BrokerFill] = []
        self._positions: dict[str, Decimal] = {}
        self._order_counter: int = 0

    # ------------------------------------------------------------------
    # Connection (no-op — always "connected")
    # ------------------------------------------------------------------
    async def _do_connect(self) -> None:
        pass

    async def _do_disconnect(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Order lifecycle
    # ------------------------------------------------------------------
    async def submit_order(self, order: Any) -> str:
        """Submit an order and immediately fill it (market-order simulation).

        Returns the broker-local order ID.
        """
        self._order_counter += 1
        broker_id = f"paper_{self._order_counter}"
        local_id = str(getattr(order, "order_id", uuid4()))

        bo = BrokerOrder(
            broker_order_id=broker_id,
            local_order_id=local_id,
            namespaced_id=f"paper:{broker_id}",
            instrument_id=getattr(order, "instrument_id", ""),
            side=str(getattr(order, "side", "buy")),
            quantity=getattr(order, "quantity", Decimal("0")),
            status="submitted",
        )
        self._orders[broker_id] = bo

        # -- Simulate fill (market order — immediate) ---------------------
        slip = 1 + (random.uniform(-1, 1) * self._config.paper_slippage_bps / 10000)
        price = Decimal(str(100 * slip)).quantize(Decimal("0.01"))
        fill_qty = bo.quantity

        fill = BrokerFill(
            broker_order_id=broker_id,
            fill_id=str(uuid4()),
            quantity=fill_qty,
            price=price,
            commission=Decimal("0"),
        )
        self._fills.append(fill)
        bo.filled_quantity = fill_qty
        bo.status = "filled"

        return broker_id

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel a previously submitted order (no-op if filled)."""
        order = self._orders.get(broker_order_id)
        if order is None:
            return False
        if order.status == "filled":
            return False
        order.status = "cancelled"
        return True

    async def amend_order(self, broker_order_id: str, **changes: Any) -> bool:
        """Amend an order's attributes (no-op for paper).

        Returns False when the order is already filled or does not exist.
        """
        _ = changes  # unused for paper
        order = self._orders.get(broker_order_id)
        return not (order is None or order.status == "filled")

    async def order_status(self, broker_order_id: str) -> str:
        """Return the status string, or ``"unknown"``."""
        order = self._orders.get(broker_order_id)
        return order.status if order else "unknown"

    async def get_fills(self) -> list[BrokerFill]:
        """Return all fills recorded by this broker (used by OrderManager reconciliation)."""
        return list(self._fills)

    async def open_orders(self) -> list[BrokerOrder]:
        """Return orders that are still open (not filled/cancelled)."""
        return [
            o for o in self._orders.values()
            if o.status not in ("filled", "cancelled")
        ]

    async def account_summary(self) -> dict:
        """Return a summary of cash / balance.

        Paper broker tracks everything in-memory; return the last P&L
        approximated from fill prices vs current synthetic price.
        """
        total_pnl = Decimal("0")
        for fill in self._fills:
            order = self._orders.get(fill.broker_order_id)
            if order is None:
                continue
            entry_price = fill.price
            current_price = Decimal(str(100))  # synthetic
            if order.side == "buy":
                pnl = (current_price - entry_price) * fill.quantity
            else:
                pnl = (entry_price - current_price) * fill.quantity
            total_pnl += pnl

        return {
            "cash": float(total_pnl + Decimal("100000")),
            "balance": float(total_pnl + Decimal("100000")),
            "pnl": float(total_pnl),
        }

    async def positions(self) -> list[BrokerPosition]:
        """Return current positions aggregated from fills."""
        from decimal import Decimal

        net: dict[str, Decimal] = {}
        avg_price: dict[str, Decimal] = {}
        for fill in self._fills:
            order = self._orders.get(fill.broker_order_id)
            if order is None:
                continue
            instrument = order.instrument_id
            signed_qty = fill.quantity if order.side == "buy" else -fill.quantity
            net[instrument] = net.get(instrument, Decimal("0")) + signed_qty
            avg_price[instrument] = fill.price
        return [
            BrokerPosition(
                instrument_id=inst, quantity=qty, avg_price=avg_price.get(inst, Decimal("0"))
            )
            for inst, qty in net.items()
            if qty != Decimal("0")
        ]

    async def stream_orders(self) -> AsyncGenerator[BrokerOrder, None]:
        """Stream order updates (passthrough stub for paper)."""
        if False:
            yield  # pragma: no cover

    async def stream_positions(self) -> AsyncGenerator[BrokerPosition, None]:
        """Stream position updates (passthrough stub for paper)."""
        if False:
            yield  # pragma: no cover
