"""Central order lifecycle manager — deterministic, no LLM involvement."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

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

    The ``risk_manager`` parameter is required.  Passing ``None`` raises
    ``ValueError`` — a missing risk gate is a safety violation.
    """

    def __init__(self, broker: Any, risk_manager: Any) -> None:
        if risk_manager is None:
            raise ValueError("risk_manager is required — a missing risk gate is a safety violation")
        self._broker = broker
        self._risk = risk_manager
        self._orders: dict[str, Order] = {}
        self._inventory: InventoryTracker = InventoryTracker()
        self._seen_fills: set[str] = set()
        self._seen_requests: dict[str, OrderResult] = {}

    async def submit(self, request: OrderRequest) -> OrderResult:
        """Submit order: validate -> idempotency check -> risk gate -> broker.

        Idempotency: if the same ``request_id`` was already processed,
        the previous result is returned without creating a new order.
        This prevents duplicate positions on network retry / timeout.
        """
        # 1. Idempotency check
        if request.request_id in self._seen_requests:
            logger.warning("duplicate_submit", request_id=request.request_id)
            return self._seen_requests[request.request_id]

        # 2. Validate request
        if request.quantity <= 0:
            raise InvalidOrderError("Quantity must be positive")

        # 2. Risk gate #2 (position/concentration check)
        if not await self._risk.check_order(request):
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

        result = OrderResult(
            request_id=request.request_id,
            order_id=order.order_id,
            broker_order_id=broker_order_id,
            status="submitted",
        )
        self._seen_requests[request.request_id] = result
        return result

    async def reconcile(self) -> None:
        """Reconcile internal order state with broker-reported state.

        Queries the broker for fills and positions, then updates the
        internal ``_orders`` dict to match broker reality.  This fixes
        the divergence where PaperBroker fills immediately but the
        OrderManager stays on ``submitted``.

        Called automatically by :meth:`open_orders` and :meth:`kill_all`.
        """
        try:
            # Query broker fills if the broker exposes them
            fills: list[Any] = []
            if hasattr(self._broker, "get_fills"):
                fills = await self._broker.get_fills()
            elif hasattr(self._broker, "_fills"):
                fills = getattr(self._broker, "_fills", [])

            for fill in fills:
                fill_id = str(getattr(fill, "fill_id", uuid4()))
                if fill_id in self._seen_fills:
                    continue

                broker_order_id = str(getattr(fill, "broker_order_id", ""))
                # Find the matching Order by broker_order_id
                order = next(
                    (o for o in self._orders.values() if o.broker_order_id == broker_order_id), None
                )
                if order is None:
                    continue

                fill_report = FillReport(
                    order_id=order.order_id,
                    broker_order_id=broker_order_id,
                    fill_id=fill_id,
                    quantity=Decimal(str(getattr(fill, "quantity", 0))),
                    price=Decimal(str(getattr(fill, "price", 0))),
                    commission=Decimal(str(getattr(fill, "commission", 0))),
                )
                await self.on_fill(fill_report)

        except Exception:
            logger.exception("Order reconciliation failed")

    async def cancel(self, order_id: str) -> bool:
        """Cancel an order by internal order ID."""
        order = self._orders.get(order_id)
        if not order or not order.broker_order_id:
            return False
        result = await self._broker.cancel_order(order.broker_order_id)
        if result:
            order.status = OrderStatus.cancelled
        return bool(result)

    def get_order(self, order_id: str) -> Order | None:
        """Look up an order by internal order ID."""
        return self._orders.get(order_id)

    async def open_orders(self) -> list[Order]:
        """Return all orders with open status (reconciled with broker first)."""
        await self.reconcile()
        return [o for o in self._orders.values() if o.is_open]

    async def kill_all(self) -> int:
        """Cancel all open orders. Returns count of cancel attempts."""
        await self.reconcile()
        count = 0
        for o in self._orders.values():
            if o.is_open and o.broker_order_id:
                result = await self._broker.cancel_order(o.broker_order_id)
                if result:
                    o.status = OrderStatus.cancelled
                count += 1
        return count

    async def on_fill(self, fill: FillReport) -> None:
        """Callback from broker when fill arrives."""
        if fill.fill_id in self._seen_fills:
            return
        self._seen_fills.add(fill.fill_id)
        order = self._orders.get(fill.order_id)
        if not order:
            return

        # Overfill protection: reject fill cumulative > quantity
        new_filled = order.filled_quantity + fill.quantity
        if new_filled > order.quantity:
            logger.error(
                "overfill_rejected",
                order_id=fill.order_id,
                quantity=order.quantity,
                existing=order.filled_quantity,
                incoming=fill.quantity,
            )
            return

        order.filled_quantity = new_filled
        order.avg_fill_price = fill.price
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.filled
        else:
            order.status = OrderStatus.partially_filled
        self._inventory.update(order, fill)
