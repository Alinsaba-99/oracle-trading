"""Asset hierarchy - base and derived instrument types."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from core.domain.enums import AssetClass


class Asset(BaseModel):
    asset_id: str = Field(..., description="Ticker or pair identifier")
    asset_class: AssetClass
    exchange: str
    currency: str = "USD"
    active: bool = True
    lot_size: Decimal = Decimal("1")
    tick_size: Decimal = Decimal("0.01")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Equity(Asset):
    asset_class: AssetClass = AssetClass.equity
    sector: str = ""
    industry: str = ""
    market_cap: Decimal | None = None
    dividend_yield: float | None = None
    shares_outstanding: int | None = None


class Crypto(Asset):
    asset_class: AssetClass = AssetClass.crypto
    token: str = ""
    chain: str = ""
    decimals: int = 18
    circulating_supply: Decimal | None = None


class FX(Asset):
    asset_class: AssetClass = AssetClass.fx
    quote_currency: str = ""
    pip_value: Decimal = Decimal("0.0001")
    rollover_rate: float | None = None


class Option(Asset):
    asset_class: AssetClass = AssetClass.option
    underlying: str = Field(..., description="Underlying instrument ID")
    strike: Decimal
    expiry: datetime
    option_type: str = Field(..., pattern="^(call|put)$")
    implied_volatility: float | None = None
    open_interest: int | None = None
