"""Pydantic models for order requests, results, and fill reports."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    """Request to create an order — pre-risk, pre-broker."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    instrument_id: str
    side: str  # buy/sell
    quantity: Decimal = Field(decimal_places=4)
    order_type: str = "market"  # market, limit, stop
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str = "day"
    execution_algo: str | None = None
    algo_config: dict[str, Any] = {}
    source: str = "mas"  # mas, cli, manual
    strategy_id: str = ""


class OrderResult(BaseModel):
    """Result of submitting an order."""

    request_id: str
    order_id: str
    broker_order_id: str = ""
    status: str  # pending, submitted, rejected
    error: str | None = None
    submitted_at: str = ""


class FillReport(BaseModel):
    """Report of a fill (partial or full)."""

    order_id: str
    broker_order_id: str
    fill_id: str
    quantity: Decimal
    price: Decimal
    commission: Decimal = Decimal("0")
    filled_at: str = ""
