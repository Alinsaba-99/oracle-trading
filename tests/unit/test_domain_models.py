"""Tests for core domain models."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from core.domain.asset import FX, Crypto, Equity, Option
from core.domain.bar import Bar, Tick
from core.domain.enums import (
    AssetClass,
    OrderSide,
    OrderType,
    TimeFrame,
    TradeDirection,
    TradeStatus,
)
from core.domain.order import Order
from core.domain.policy import Policy, PolicyCondition, PolicyType
from core.domain.signal import Signal
from core.domain.trade import Trade


class TestAssetModels:
    def test_equity_defaults(self):
        aapl = Equity(asset_id="AAPL", exchange="NASDAQ")
        assert aapl.asset_class == AssetClass.equity
        assert aapl.currency == "USD"
        assert aapl.active is True

    def test_crypto_defaults(self):
        btc = Crypto(asset_id="BTC-USD", exchange="BINANCE", token="BTC")
        assert btc.asset_class == AssetClass.crypto
        assert btc.decimals == 18

    def test_fx_defaults(self):
        eur = FX(asset_id="EUR-USD", exchange="IDEALPRO", quote_currency="USD")
        assert eur.asset_class == AssetClass.fx
        assert eur.pip_value == Decimal("0.0001")

    def test_option_validation(self):
        opt = Option(
            asset_id="AAPL250717C00200000",
            exchange="OPRA",
            underlying="AAPL",
            strike=Decimal("200"),
            expiry=datetime(2025, 7, 17),
            option_type="call",
        )
        assert opt.asset_class == AssetClass.option
        assert opt.option_type == "call"

    def test_option_invalid_type(self):
        with pytest.raises(ValidationError):
            Option(
                asset_id="INVALID",
                exchange="OPRA",
                underlying="AAPL",
                strike=Decimal("200"),
                expiry=datetime(2025, 7, 17),
                option_type="invalid",
            )


class TestBarModel:
    def test_valid_bar(self):
        bar = Bar(
            instrument_id="AAPL",
            timestamp=datetime.now(UTC),
            timeframe=TimeFrame.d1,
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("99"),
            close=Decimal("103"),
            volume=Decimal("1000000"),
        )
        assert bar.complete is False
        assert bar.vwap is None

    def test_invalid_ohlc(self):
        with pytest.raises(ValidationError):
            Bar(
                instrument_id="AAPL",
                timestamp=datetime.now(UTC),
                timeframe=TimeFrame.d1,
                open=Decimal("100"),
                high=Decimal("99"),
                low=Decimal("95"),
                close=Decimal("97"),
                volume=Decimal("1000000"),
            )

    def test_negative_volume(self):
        with pytest.raises(ValidationError):
            Bar(
                instrument_id="AAPL",
                timestamp=datetime.now(UTC),
                timeframe=TimeFrame.d1,
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("95"),
                close=Decimal("103"),
                volume=Decimal("-100"),
            )


class TestTickModel:
    def test_valid_tick(self):
        tick = Tick(
            instrument_id="AAPL",
            timestamp=datetime.now(UTC),
            price=Decimal("150.25"),
            volume=Decimal("100"),
        )
        assert tick.price == Decimal("150.25")

    def test_negative_price(self):
        with pytest.raises(ValidationError):
            Tick(
                instrument_id="AAPL",
                timestamp=datetime.now(UTC),
                price=Decimal("-10"),
                volume=Decimal("100"),
            )


class TestOrderModel:
    def test_market_order(self):
        order = Order(
            instrument_id="AAPL",
            portfolio_id="test",
            side=OrderSide.buy,
            order_type=OrderType.market,
            quantity=Decimal("100"),
            strategy_id="strat_1",
        )
        assert order.status.value == "pending"
        assert order.price is None
        assert order.is_open is True

    def test_limit_order(self):
        order = Order(
            instrument_id="AAPL",
            portfolio_id="test",
            side=OrderSide.buy,
            order_type=OrderType.limit,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
        )
        assert order.price == Decimal("150.00")

    def test_limit_order_missing_price(self):
        with pytest.raises(ValidationError):
            Order(
                instrument_id="AAPL",
                portfolio_id="test",
                side=OrderSide.buy,
                order_type=OrderType.limit,
                quantity=Decimal("100"),
            )

    def test_stop_order_missing_stop(self):
        with pytest.raises(ValidationError):
            Order(
                instrument_id="AAPL",
                portfolio_id="test",
                side=OrderSide.buy,
                order_type=OrderType.stop,
                quantity=Decimal("100"),
            )

    def test_order_lifecycle(self):
        order = Order(
            instrument_id="AAPL",
            portfolio_id="test",
            side=OrderSide.buy,
            order_type=OrderType.market,
            quantity=Decimal("100"),
        )
        assert order.is_filled is False

        filled = order.model_copy(update={"status": "filled", "filled_quantity": Decimal("100")})
        assert filled.is_filled is True


class TestTradeModel:
    def test_trade_creation(self):
        trade = Trade(
            instrument_id="AAPL",
            direction=TradeDirection.long,
            entry_price=Decimal("150.00"),
            quantity=Decimal("100"),
            entry_time=datetime.now(UTC),
        )
        assert trade.status == TradeStatus.open
        assert trade.duration_hours is None
        assert trade.is_profitable is None

    def test_trade_close(self):
        entry_time = datetime.now(UTC)
        exit_time = entry_time + timedelta(days=3)
        trade = Trade(
            instrument_id="AAPL",
            direction=TradeDirection.long,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("165.00"),
            quantity=Decimal("100"),
            entry_time=entry_time,
            exit_time=exit_time,
            status=TradeStatus.closed,
            pnl=Decimal("1500.00"),
            pnl_pct=0.10,
            exit_reason="take_profit",
        )
        assert trade.status == TradeStatus.closed
        assert trade.duration_hours == 72
        assert trade.is_profitable is True

    def test_trade_short_profit(self):
        trade = Trade(
            instrument_id="AAPL",
            direction=TradeDirection.short,
            entry_price=Decimal("150.00"),
            exit_price=Decimal("135.00"),
            quantity=Decimal("100"),
            entry_time=datetime.now(UTC),
            exit_time=datetime.now(UTC),
            status=TradeStatus.closed,
            pnl=Decimal("1500.00"),
            pnl_pct=0.10,
            exit_reason="take_profit",
        )
        assert trade.is_profitable is True


class TestSignalModel:
    def test_valid_signal(self):
        signal = Signal(
            instrument_id="AAPL", direction="long", confidence=0.75, strategy_id="gen_047"
        )
        assert signal.direction == "long"
        assert signal.confidence == 0.75

    def test_invalid_confidence(self):
        with pytest.raises(ValidationError):
            Signal(instrument_id="AAPL", direction="long", confidence=1.5)

    def test_invalid_direction(self):
        with pytest.raises(ValidationError):
            Signal(instrument_id="AAPL", direction="buy", confidence=0.5)


class TestPolicyModel:
    def test_policy_creation(self):
        policy = Policy(
            policy_id="max_daily_loss",
            name="Maximum Daily Loss",
            type=PolicyType.hard_limit,
            priority=100,
            conditions=[
                PolicyCondition(metric="portfolio.day_pnl", operator="less_than", value=-5000)
            ],
        )
        assert policy.policy_id == "max_daily_loss"
        assert len(policy.conditions) == 1
        assert policy.conditions[0].metric == "portfolio.day_pnl"

    def test_policy_priority_ordering(self):
        policies = [
            Policy(policy_id="a", priority=10, conditions=[]),
            Policy(policy_id="b", priority=100, conditions=[]),
            Policy(policy_id="c", priority=50, conditions=[]),
        ]
        sorted_policies = sorted(policies, key=lambda p: -p.priority)
        assert [p.policy_id for p in sorted_policies] == ["b", "c", "a"]
