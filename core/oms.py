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
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(UTC)


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

    # Side of the fill: "buy" debits cash by price*qty,
    # "sell" credits cash by price*qty.  Defaults to "buy" for
    # backward compatibility with existing callers.
    side: str = "buy"

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

    def __init__(self, ledger: Any | None = None, idempotency_store: Any | None = None) -> None:
        self._orders: dict[str, Order] = {}
        self._fills: dict[str, Fill] = {}
        self._broker_fill_index: dict[str, str] = {}
        self._outbox: list[OutboxEvent] = []
        self._idempotency: dict[str, str] = {}  # client_order_id → order_id
        self._ledger = ledger
        # Durable idempotency: if provided, cross-process restarts are safe.
        # The in-memory dict still serves as the fast-path cache; the
        # durable store is read on miss, written on every put.
        self._idempotency_store = idempotency_store

    # ── Order lifecycle ─────────────────────────────────────────────

    def create_order(self, order: Order) -> Order:
        """Persist a new order with idempotency check.

        If ``client_order_id`` was already seen, returns the existing
        order instead of creating a duplicate.

        Idempotency is consulted in two layers: in-memory fast path,
        then durable store (if configured).  Writes go to both layers.

        On a process restart where the in-memory order store has been
        wiped, the durable layer still resolves the
        ``client_order_id`` and returns a stub Order with the same
        ``order_id`` so the broker is not contacted twice.
        """
        # Fast path: in-memory
        if order.client_order_id in self._idempotency:
            existing_id = self._idempotency[order.client_order_id]
            existing = self._orders.get(existing_id)
            if existing is not None:
                return existing

        # Slow path: durable store (cross-process safe)
        if self._idempotency_store is not None:
            existing_id = self._idempotency_store.get(order.client_order_id)
            if existing_id is not None:
                # Backfill fast-path cache; return whichever order we
                # have, or a stub if the in-memory orders dict was wiped.
                existing = self._orders.get(existing_id)
                if existing is not None:
                    self._idempotency[order.client_order_id] = existing_id
                    return existing
                # Stub: caller will see the right order_id; the broker
                # will short-circuit because we don't re-submit.
                stub = Order(**{**order.__dict__, "order_id": existing_id, "status": "submitted"})
                return stub

        # Neither layer has it: persist a fresh order.
        self._orders[order.order_id] = order
        self._idempotency[order.client_order_id] = order.order_id
        if self._idempotency_store is not None:
            self._idempotency_store.put(order.client_order_id, order.order_id)

        self._outbox.append(
            OutboxEvent(
                aggregate_type="order",
                aggregate_id=order.order_id,
                event_type="order.created",
                payload={"order_id": order.order_id, "status": order.status},
            )
        )
        return order

    def update_order(self, order: Order) -> Order:
        """Update an existing order (idempotent status transitions)."""
        if order.order_id not in self._orders:
            raise ValueError(f"Order {order.order_id} not found")

        existing = self._orders[order.order_id]
        # Prevent backward status transitions
        if order.status == "pending" and existing.status != "pending":
            raise ValueError(
                f"Cannot revert order {order.order_id} from {existing.status} to {order.status}"
            )

        self._orders[order.order_id] = order
        self._outbox.append(
            OutboxEvent(
                aggregate_type="order",
                aggregate_id=order.order_id,
                event_type=f"order.{order.status}",
                payload={"order_id": order.order_id, "status": order.status},
            )
        )
        return order

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_orders_by_account(self, account_id: str) -> list[Order]:
        return [o for o in self._orders.values() if o.account_id == account_id]

    # ── Fill management ─────────────────────────────────────────────

    def record_fill(self, fill: Fill) -> Fill:
        """Record a fill and update the linked order.

        Duplicate detection via ``broker_fill_id``.

        Computes ``avg_fill_price`` as a volume-weighted average across
        all fills received so far for this order (NOT just the latest
        fill price).  Also enforces a cumulative overfill guard: raises
        ValueError if accepting this fill would push cumulative
        ``filled_quantity`` above ``order.quantity``.
        """
        if fill.broker_fill_id:
            dup_key = f"{fill.order_id}:{fill.broker_fill_id}"
            existing_fill_id = self._broker_fill_index.get(dup_key)
            if existing_fill_id is not None:
                return self._fills[existing_fill_id]

        self._fills[fill.fill_id] = fill
        if fill.broker_fill_id:
            self._broker_fill_index[f"{fill.order_id}:{fill.broker_fill_id}"] = fill.fill_id

        # Update the order's filled quantity + VWAP
        order = self._orders.get(fill.order_id)
        if order:
            new_filled = order.filled_quantity + fill.quantity
            # Overfill guard: cumulative fills must not exceed order quantity
            if new_filled > order.quantity:
                raise ValueError(
                    f"Cumulative fill quantity {new_filled} would exceed "
                    f"order {order.order_id} quantity {order.quantity}"
                )

            # VWAP across all fills so far for this order, weighted by quantity
            order_fills = self.get_fills(fill.order_id)
            total_qty = sum((f.quantity for f in order_fills), Decimal("0"))
            if total_qty > 0:
                vwap = sum((f.price * f.quantity for f in order_fills), Decimal("0")) / total_qty
            else:
                vwap = fill.price

            new_status = "filled" if new_filled >= order.quantity else "partially_filled"
            updated = Order(
                **{
                    **order.__dict__,
                    "filled_quantity": new_filled,
                    "avg_fill_price": vwap,
                    "status": new_status,
                    "version": order.version + 1,
                    "updated_at": fill.fill_time,
                }
            )
            self._orders[fill.order_id] = updated

            # Outbox
            self._outbox.append(
                OutboxEvent(
                    aggregate_type="order",
                    aggregate_id=order.order_id,
                    event_type="order.filled",
                    payload={
                        "order_id": order.order_id,
                        "fill_id": fill.fill_id,
                        "quantity": str(fill.quantity),
                        "price": str(fill.price),
                    },
                )
            )

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
                    side=fill.side,
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
                self._outbox.append(OutboxEvent(**{**evt.__dict__, "status": "published"}))
                break

    # ── Snapshot / recovery ─────────────────────────────────────────

    def account_snapshot(self, account_id: str) -> dict[str, Any]:
        """Return a snapshot of all orders and fills for an account."""
        orders = self.get_orders_by_account(account_id)
        fills = [f for o in orders for f in self.get_fills(o.order_id)]
        return {
            "account_id": account_id,
            "orders": [o.__dict__ for o in orders],
            "fills": [f.__dict__ for f in fills],
            "snapshot_time": _utcnow().isoformat(),
        }
