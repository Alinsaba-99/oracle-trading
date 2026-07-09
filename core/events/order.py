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
