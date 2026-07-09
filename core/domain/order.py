"""Order model with lifecycle."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from core.domain.enums import OrderSide, OrderStatus, OrderType, TimeInForce


class Order(BaseModel):
    order_id: str = Field(default_factory=lambda: str(uuid4()))
    instrument_id: str
    portfolio_id: str
    strategy_id: str = ""
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.day
    status: OrderStatus = OrderStatus.pending
    execution_algo: str | None = None
    broker_order_id: str | None = None
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Decimal | None = None
    commission: Decimal = Decimal("0")
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_order_type(self) -> "Order":
        if self.order_type == OrderType.market:
            assert self.price is None, "Market orders must not have price"
        if self.order_type == OrderType.limit:
            assert self.price is not None, "Limit orders must have price"
        if self.order_type == OrderType.stop:
            assert self.stop_price is not None, "Stop orders must have stop_price"
        assert self.quantity > 0, "Quantity must be positive"
        assert self.filled_quantity <= self.quantity, "Filled qty must be <= quantity"
        assert self.commission >= 0, "Commission must be non-negative"
        return self

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.filled

    @property
    def is_open(self) -> bool:
        return self.status in (
            OrderStatus.pending,
            OrderStatus.submitted,
            OrderStatus.partially_filled,
        )
