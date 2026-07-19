"""Durable OMS — order lifecycle with idempotency and outbox integration.

The OMS is the authoritative source for order state.  It uses an
idempotency key (client_order_id) to guarantee at-most-once submission
even across network retries and process restarts.

Flow::

    Intent → validate → idempotency check → persist → submit → 
    outbox event → broker → fill → outbox event → ledger update
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Domain types ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Order:
    """Durable, immutable order record."""

    order_id: str = field(default_factory=lambda: str(uuid4()))
    account_id: str = ""
    client_order_id: str = ""
    broker_order_id: str | None = None

    instrument_id: str = ""
    side: str = "buy"
    order_type: str = "market"
    quantity: Decimal = Decimal("0")
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str = "day"
    execution_algo: str | None = None

    status: str = "pending"
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Decimal | None = None

    source: str = "api"
    strategy_id: str | None = None
    reject_reason: str | None = None
    error_message: str | None = None

    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    version: int = 1


@dataclass(frozen=True)
class Fill:
    """A single fill against an order."""

    fill_id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    account_id: str = ""
    broker_fill_id: str | None = None

    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")

    fill_time: datetime = field(default_factory=_utcnow)
    idempotency_key: str | None = None


# ── Outbox event ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class OutboxEvent:
    """Transactional outbox event for reliable async delivery."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    aggregate_type: str = ""
    aggregate_id: str = ""
    event_type: str = ""
    event_version: int = 1
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=_utcnow)


# ── Durable OMS (in-memory, same contract as PostgreSQL version) ─────


class InMemoryOMS:
    """In-memory OMS store for development / testing.

    Implements the same contract as a PostgreSQL-backed OMS but
    stores orders, fills, and outbox events in Python dicts.
    """

    def __init__(self, ledger: Any | None = None) -> None:
        self._orders: dict[str, Order] = {}
        self._fills: dict[str, Fill] = {}
        self._outbox: list[OutboxEvent] = []
        self._idempotency: dict[str, str] = {}  # client_order_id → order_id
        self._ledger = ledger

    # ── Order lifecycle ─────────────────────────────────────────────

    def create_order(self, order: Order) -> Order:
        """Persist a new order with idempotency check.

        If ``client_order_id`` was already seen, returns the existing
        order instead of creating a duplicate.
        """
        if order.client_order_id in self._idempotency:
            existing_id = self._idempotency[order.client_order_id]
            return self._orders[existing_id]

        self._orders[order.order_id] = order
        self._idempotency[order.client_order_id] = order.order_id

        self._outbox.append(OutboxEvent(
            aggregate_type="order",
            aggregate_id=order.order_id,
            event_type="order.created",
            payload={"order_id": order.order_id, "status": order.status},
        ))
        return order

    def update_order(self, order: Order) -> Order:
        """Update an existing order (idempotent status transitions)."""
        if order.order_id not in self._orders:
            raise ValueError(f"Order {order.order_id} not found")

        existing = self._orders[order.order_id]
        # Prevent backward status transitions
        if order.status == "pending" and existing.status != "pending":
            raise ValueError(
                f"Cannot revert order {order.order_id} from "
                f"{existing.status} to {order.status}"
            )

        self._orders[order.order_id] = order
        self._outbox.append(OutboxEvent(
            aggregate_type="order",
            aggregate_id=order.order_id,
            event_type=f"order.{order.status}",
            payload={"order_id": order.order_id, "status": order.status},
        ))
        return order

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_orders_by_account(self, account_id: str) -> list[Order]:
        return [
            o for o in self._orders.values()
            if o.account_id == account_id
        ]

    # ── Fill management ─────────────────────────────────────────────

    def record_fill(self, fill: Fill) -> Fill:
        """Record a fill and update the linked order.

        Duplicate detection via ``broker_fill_id``.
        """
        if fill.broker_fill_id:
            dup_key = f"{fill.order_id}:{fill.broker_fill_id}"
            if dup_key in self._fills:
                return self._fills[fill.broker_fill_id]  # type: ignore

        self._fills[fill.fill_id] = fill

        # Update the order's filled quantity
        order = self._orders.get(fill.order_id)
        if order:
            new_filled = order.filled_quantity + fill.quantity
            new_status = "filled" if new_filled >= order.quantity else "partially_filled"
            updated = Order(
                **{**order.__dict__,
                   "filled_quantity": new_filled,
                   "avg_fill_price": fill.price,
                   "status": new_status,
                   "version": order.version + 1,
                   "updated_at": _utcnow()}
            )
            self._orders[fill.order_id] = updated

            # Outbox
            self._outbox.append(OutboxEvent(
                aggregate_type="order",
                aggregate_id=order.order_id,
                event_type="order.filled",
                payload={
                    "order_id": order.order_id,
                    "fill_id": fill.fill_id,
                    "quantity": str(fill.quantity),
                    "price": str(fill.price),
                },
            ))

            # Update ledger if attached
            if self._ledger and fill.account_id:
                self._ledger.record_fill(
                    account_id=fill.account_id,
                    order_id=fill.order_id,
                    fill_id=fill.fill_id,
                    quantity=fill.quantity,
                    price=fill.price,
                    commission=fill.commission,
                    realized_pnl=fill.realized_pnl,
                )

        return fill

    def get_fills(self, order_id: str) -> list[Fill]:
        return [f for f in self._fills.values() if f.order_id == order_id]

    # ── Outbox ──────────────────────────────────────────────────────

    def pending_events(self) -> list[OutboxEvent]:
        return [e for e in self._outbox if e.status == "pending"]

    def mark_published(self, event_id: str) -> None:
        for evt in self._outbox:
            if evt.event_id == event_id:
                self._outbox.remove(evt)
                self._outbox.append(OutboxEvent(
                    **{**evt.__dict__, "status": "published"}
                ))
                break

    # ── Snapshot / recovery ─────────────────────────────────────────

    def account_snapshot(self, account_id: str) -> dict[str, Any]:
        """Return a snapshot of all orders and fills for an account."""
        orders = self.get_orders_by_account(account_id)
        fills = [
            f for o in orders
            for f in self.get_fills(o.order_id)
        ]
        return {
            "account_id": account_id,
            "orders": [o.__dict__ for o in orders],
            "fills": [f.__dict__ for f in fills],
            "snapshot_time": _utcnow().isoformat(),
        }
