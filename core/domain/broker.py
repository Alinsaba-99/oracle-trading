"""Canonical broker-level order, fill, and position models.

Moved from ``execution.brokers.types`` (P0 cycle-break: ``core.kill`` needs
these types and core may not import execution).  ``execution/brokers/types.py``
remains as a backward-compatible re-export shim.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class BrokerOrder(BaseModel):
    """Canonical broker-order representation (normalised across IBKR / CCXT / Paper)."""

    broker_order_id: str
    local_order_id: str
    namespaced_id: str  # e.g. "ibkr:12345" or "paper:1"
    instrument_id: str
    side: str
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    price: Decimal | None = None
    status: str = "pending"
    created_at: str = ""

    # M32-010: order-type + attached bracket legs ---------------------------
    order_type: str = "market"  # market | limit | stop | stop_limit
    stop_price: Decimal | None = None
    take_profit_price: Decimal | None = None
    parent_order_id: str | None = None  # set on child legs of a bracket


class BrokerFill(BaseModel):
    """A single fill (partial or full) reported by the broker."""

    broker_order_id: str
    fill_id: str
    quantity: Decimal
    price: Decimal
    commission: Decimal = Decimal("0")
    filled_at: str = ""


class BrokerPosition(BaseModel):
    """Normalised position snapshot from the broker."""

    instrument_id: str
    quantity: Decimal
    avg_price: Decimal = Field(decimal_places=4)
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")


__all__ = ["BrokerFill", "BrokerOrder", "BrokerPosition"]
