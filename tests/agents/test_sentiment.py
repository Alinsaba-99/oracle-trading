"""Tests for SentimentAnalyst."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.analysts.sentiment import SentimentAnalyst, SentimentResponse
from agents.config import MASConfig
from agents.protocol import AnalystInput, AnalystSignal

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_llm(response: SentimentResponse | None = None) -> AsyncMock:
    """Return an async mock LLM client that returns a canned SentimentResponse."""
    mock = AsyncMock()
    mock.model_name = "test-sentiment-model"

    if response is None:
        response = SentimentResponse(
            direction="buy",
            confidence=0.75,
            reasoning="Positive sentiment detected across news and social channels.",
            sentiment_score=0.6,
        )

    async def structured_call(**_kwargs: Any) -> SentimentResponse:
        return response

    mock.structured_call = structured_call
    return mock


def _make_input(
    instrument: str = "BTC/USD",
    news: float = 0.3,
    social: float = 0.5,
    overall: float | None = None,
    fear_greed: int = 55,
) -> AnalystInput:
    sentiment_data: dict[str, Any] = {
        "news": news,
        "social": social,
        "fear_greed": fear_greed,
    }
    if overall is not None:
        sentiment_data["overall"] = overall
    return AnalystInput(
        instrument=instrument,
        market_state={"regime": "bull", "volatility": "medium"},
        agent_specific_data={"sentiment": sentiment_data},
    )


# ── Tests ───────────────────────────────────────────────────────────────────


class TestSentimentAnalystConstruction:
    def test_blind_spot(self) -> None:
        """Blind spot highlights the sentiment-only limitation."""
        config = MASConfig()
        llm = _make_llm()
        analyst = SentimentAnalyst(llm_client=llm, config=config)
        assert (
            analyst.blind_spot
            == "Ignora prezzi e fondamentali — si basa solo su sentiment e news"
        )

    def test_name(self) -> None:
        """Name property returns 'sentiment'."""
        config = MASConfig()
        llm = _make_llm()
        analyst = SentimentAnalyst(llm_client=llm, config=config)
        assert analyst.name == "sentiment"


class TestSentimentAnalystAnalyze:
    @pytest.mark.asyncio
    async def test_returns_analyst_signal(self) -> None:
        """Happy path — SentimentAnalyst returns a well-formed AnalystSignal."""
        llm = _make_llm()
        analyst = SentimentAnalyst(llm_client=llm, config=MASConfig())
        result = await analyst.analyze(_make_input())
        assert isinstance(result, AnalystSignal)
        assert result.source == "sentiment"
        assert result.vote.direction == "buy"
        assert result.vote.confidence == 0.75

    @pytest.mark.asyncio
    async def test_extreme_positive_sentiment_yields_buy(self) -> None:
        """Very positive sentiment → buy direction."""
        bullish = SentimentResponse(
            direction="buy",
            confidence=0.95,
            reasoning="Extremely positive sentiment across all channels.",
            sentiment_score=0.92,
        )
        llm = _make_llm(bullish)
        analyst = SentimentAnalyst(llm_client=llm, config=MASConfig())
        result = await analyst.analyze(
            _make_input(news=0.9, social=0.85, fear_greed=85),
        )
        assert result.vote.direction == "buy"
        assert result.vote.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_extreme_negative_sentiment_yields_sell(self) -> None:
        """Very negative sentiment → sell direction."""
        bearish = SentimentResponse(
            direction="sell",
            confidence=0.9,
            reasoning="Strongly negative sentiment across news and social media.",
            sentiment_score=-0.85,
        )
        llm = _make_llm(bearish)
        analyst = SentimentAnalyst(llm_client=llm, config=MASConfig())
        result = await analyst.analyze(
            _make_input(news=-0.8, social=-0.9, fear_greed=15),
        )
        assert result.vote.direction == "sell"
        assert result.vote.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_neutral_sentiment_yields_hold(self) -> None:
        """Mixed/neutral sentiment → hold direction."""
        neutral = SentimentResponse(
            direction="hold",
            confidence=0.6,
            reasoning="Mixed signals — news positive but social negative.",
            sentiment_score=0.05,
        )
        llm = _make_llm(neutral)
        analyst = SentimentAnalyst(llm_client=llm, config=MASConfig())
        result = await analyst.analyze(
            _make_input(news=0.1, social=-0.1, fear_greed=50),
        )
        assert result.vote.direction == "hold"

    @pytest.mark.asyncio
    async def test_metadata_includes_sentiment_scores(self) -> None:
        """Analyze populates metadata with all sentiment values."""
        llm = _make_llm()
        analyst = SentimentAnalyst(llm_client=llm, config=MASConfig())
        result = await analyst.analyze(
            _make_input(news=0.4, social=0.6, overall=0.5, fear_greed=65),
        )
        assert result.metadata["news_sentiment"] == 0.4
        assert result.metadata["social_sentiment"] == 0.6
        assert result.metadata["overall_sentiment"] == 0.5
        assert result.metadata["fear_greed_index"] == 65
        assert result.metadata["sentiment_score"] == 0.6

    @pytest.mark.asyncio
    async def test_blind_spot_in_signal(self) -> None:
        """AnalystSignal carries the correct blind spot."""
        llm = _make_llm()
        analyst = SentimentAnalyst(llm_client=llm, config=MASConfig())
        result = await analyst.analyze(_make_input())
        assert "Ignora prezzi e fondamentali" in result.blind_spot

    @pytest.mark.asyncio
    async def test_overall_sentiment_defaults_to_average(self) -> None:
        """When overall is not provided, it's computed as (news+social)/2."""
        llm = _make_llm()
        analyst = SentimentAnalyst(llm_client=llm, config=MASConfig())
        result = await analyst.analyze(
            _make_input(news=0.8, social=0.6, overall=None),
        )
        # (0.8 + 0.6) / 2 = 0.7 → should be in metadata
        assert result.metadata["overall_sentiment"] == 0.7
