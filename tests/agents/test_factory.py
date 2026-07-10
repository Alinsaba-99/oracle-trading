"""Tests for analysts factory — create_analyst and list_analysts."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agents.analysts.base import BaseAnalyst
from agents.analysts.factory import ANALYST_REGISTRY, create_analyst, list_analysts
from agents.analysts.macro import MacroAnalyst
from agents.analysts.sentiment import SentimentAnalyst
from agents.analysts.technical import TechnicalAnalyst
from agents.config import MASConfig

# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture
def llm_client() -> AsyncMock:
    """A minimal LLM client mock that satisfies the protocol."""
    mock = AsyncMock()
    mock.model_name = "test-factory-model"

    async def structured_call(**_kwargs: object) -> object:
        msg = "Not intended to be called in factory tests"
        raise RuntimeError(msg)

    mock.structured_call = structured_call
    return mock


# ── Tests ───────────────────────────────────────────────────────────────────


class TestCreateAnalyst:
    def test_creates_macro(self, llm_client: AsyncMock) -> None:
        """create_analyst('macro') returns a MacroAnalyst instance."""
        analyst = create_analyst("macro", llm_client)
        assert isinstance(analyst, MacroAnalyst)
        assert isinstance(analyst, BaseAnalyst)

    def test_creates_technical(self, llm_client: AsyncMock) -> None:
        """create_analyst('technical') returns a TechnicalAnalyst instance."""
        analyst = create_analyst("technical", llm_client)
        assert isinstance(analyst, TechnicalAnalyst)
        assert isinstance(analyst, BaseAnalyst)

    def test_creates_sentiment(self, llm_client: AsyncMock) -> None:
        """create_analyst('sentiment') returns a SentimentAnalyst instance."""
        analyst = create_analyst("sentiment", llm_client)
        assert isinstance(analyst, SentimentAnalyst)
        assert isinstance(analyst, BaseAnalyst)

    def test_unknown_type_raises(self, llm_client: AsyncMock) -> None:
        """create_analyst with an unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown analyst type: unknown"):
            create_analyst("unknown", llm_client)

    def test_unknown_type_shows_choices(self, llm_client: AsyncMock) -> None:
        """Error message includes available choices."""
        with pytest.raises(ValueError) as exc_info:
            create_analyst("unknown", llm_client)
        msg = str(exc_info.value)
        for choice in ("macro", "technical", "sentiment"):
            assert choice in msg

    def test_config_can_be_provided(self, llm_client: AsyncMock) -> None:
        """create_analyst accepts an optional config."""
        config = MASConfig(primary_model="custom-model")
        analyst = create_analyst("sentiment", llm_client, config=config)
        assert analyst._config.primary_model == "custom-model"


class TestListAnalysts:
    def test_returns_all_three_types(self) -> None:
        """list_analysts() returns all registered analyst types."""
        types = list_analysts()
        assert sorted(types) == sorted(["macro", "technical", "sentiment"])

    def test_matches_registry_keys(self) -> None:
        """list_analysts keys match ANALYST_REGISTRY."""
        assert list_analysts() == list(ANALYST_REGISTRY)
