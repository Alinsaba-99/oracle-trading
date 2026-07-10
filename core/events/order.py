"""Order event models."""

from datetime import datetime
from decimal import Decimal

from core.domain.events import Event


class OrderSubmittedEvent(Event):
    order_id: str
    instrument_id: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal | None = None
    time_in_force: str = "day"
    strategy_id: str = ""
    portfolio_id: str = ""
    broker: str = ""
    execution_algo: str | None = None


class OrderFilledEvent(Event):
    order_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    fill_price: Decimal
    fill_quantity: Decimal
    commission: Decimal = Decimal("0")
    filled_at: datetime
    broker: str = ""
    venue: str = ""


class OrderCancelledEvent(Event):
    order_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    cancelled_quantity: Decimal
    broker: str = ""
    reason: str = ""


class OrderRejectedEvent(Event):
    order_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    reason: str
    broker: str = ""
    error_code: str = ""


class OrderPartiallyFilledEvent(Event):
    order_id: str
    instrument_id: str
    side: str
    fill_quantity: Decimal
    fill_price: Decimal
    remaining_quantity: Decimal
    commission: Decimal = Decimal("0")
    filled_at: datetime
    broker: str = ""


class OrderAmendedEvent(Event):
    order_id: str
    instrument_id: str
    previous_price: Decimal | None = None
    new_price: Decimal | None = None
    previous_quantity: Decimal | None = None
    new_quantity: Decimal | None = None
    broker: str = ""
