"""Tests for the MacroAnalyst agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, PropertyMock

import pytest
from pydantic import BaseModel

from agents.analysts.macro import MacroAnalyst
from agents.config import MASConfig
from agents.errors import ModelCallError
from agents.protocol import AgentVote, AnalystInput, AnalystSignal

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def llm_client() -> AsyncMock:
    """Return a mock LLM client that succeeds by default."""
    client = AsyncMock()

    async def structured_call_impl(**_: object) -> BaseModel:
        return AgentVote(
            direction="buy",
            confidence=0.75,
            reasoning="GDP growth above trend, CPI stable, accommodative central bank.",
            risk_score=0.3,
        )

    client.structured_call = structured_call_impl
    type(client).model_name = PropertyMock(return_value="mock-model/v1")
    return client


@pytest.fixture
def config() -> MASConfig:
    return MASConfig()


@pytest.fixture
def analyst(llm_client: AsyncMock, config: MASConfig) -> MacroAnalyst:
    return MacroAnalyst(llm_client=llm_client, config=config)


@pytest.fixture
def sample_input() -> AnalystInput:
    return AnalystInput(
        instrument="SPY",
        market_state=None,
        agent_specific_data={"gdp": 2.4, "cpi": 3.1, "interest_rate": 5.5, "unemployment": 3.7},
    )


# ── Basic Properties ──────────────────────────────────────────────────────────


class TestMacroAnalystIdentity:
    """Verify static identity properties of the macro analyst."""

    def test_name(self, analyst: MacroAnalyst) -> None:
        assert analyst.name == "macro"

    def test_blind_spot(self, analyst: MacroAnalyst) -> None:
        spot = analyst.blind_spot
        assert isinstance(spot, str)
        assert len(spot) > 10
        assert "price action" in spot or "volumi" in spot


# ── Analysis ──────────────────────────────────────────────────────────────────


class TestMacroAnalystAnalyze:
    """Verify the analyze method produces correct signals."""

    async def test_returns_analystsignal(
        self, analyst: MacroAnalyst, sample_input: AnalystInput
    ) -> None:
        signal = await analyst.analyze(sample_input)

        assert isinstance(signal, AnalystSignal)
        assert signal.source == "macro"
        assert signal.vote.direction == "buy"
        assert signal.vote.confidence == 0.75
        assert signal.blind_spot == analyst.blind_spot
        assert signal.model == "mock-model/v1"
        assert isinstance(signal.prompt_hash, str)
        assert len(signal.prompt_hash) > 0

    async def test_metadata_contains_indicators(
        self, analyst: MacroAnalyst, sample_input: AnalystInput
    ) -> None:
        signal = await analyst.analyze(sample_input)

        assert "indicators_used" in signal.metadata
        assert "gdp" in signal.metadata["indicators_used"]
        assert "cpi" in signal.metadata["indicators_used"]
        assert signal.metadata["indicators"]["gdp"] == 2.4

    async def test_llm_failure_returns_safe_signal(
        self, config: MASConfig, sample_input: AnalystInput
    ) -> None:
        failing_client = AsyncMock()
        failing_client.structured_call = AsyncMock(side_effect=ModelCallError("API timeout"))
        type(failing_client).model_name = PropertyMock(return_value="failing-model")
        analyst = MacroAnalyst(llm_client=failing_client, config=config)

        signal = await analyst.analyze(sample_input)

        assert isinstance(signal, AnalystSignal)
        assert signal.vote.direction == "hold"
        assert signal.vote.confidence == 0.0
        assert signal.vote.risk_score == 1.0
        assert "error" in signal.metadata

    async def test_llm_non_model_error_handled(
        self, config: MASConfig, sample_input: AnalystInput
    ) -> None:
        """A generic exception from the LLM also yields a safe signal."""
        failing_client = AsyncMock()
        failing_client.structured_call = AsyncMock(side_effect=RuntimeError("connection refused"))
        type(failing_client).model_name = PropertyMock(return_value="err-model")
        analyst = MacroAnalyst(llm_client=failing_client, config=config)

        signal = await analyst.analyze(sample_input)

        assert isinstance(signal, AnalystSignal)
        assert signal.vote.direction == "hold"

    async def test_empty_indicators_no_crash(self, analyst: MacroAnalyst) -> None:
        input_empty = AnalystInput(instrument="SPY", market_state=None, agent_specific_data={})
        signal = await analyst.analyze(input_empty)

        assert isinstance(signal, AnalystSignal)
        assert signal.metadata["indicators_used"] == []
        assert signal.vote.direction == "buy"  # mock still returns buy

    async def test_different_input_produces_different_prompt_hash(
        self, analyst: MacroAnalyst
    ) -> None:
        input_a = AnalystInput(
            instrument="SPY",
            market_state=None,
            agent_specific_data={"gdp": 2.4, "cpi": 3.1, "interest_rate": 5.5, "unemployment": 3.7},
        )
        input_b = AnalystInput(
            instrument="QQQ",
            market_state=None,
            agent_specific_data={
                "gdp": -0.5,
                "cpi": 6.2,
                "interest_rate": 7.0,
                "unemployment": 5.2,
            },
        )

        signal_a = await analyst.analyze(input_a)
        signal_b = await analyst.analyze(input_b)

        assert signal_a.prompt_hash != signal_b.prompt_hash

    async def test_extra_indicators_in_metadata(self, analyst: MacroAnalyst) -> None:
        input_extra = AnalystInput(
            instrument="SPY",
            market_state=None,
            agent_specific_data={
                "gdp": 2.4,
                "cpi": 3.1,
                "interest_rate": 5.5,
                "unemployment": 3.7,
                "retail_sales": 0.8,
                "industrial_production": 1.2,
            },
        )
        signal = await analyst.analyze(input_extra)

        assert "retail_sales" in signal.metadata["indicators_used"]
        assert signal.metadata["indicators"]["retail_sales"] == 0.8
