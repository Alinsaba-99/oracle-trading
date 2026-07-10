"""Tests for agents/protocol.py -- data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agents.protocol import (
    AgentVote,
    AnalystInput,
    AnalystSignal,
    DebateResult,
    MarketState,
    PortfolioDecision,
    RiskAssessment,
)


class TestAgentVote:
    def test_default_fields(self) -> None:
        v = AgentVote(direction="buy", confidence=0.8, reasoning="strong trend")
        assert v.direction == "buy"
        assert v.confidence == 0.8
        assert v.reasoning == "strong trend"
        assert v.risk_score is None

    def test_confidence_range_accepts_all_floats(self) -> None:
        v = AgentVote(direction="sell", confidence=0.0, reasoning="no confidence")
        assert v.confidence == 0.0
        v2 = AgentVote(direction="hold", confidence=1.0, reasoning="full confidence")
        assert v2.confidence == 1.0

    def test_all_direction_literals(self) -> None:
        for d in ("buy", "sell", "hold"):
            v = AgentVote(direction=d, confidence=0.5, reasoning="test")
            assert v.direction == d

    def test_invalid_direction(self) -> None:
        with pytest.raises(ValidationError):
            AgentVote(direction="invalid", confidence=0.5, reasoning="bad")  # type: ignore[arg-type]

    def test_risk_score_optional(self) -> None:
        v1 = AgentVote(direction="buy", confidence=0.5, reasoning="test")
        assert v1.risk_score is None
        v2 = AgentVote(direction="buy", confidence=0.5, reasoning="test", risk_score=0.3)
        assert v2.risk_score == 0.3

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            AgentVote()  # type: ignore[call-arg]


class TestAnalystSignal:
    def test_roundtrip_serialization(self) -> None:
        vote = AgentVote(direction="buy", confidence=0.9, reasoning="strong")
        signal = AnalystSignal(
            source="technical",
            vote=vote,
            metadata={"rsi": 72.5, "ma_cross": True},
            blind_spot="low volume",
        )
        data = signal.model_dump()
        restored = AnalystSignal.model_validate(data)
        assert restored.source == "technical"
        assert restored.vote.direction == "buy"
        assert restored.vote.confidence == 0.9
        assert restored.metadata == {"rsi": 72.5, "ma_cross": True}
        assert restored.blind_spot == "low volume"
        assert restored.prompt_hash == ""
        assert restored.model == ""
        assert restored.tokens_used == 0

    def test_all_source_literals(self) -> None:
        for src in ("macro", "technical", "sentiment"):
            s = AnalystSignal(
                source=src,
                vote=AgentVote(direction="hold", confidence=0.5, reasoning="test"),
                metadata={},
                blind_spot="none",
            )
            assert s.source == src

    def test_invalid_source(self) -> None:
        with pytest.raises(ValidationError):
            AnalystSignal(
                source="quant",  # type: ignore[arg-type]
                vote=AgentVote(direction="hold", confidence=0.5, reasoning="test"),
                metadata={},
                blind_spot="none",
            )

    def test_empty_metadata(self) -> None:
        s = AnalystSignal(
            source="sentiment",
            vote=AgentVote(direction="buy", confidence=0.6, reasoning="positive"),
            metadata={},
            blind_spot="no data",
        )
        assert s.metadata == {}


class TestPortfolioDecision:
    def test_frozen_cannot_modify(self) -> None:
        d = PortfolioDecision(
            direction="buy",
            instrument="BTC/USD",
            position_size=0.1,
            confidence=0.75,
            reasoning="strong signal",
            agents_contributing=["technical", "sentiment"],
            regime_at_decision="bull",
            risk_approved=True,
        )
        with pytest.raises(ValidationError):
            d.confidence = 0.9  # type: ignore[misc]

    def test_all_direction_literals(self) -> None:
        for d in ("buy", "sell", "hold", "no_trade"):
            p = PortfolioDecision(
                direction=d,
                instrument="ETH/USD",
                position_size=0.0,
                confidence=0.0,
                reasoning="no signal",
                agents_contributing=[],
                regime_at_decision="neutral",
                risk_approved=True,
            )
            assert p.direction == d

    def test_escalated_default(self) -> None:
        p = PortfolioDecision(
            direction="hold",
            instrument="SOL/USD",
            position_size=0.0,
            confidence=0.0,
            reasoning="wait",
            agents_contributing=[],
            regime_at_decision="neutral",
            risk_approved=False,
        )
        assert p.escalated is False

    def test_escalated_true(self) -> None:
        p = PortfolioDecision(
            direction="buy",
            instrument="SOL/USD",
            position_size=0.0,
            confidence=0.0,
            reasoning="manual review needed",
            agents_contributing=[],
            regime_at_decision="uncertain",
            risk_approved=False,
            escalated=True,
        )
        assert p.escalated is True


class TestMarketState:
    def test_frozen_cannot_modify(self) -> None:
        m = MarketState(
            regime="bull",
            phase="expansion",
            volatility="low",
            liquidity="high",
            risk_appetite="high",
        )
        with pytest.raises(ValidationError):
            m.regime = "bear"  # type: ignore[misc]

    def test_narrative_default(self) -> None:
        m = MarketState(
            regime="bear",
            phase="contraction",
            volatility="high",
            liquidity="low",
            risk_appetite="low",
        )
        assert m.narrative == ""

    def test_narrative_custom(self) -> None:
        m = MarketState(
            regime="bull",
            phase="expansion",
            volatility="low",
            liquidity="high",
            risk_appetite="high",
            narrative="Strong economic data",
        )
        assert m.narrative == "Strong economic data"


class TestDebateResult:
    def test_defaults(self) -> None:
        d = DebateResult(round_1={"macro": "buy", "technical": "hold"})
        assert d.round_2 is None
        assert d.consensus is None
        assert d.disagreements == []
        assert d.debate_quality == 0.0

    def test_frozen(self) -> None:
        d = DebateResult(round_1={"a": "buy"})
        with pytest.raises(ValidationError):
            d.debate_quality = 0.5  # type: ignore[misc]


class TestRiskAssessment:
    def test_fields(self) -> None:
        r = RiskAssessment(
            approved=True,
            max_position_size=0.1,
            kelly_fraction=0.25,
            var_95=0.02,
            reasons=["low volatility", "strong trend"],
        )
        assert r.approved is True
        assert r.max_position_size == 0.1
        assert r.reasons == ["low volatility", "strong trend"]

    def test_frozen(self) -> None:
        r = RiskAssessment(
            approved=False,
            max_position_size=0.0,
            kelly_fraction=0.0,
            var_95=0.0,
            reasons=["too risky"],
        )
        with pytest.raises(ValidationError):
            r.approved = True  # type: ignore[misc]


class TestAnalystInput:
    def test_minimal(self) -> None:
        inp = AnalystInput(
            instrument="BTC/USD",
            market_state={"regime": "bull"},
            agent_specific_data={},
        )
        assert inp.instrument == "BTC/USD"
        assert inp.agent_specific_data == {}

    def test_agent_specific_data(self) -> None:
        inp = AnalystInput(
            instrument="ETH/USD",
            market_state={"regime": "neutral"},
            agent_specific_data={"lookback": 14, "indicators": ["rsi", "macd"]},
        )
        assert inp.agent_specific_data["lookback"] == 14
