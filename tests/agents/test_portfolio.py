"""Tests for PortfolioManager — decision aggregation, risk integration, escalation."""

from __future__ import annotations

import pytest

from agents.decision.portfolio import PortfolioManager
from agents.decision.risk import RiskManager
from agents.decision.scoring import SignalScorer
from agents.protocol import AgentVote, AnalystSignal, PortfolioDecision, RiskAssessment

# ── Shared fixtures ────────────────────────────────────────────────────────


def _signal(
    source: str, direction: str, confidence: float, reasoning: str = "test signal"
) -> AnalystSignal:
    return AnalystSignal(
        source=source,  # type: ignore[arg-type]
        vote=AgentVote(
            direction=direction,  # type: ignore[arg-type]
            confidence=confidence,
            reasoning=reasoning,
        ),
        metadata={},
        blind_spot="none",
    )


SIGNALS_BUY = [
    _signal("macro", "buy", 0.8, "bullish macro"),
    _signal("technical", "buy", 0.7, "bullish technical"),
    _signal("sentiment", "sell", 0.3, "bearish sentiment"),
]

SIGNALS_SELL = [
    _signal("macro", "sell", 0.9, "bearish macro"),
    _signal("technical", "sell", 0.8, "bearish technical"),
    _signal("sentiment", "sell", 0.7, "bearish sentiment"),
]

SIGNALS_SPLIT = [
    _signal("macro", "buy", 0.6, "bullish"),
    _signal("technical", "sell", 0.6, "bearish"),
    _signal("sentiment", "hold", 0.6, "neutral"),
]


@pytest.fixture
def pm() -> PortfolioManager:
    return PortfolioManager(SignalScorer(), RiskManager())


@pytest.fixture
def market_state_bull() -> object:
    return type("MarketState", (), {"regime": "bull"})()


# ── decide ─────────────────────────────────────────────────────────────────


class TestDecide:
    """PortfolioManager.decide produces correct decisions."""

    def test_returns_portfolio_decision(
        self, pm: PortfolioManager, market_state_bull: object
    ) -> None:
        """decide returns a PortfolioDecision instance."""
        result = pm.decide(SIGNALS_BUY, market_state_bull)
        assert isinstance(result, PortfolioDecision)

    def test_direction_matches_highest_weight(
        self, pm: PortfolioManager, market_state_bull: object
    ) -> None:
        """Direction is the signal with highest weighted vote."""
        result = pm.decide(SIGNALS_BUY, market_state_bull)
        assert result.direction == "buy"

    def test_sell_direction(self, pm: PortfolioManager, market_state_bull: object) -> None:
        """Sell signals produce sell direction."""
        result = pm.decide(SIGNALS_SELL, market_state_bull)
        assert result.direction == "sell"

    def test_risk_approved_when_small_position(
        self, pm: PortfolioManager, market_state_bull: object
    ) -> None:
        """Small position → risk approved."""
        result = pm.decide(SIGNALS_BUY, market_state_bull)
        assert result.risk_approved

    def test_agents_contributing_lists_sources(
        self, pm: PortfolioManager, market_state_bull: object
    ) -> None:
        """agents_contributing contains all signal source names."""
        result = pm.decide(SIGNALS_BUY, market_state_bull)
        assert sorted(result.agents_contributing) == sorted(["macro", "technical", "sentiment"])

    def test_instrument_default(self, pm: PortfolioManager, market_state_bull: object) -> None:
        """Default instrument is SPY."""
        result = pm.decide(SIGNALS_BUY, market_state_bull)
        assert result.instrument == "SPY"

    def test_regime_from_market_state(self, pm: PortfolioManager) -> None:
        """regime_at_decision is read from market_state."""
        state = type("MarketState", (), {"regime": "bear"})()
        result = pm.decide(SIGNALS_BUY, state)
        assert result.regime_at_decision == "bear"

    def test_regime_fallback_unknown(self, pm: PortfolioManager) -> None:
        """Missing regime attribute → 'unknown'."""
        state = object()
        result = pm.decide(SIGNALS_BUY, state)
        assert result.regime_at_decision == "unknown"

    def test_confidence_and_position_size_relationship(
        self, pm: PortfolioManager, market_state_bull: object
    ) -> None:
        """Position size is confidence * 0.2."""
        result = pm.decide(SIGNALS_BUY, market_state_bull)
        # buy = 0.8 + 0.7 = 1.5, sell = 0.3, total = 1.8
        # buy_w = 1.5/1.8 ≈ 0.833
        # confidence = buy_w ≈ 0.833
        # position_size = 0.833 * 0.2 ≈ 0.167
        assert result.confidence == pytest.approx(1.5 / 1.8)
        assert result.position_size == pytest.approx(result.confidence * 0.2)

    def test_decision_not_escalated_by_default(
        self, pm: PortfolioManager, market_state_bull: object
    ) -> None:
        """Regular decide returns escalated=False."""
        result = pm.decide(SIGNALS_BUY, market_state_bull)
        assert not result.escalated


class TestDecideRiskRejection:
    """RiskManager rejection handling."""

    def test_direction_becomes_no_trade_on_rejection(self, market_state_bull: object) -> None:
        """When risk rejects, direction becomes 'no_trade'."""

        class RejectAllRiskManager(RiskManager):
            def approve(
                self, _decision: object, _portfolio: object | None = None
            ) -> RiskAssessment:
                return RiskAssessment(
                    approved=False,
                    max_position_size=0.25,
                    kelly_fraction=0.2,
                    var_95=-0.02,
                    reasons=["Simulated rejection"],
                )

        rm_reject = PortfolioManager(SignalScorer(), RejectAllRiskManager())
        result = rm_reject.decide(SIGNALS_BUY, market_state_bull)
        assert result.direction == "no_trade"
        assert not result.risk_approved

    def test_rejection_includes_reason_in_reasoning(self, market_state_bull: object) -> None:
        """Risk rejection adds reason to the decision reasoning."""

        class RejectAllRiskManager(RiskManager):
            def approve(
                self, _decision: object, _portfolio: object | None = None
            ) -> RiskAssessment:
                return RiskAssessment(
                    approved=False,
                    max_position_size=0.25,
                    kelly_fraction=0.2,
                    var_95=-0.02,
                    reasons=["Simulated rejection"],
                )

        rm_reject = PortfolioManager(SignalScorer(), RejectAllRiskManager())
        result = rm_reject.decide(SIGNALS_BUY, market_state_bull)
        assert "RISK REJECTED" in result.reasoning
        assert "Simulated rejection" in result.reasoning


class TestEscalate:
    """PortfolioManager.escalate handles debate escalation."""

    def test_escalate_returns_escalated_true(self) -> None:
        """Escalate produces escalated=True."""
        result = PortfolioManager.escalate(object())
        assert result.escalated

    def test_escalate_direction_is_hold(self) -> None:
        """Escalate default direction is hold."""
        result = PortfolioManager.escalate(object())
        assert result.direction == "hold"

    def test_escalate_zero_position(self) -> None:
        """Escalate position size is 0.0."""
        result = PortfolioManager.escalate(object())
        assert result.position_size == 0.0

    def test_escalate_risk_approved(self) -> None:
        """Escalate decision has risk pre-approved."""
        result = PortfolioManager.escalate(object())
        assert result.risk_approved

    def test_escalate_confidence(self) -> None:
        """Escalate confidence is a low default (0.3)."""
        result = PortfolioManager.escalate(object())
        assert result.confidence == 0.3

    def test_escalate_instrument_default_spy(self) -> None:
        """Escalate defaults to SPY."""
        result = PortfolioManager.escalate(object())
        assert result.instrument == "SPY"


class TestBuildReasoning:
    """_build_reasoning helper."""

    def test_reasoning_includes_all_sources(self) -> None:
        """Each signal appears in reasoning output."""
        reasoning = PortfolioManager._build_reasoning(SIGNALS_BUY, "buy")
        assert "[macro]" in reasoning
        assert "[technical]" in reasoning
        assert "[sentiment]" in reasoning
        assert reasoning.startswith("Decision: BUY")
