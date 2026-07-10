"""Tests for TechnicalAnalyst — signal generation, edge cases, and independence."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agents.analysts.technical import TechnicalAnalyst, TechnicalResponse
from agents.config import MASConfig
from agents.protocol import AnalystInput, AnalystSignal


class _MockLLM:
    """Minimal mock LLM client for testing TechnicalAnalyst."""

    def __init__(self, response: TechnicalResponse | None = None) -> None:
        self._response = response or TechnicalResponse(
            direction="buy", confidence=0.75, reasoning="Mock analysis"
        )
        self.call_count = 0

    @property
    def model_name(self) -> str:
        return "mock-technical"

    async def structured_call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        temperature: float = 0.1,
        timeout_s: float = 30.0,
    ) -> BaseModel:
        self.call_count += 1
        _ = system_prompt, user_prompt, response_model, temperature, timeout_s
        return self._response

    async def count_tokens(self, text: str) -> int:
        return len(text) // 4


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> _MockLLM:
    return _MockLLM()


@pytest.fixture
def config() -> MASConfig:
    return MASConfig()


@pytest.fixture
def analyst(mock_llm: _MockLLM, config: MASConfig) -> TechnicalAnalyst:
    return TechnicalAnalyst(llm_client=mock_llm, config=config)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_input(instrument: str = "AAPL", data: dict[str, Any] | None = None) -> AnalystInput:
    return AnalystInput(
        instrument=instrument, market_state={"regime": "neutral"}, agent_specific_data=data or {}
    )


# ── Tests ────────────────────────────────────────────────────────────────────


class TestTechnicalAnalyst:
    """Tests for TechnicalAnalyst signal generation."""

    async def test_returns_buy_signal(self, analyst: TechnicalAnalyst) -> None:
        """Direction 'buy' is reflected in the returned signal."""
        data = _make_input(
            data={
                "rsi": 35,
                "macd": {"macd": 1.2, "signal": 0.8, "histogram": 0.4},
                "bollinger_bands": {"upper": 210, "middle": 200, "lower": 190},
                "price": 192,
                "sma_50": 195,
                "sma_200": 185,
                "volume": {"relative": 1.3},
            }
        )
        signal = await analyst.analyze(data)
        assert isinstance(signal, AnalystSignal)
        assert signal.vote.direction == "buy"
        assert signal.source == "technical"
        assert signal.vote.confidence == 0.75
        assert signal.vote.reasoning == "Mock analysis"

    async def test_returns_sell_signal(self) -> None:
        """Direction 'sell' from LLM is reflected in the signal."""
        mock_llm = _MockLLM(
            response=TechnicalResponse(
                direction="sell", confidence=0.6, reasoning="Bearish pattern"
            )
        )
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        data = _make_input(
            data={"rsi": 75, "macd": {"macd": 0.5, "signal": 0.9, "histogram": -0.4}}
        )
        signal = await tech.analyze(data)
        assert signal.vote.direction == "sell"
        assert signal.vote.confidence == 0.6
        assert "Bearish" in signal.vote.reasoning

    async def test_returns_hold_signal(self) -> None:
        """Direction 'hold' from LLM is reflected in the signal."""
        mock_llm = _MockLLM(
            response=TechnicalResponse(direction="hold", confidence=0.3, reasoning="Mixed signals")
        )
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        data = _make_input(data={"rsi": 50, "macd": {"macd": 1.0, "signal": 1.0, "histogram": 0.0}})
        signal = await tech.analyze(data)
        assert signal.vote.direction == "hold"
        assert signal.vote.confidence == 0.3

    async def test_handles_missing_indicators(self) -> None:
        """Missing indicators produce a valid signal with defaults."""
        mock_llm = _MockLLM()
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        data = _make_input(data={"rsi": 42})
        signal = await tech.analyze(data)
        assert isinstance(signal, AnalystSignal)
        assert "rsi" in signal.metadata.get("indicators", {})
        assert signal.vote.direction in ("buy", "sell", "hold")

    async def test_blind_spot_returns_expected_string(self) -> None:
        """Blind spot describes what the analyst ignores."""
        mock_llm = _MockLLM()
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        assert tech.blind_spot == "Ignora fondamentali e macro — analizza solo prezzo e volumi"

    async def test_name_returns_technical(self) -> None:
        """Name property returns 'technical'."""
        mock_llm = _MockLLM()
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        assert tech.name == "technical"

    async def test_metadata_contains_indicators(self, analyst: TechnicalAnalyst) -> None:
        """Signal metadata includes the original indicators dict."""
        indicators = {"rsi": 62, "volume": {"relative": 0.9}}
        data = _make_input(data=indicators)
        signal = await analyst.analyze(data)
        assert signal.metadata.get("indicators") == indicators

    async def test_blind_spot_in_signal(self, analyst: TechnicalAnalyst) -> None:
        """Blind spot is attached to the returned signal."""
        data = _make_input()
        signal = await analyst.analyze(data)
        assert signal.blind_spot == analyst.blind_spot

    async def test_empty_data_edge_case(self) -> None:
        """Empty agent_specific_data produces a valid signal."""
        mock_llm = _MockLLM()
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        data = _make_input(data={})
        signal = await tech.analyze(data)
        assert isinstance(signal, AnalystSignal)
        assert signal.vote.direction in ("buy", "sell", "hold")

    async def test_multiple_calls_independent(self) -> None:
        """Each call uses the indicators from its own input."""
        mock_llm = _MockLLM()
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        data1 = _make_input(data={"rsi": 25})
        data2 = _make_input(data={"rsi": 80})

        signal1 = await tech.analyze(data1)
        signal2 = await tech.analyze(data2)

        assert signal1.metadata["indicators"]["rsi"] == 25
        assert signal2.metadata["indicators"]["rsi"] == 80

    async def test_risk_score_propagated(self) -> None:
        """Optional risk_score from LLM is propagated to AgentVote."""
        mock_llm = _MockLLM(
            response=TechnicalResponse(
                direction="sell", confidence=0.8, reasoning="Risky", risk_score=0.6
            )
        )
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        data = _make_input()
        signal = await tech.analyze(data)
        assert signal.vote.risk_score == 0.6

    async def test_signal_default_fields(self) -> None:
        """AnalystSignal has default fields populated correctly."""
        mock_llm = _MockLLM()
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        data = _make_input()
        signal = await tech.analyze(data)
        assert signal.model == ""
        assert signal.tokens_used == 0
        assert signal.prompt_hash == ""

    async def test_prompt_includes_indicators(self) -> None:
        """_build_prompt formats indicator values correctly."""
        mock_llm = _MockLLM()
        tech = TechnicalAnalyst(llm_client=mock_llm, config=MASConfig())
        prompt = tech._build_prompt("TEST", {"rsi": 72, "sma_50": 100, "sma_200": 90})
        assert "RSI(14): 72" in prompt
        assert "Ipercomprato" in prompt
        assert "SMA(50): 100" in prompt
        assert "SMA(200): 90" in prompt
        assert "Trend rialzista" in prompt

    async def test_mock_llm_call_count(self, analyst: TechnicalAnalyst, mock_llm: _MockLLM) -> None:
        """Each analyze call increments the LLM call count."""
        data = _make_input()
        assert mock_llm.call_count == 0
        await analyst.analyze(data)
        assert mock_llm.call_count == 1
        await analyst.analyze(data)
        assert mock_llm.call_count == 2
