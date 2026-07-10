"""Central order lifecycle manager — deterministic, no LLM involvement."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from core.domain.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from core.domain.order import Order
from execution.order_manager.errors import InvalidOrderError
from execution.order_manager.inventory import InventoryTracker
from execution.order_manager.types import FillReport, OrderRequest, OrderResult

logger = structlog.get_logger("oracle.execution")


class OrderManager:
    """Central order lifecycle manager — no LLM, purely deterministic.

    Flow: OrderRequest -> RiskManager gate #2 -> Create Order -> Submit to Broker
    """

    def __init__(self, broker: Any, risk_manager: Any | None = None) -> None:
        self._broker = broker
        self._risk = risk_manager
        self._orders: dict[str, Order] = {}
        self._inventory: InventoryTracker = InventoryTracker()

    async def submit(self, request: OrderRequest) -> OrderResult:
        """Submit order: validate -> risk gate -> create Order -> broker -> result."""
        # 1. Validate request
        if request.quantity <= 0:
            raise InvalidOrderError("Quantity must be positive")

        # 2. Risk gate #2 (position/concentration check)
        if self._risk is not None and not await self._risk.check_order(request):
            return OrderResult(
                request_id=request.request_id,
                order_id="",
                status="rejected",
                error="Risk gate #2 rejected",
            )

        # 3. Create Order
        order = Order(
            instrument_id=request.instrument_id,
            side=OrderSide(request.side),
            order_type=OrderType(request.order_type),
            quantity=request.quantity,
            price=Decimal(str(request.price)) if request.price is not None else None,
            stop_price=Decimal(str(request.stop_price)) if request.stop_price is not None else None,
            time_in_force=TimeInForce(request.time_in_force),
            execution_algo=request.execution_algo,
            strategy_id=request.strategy_id,
            portfolio_id="",
        )
        order.status = OrderStatus.submitted
        self._orders[order.order_id] = order

        # 4. Submit to broker
        try:
            broker_order_id = await self._broker.submit_order(order)
            order.broker_order_id = broker_order_id
        except Exception as e:
            order.status = OrderStatus.rejected
            order.error = str(e)
            return OrderResult(
                request_id=request.request_id,
                order_id=order.order_id,
                status="rejected",
                error=str(e),
            )

        return OrderResult(
            request_id=request.request_id,
            order_id=order.order_id,
            broker_order_id=broker_order_id,
            status="submitted",
        )

    async def cancel(self, order_id: str) -> bool:
        """Cancel an order by internal order ID."""
        order = self._orders.get(order_id)
        if not order or not order.broker_order_id:
            return False
        result = await self._broker.cancel_order(order.broker_order_id)
        return bool(result)

    def get_order(self, order_id: str) -> Order | None:
        """Look up an order by internal order ID."""
        return self._orders.get(order_id)

    def open_orders(self) -> list[Order]:
        """Return all orders with open status."""
        return [o for o in self._orders.values() if o.is_open]

    async def kill_all(self) -> int:
        """Cancel all open orders. Returns count of cancel attempts."""
        count = 0
        for o in self.open_orders():
            if o.broker_order_id:
                await self._broker.cancel_order(o.broker_order_id)
                count += 1
        return count

    async def on_fill(self, fill: FillReport) -> None:
        """Callback from broker when fill arrives."""
        order = self._orders.get(fill.order_id)
        if not order:
            return
        order.filled_quantity += fill.quantity
        order.avg_fill_price = fill.price
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.filled
        else:
            order.status = OrderStatus.partially_filled
        self._inventory.update(order, fill)
