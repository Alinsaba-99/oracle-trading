"""Tests for NATS event models."""

from datetime import UTC, datetime
from decimal import Decimal

from core.events.agent import (
    AgentAnalysisCompletedEvent,
    AgentDebateCompletedEvent,
    AgentDecisionProposedEvent,
)
from core.events.experiment import ExperimentCompletedEvent
from core.events.feature import FeatureUpdatedEvent
from core.events.market import MarketBarEvent, MarketTickEvent
from core.events.order import OrderFilledEvent, OrderSubmittedEvent
from core.events.policy import PolicyApprovedEvent, PolicyRejectedEvent
from core.events.portfolio import PortfolioUpdatedEvent
from core.events.regime import RegimeUpdatedEvent
from core.events.signal import SignalFilteredEvent, SignalGeneratedEvent
from core.events.trade import TradeClosedEvent, TradeOpenedEvent


class TestMarketEvents:
    def test_tick_event(self):
        event = MarketTickEvent(
            instrument_id="AAPL",
            bid=Decimal("198.50"),
            ask=Decimal("198.52"),
            volume=Decimal("100"),
        )
        assert event.instrument_id == "AAPL"
        assert event.version == 1
        assert event.event_id is not None

    def test_bar_event(self):
        event = MarketBarEvent(
            instrument_id="BTC-USD",
            timeframe="1m",
            open=Decimal("62345"),
            high=Decimal("62400"),
            low=Decimal("62320"),
            close=Decimal("62380"),
            volume=Decimal("125.5"),
        )
        assert event.timeframe == "1m"


class TestSignalEvents:
    def test_generated_event(self):
        event = SignalGeneratedEvent(
            instrument_id="AAPL",
            strategy_id="gen_047",
            direction="long",
            confidence=0.73,
            reason="Bullish breakout on volume",
        )
        assert event.confidence == 0.73

    def test_filtered_event(self):
        event = SignalFilteredEvent(
            instrument_id="AAPL", filter="earnings_window", reason="Earnings within 24h"
        )
        assert event.action == "blocked"


class TestOrderEvents:
    def test_submitted(self):
        event = OrderSubmittedEvent(
            order_id="ord_001",
            instrument_id="AAPL",
            side="buy",
            order_type="limit",
            quantity=Decimal("100"),
            price=Decimal("198.50"),
        )
        assert event.price == Decimal("198.50")

    def test_filled(self):
        event = OrderFilledEvent(
            order_id="ord_001",
            instrument_id="AAPL",
            side="buy",
            quantity=Decimal("100"),
            fill_price=Decimal("198.48"),
            fill_quantity=Decimal("100"),
            filled_at=datetime.now(UTC),
        )
        assert event.fill_price == Decimal("198.48")


class TestPolicyEvents:
    def test_approved(self):
        event = PolicyApprovedEvent(policy_id="max_daily_loss", policy_type="hard_limit")
        assert event.policy_id == "max_daily_loss"

    def test_rejected(self):
        event = PolicyRejectedEvent(
            policy_id="max_daily_loss", policy_type="hard_limit", reason="Daily loss limit exceeded"
        )
        assert event.reason == "Daily loss limit exceeded"


class TestTradeEvents:
    def test_opened(self):
        event = TradeOpenedEvent(
            trade_id="trade_001",
            instrument_id="AAPL",
            direction="long",
            entry_price=Decimal("198.48"),
            quantity=Decimal("100"),
            entry_time=datetime.now(UTC),
        )
        assert event.initial_stop_loss is None

    def test_closed(self):
        event = TradeClosedEvent(
            trade_id="trade_001",
            instrument_id="AAPL",
            direction="long",
            entry_price=Decimal("198.48"),
            exit_price=Decimal("205.30"),
            quantity=Decimal("100"),
            entry_time=datetime.now(UTC),
            exit_time=datetime.now(UTC),
            pnl=Decimal("682.00"),
            pnl_pct=0.034,
            exit_reason="take_profit",
        )
        assert event.pnl == Decimal("682.00")


class TestAgentEvents:
    def test_analysis_completed(self):
        event = AgentAnalysisCompletedEvent(
            agent="fundamental_analyst",
            instrument_id="AAPL",
            signal="buy",
            confidence=0.65,
            summary="Strong cash flows",
        )
        assert event.agent == "fundamental_analyst"

    def test_debate_completed(self):
        event = AgentDebateCompletedEvent(instrument_id="AAPL", consensus="cautious_buy")
        assert event.no_trade_recommended is False

    def test_decision_proposed(self):
        event = AgentDecisionProposedEvent(
            instrument_id="AAPL", decision="buy", quantity=500, rationale="Bullish setup"
        )
        assert event.quantity == 500


class TestMiscEvents:
    def test_experiment_completed(self):
        event = ExperimentCompletedEvent(experiment_id="exp_001", metrics={"sharpe": 1.87})
        assert event.metrics["sharpe"] == 1.87

    def test_feature_updated(self):
        event = FeatureUpdatedEvent(
            instrument_id="AAPL",
            feature_set="technical_v2",
            features={"rsi_14": 62.5, "sma_20": 195.5},
        )
        assert event.features["rsi_14"] == 62.5

    def test_regime_updated(self):
        event = RegimeUpdatedEvent(regime={"volatility": "medium", "trend": "bull"})
        assert event.regime["volatility"] == "medium"

    def test_portfolio_updated(self):
        event = PortfolioUpdatedEvent(
            portfolio_id="main", total_value=Decimal("1050000"), cash=Decimal("350000")
        )
        assert event.total_value == Decimal("1050000")
