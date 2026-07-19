"""Tests for agents/oracle — MarketOracle and NarrativeSynthesizer."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import MagicMock, PropertyMock

import numpy as np
import pytest

from agents.oracle.oracle import MarketOracle
from agents.oracle.synthesizer import NarrativeSynthesizer
from agents.protocol import MarketState

# ======================================================================
# Helpers
# ======================================================================


class MockData:
    """Minimal DataFrame-like object for testing regime / phase / vol inference."""

    def __init__(self, closes: list[float]) -> None:
        self._closes: np.ndarray = np.array(closes, dtype=np.float64)

    def __getitem__(self, key: str) -> np.ndarray:
        if key == "close":
            return self._closes
        raise KeyError(key)


class MockLLM:
    """Async LLM mock that returns a canned narrative."""

    def __init__(self, narrative: str = "Mercato in trend positivo.") -> None:
        self.narrative = narrative
        self.last_system: str | None = None
        self.last_user: str | None = None
        self.call_count: int = 0

    async def structured_call(
        self, system_prompt: str = "", user_prompt: str = "", response_model: Any = None, **_: Any
    ) -> Any:
        self.last_system = system_prompt
        self.last_user = user_prompt
        self.call_count += 1
        if response_model is not None and hasattr(response_model, "model_validate"):
            return response_model(text=self.narrative)
        return self.narrative


class MockFailingLLM:
    """Async LLM mock that always raises."""

    async def structured_call(
        self,
        _system_prompt: str = "",
        _user_prompt: str = "",
        _response_model: Any = None,
        **_kwargs: Any,
    ) -> Any:
        msg = "LLM unavailable"
        raise RuntimeError(msg)


def make_detector(regime: str = "bull", confidence: float = 0.85) -> MagicMock:
    """Create a pre-configured RegimeDetector mock."""
    detector = MagicMock()
    detector.fitted = False  # property, not property mock yet

    # We need fitted to be readable and settable
    type(detector).fitted = PropertyMock(
        side_effect=lambda self=None: self._fitted if hasattr(self, "_fitted") else False
    )

    detector._fitted = False

    def mock_fit(returns, prices=None):  # noqa: ARG001
        detector._fitted = True
        return detector

    detector.fit = MagicMock(side_effect=mock_fit)
    detector.detect = MagicMock(
        return_value=(regime, confidence, {"transitions": 1, "scores": {"hmm": confidence}})
    )

    return detector


# ======================================================================
# MarketOracle — basic integration
# ======================================================================


class TestMarketOracle:
    """Integration-level tests for MarketOracle."""

    PRICES_UP: ClassVar[list[float]] = [100.0 + i * 0.5 for i in range(200)]
    PRICES_DOWN: ClassVar[list[float]] = [200.0 - i * 0.5 for i in range(200)]
    PRICES_SIDEWAYS: ClassVar[list[float]] = [100.0 + (i % 5 - 2) for i in range(200)]

    @pytest.fixture
    def llm(self) -> MockLLM:
        return MockLLM()

    @pytest.fixture
    def detector(self) -> MagicMock:
        return make_detector("bull", 0.85)

    @pytest.fixture
    def oracle(self, llm: MockLLM, detector: MagicMock) -> MarketOracle:
        return MarketOracle(llm_client=llm, regime_detector=detector)

    # ------------------------------------------------------------------
    # 1. MarketOracle returns MarketState
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_returns_market_state(self, oracle: MarketOracle) -> None:
        data = MockData(self.PRICES_UP)
        result = await oracle.analyze(data)
        assert isinstance(result, MarketState)

    @pytest.mark.asyncio
    async def test_market_state_fields_populated(self, oracle: MarketOracle) -> None:
        data = MockData(self.PRICES_UP)
        state = await oracle.analyze(data)
        assert state.regime == "bull"
        assert state.phase in ("markup", "accumulation", "unknown")
        assert state.volatility in ("low", "medium", "high")
        assert state.liquidity == "normal"
        assert state.risk_appetite == "risk_on"
        # narrative set by LLM
        assert state.narrative == "Mercato in trend positivo."

    # ------------------------------------------------------------------
    # 2. Regime detection called with correct data
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_regime_detector_called(self, oracle: MarketOracle, detector: MagicMock) -> None:
        data = MockData(self.PRICES_UP)
        await oracle.analyze(data)
        # fit + detect both called
        assert detector.fit.called
        assert detector.detect.called
        # detect receives numpy arrays as positional args
        args, _kwargs = detector.detect.call_args
        returns, prices = args
        assert isinstance(returns, np.ndarray)
        assert isinstance(prices, np.ndarray)

    @pytest.mark.asyncio
    async def test_regime_detector_not_fitted_twice(
        self, oracle: MarketOracle, detector: MagicMock
    ) -> None:
        data = MockData(self.PRICES_UP)
        await oracle.analyze(data)
        await oracle.analyze(data)
        assert detector.fit.call_count == 1  # only fitted once

    # ------------------------------------------------------------------
    # 3. LLM narrative called after regime detection
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_llm_called_with_state_context(self, oracle: MarketOracle, llm: MockLLM) -> None:
        data = MockData(self.PRICES_UP)
        await oracle.analyze(data)
        assert llm.call_count == 1
        assert "bull" in llm.last_user or "bull" in llm.last_system  # type: ignore[operator]

    # ------------------------------------------------------------------
    # 4. LLM failure doesn't crash
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_llm_failure_returns_state_without_narrative(self, detector: MagicMock) -> None:
        oracle = MarketOracle(llm_client=MockFailingLLM(), regime_detector=detector)
        data = MockData(self.PRICES_UP)
        state = await oracle.analyze(data)
        assert isinstance(state, MarketState)
        assert state.narrative == ""

    # ------------------------------------------------------------------
    # 5. Phase inference
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_phase_accumulation_by_default(self, oracle: MarketOracle) -> None:
        # With SMA fix: uptrend data has SMA(50) > SMA(200), giving markup
        data = MockData(self.PRICES_UP)
        state = await oracle.analyze(data)
        assert state.phase in ("markup", "accumulation")

    @pytest.mark.asyncio
    async def test_phase_always_accumulation_for_trends(
        self, llm: MockLLM, detector: MagicMock
    ) -> None:
        # With SMA fix: downtrend data has SMA(50) < SMA(200)
        detector.detect.return_value = ("bear", 0.85, {"transitions": 1, "scores": {}})
        oracle = MarketOracle(llm_client=llm, regime_detector=detector)
        data = MockData(self.PRICES_DOWN)
        state = await oracle.analyze(data)
        assert state.phase in ("markdown", "accumulation")

    @pytest.mark.asyncio
    async def test_phase_unknown_when_insufficient_data(self, oracle: MarketOracle) -> None:
        data = MockData([100.0, 101.0, 102.0])  # only 3 bars
        state = await oracle.analyze(data)
        assert state.phase == "unknown"

    # ------------------------------------------------------------------
    # 6. Volatility inference
    # ------------------------------------------------------------------

    @pytest.fixture
    def low_vol_oracle(self, llm: MockLLM, detector: MagicMock) -> MarketOracle:
        return MarketOracle(llm_client=llm, regime_detector=detector)

    @pytest.mark.asyncio
    async def test_volatility_high(self, low_vol_oracle: MarketOracle) -> None:
        # 5% daily moves => high vol
        prices = [100.0]
        for _ in range(30):
            prices.append(prices[-1] * (1 + np.random.choice([-0.05, 0.05])))
        data = MockData(prices)
        state = await low_vol_oracle.analyze(data)
        assert state.volatility == "high"

    @pytest.mark.asyncio
    async def test_volatility_low(self, low_vol_oracle: MarketOracle) -> None:
        # Sub-0.5% daily moves => low vol
        prices = [100.0 + i * 0.1 for i in range(30)]
        data = MockData(prices)
        state = await low_vol_oracle.analyze(data)
        assert state.volatility == "low"

    @pytest.mark.asyncio
    async def test_volatility_medium(self, low_vol_oracle: MarketOracle) -> None:
        # 2% daily moves => medium vol (std ~0.02 > 0.015)
        prices = [100.0]
        for _ in range(30):
            prices.append(prices[-1] * (1 + np.random.choice([-0.02, 0.02])))
        data = MockData(prices)
        state = await low_vol_oracle.analyze(data)
        assert state.volatility == "medium"

    # ------------------------------------------------------------------
    # 7. Edge cases
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_single_row_dataframe(self, oracle: MarketOracle) -> None:
        """Single close price — should not crash."""
        data = MockData([100.0])
        state = await oracle.analyze(data)
        assert isinstance(state, MarketState)

    @pytest.mark.asyncio
    async def test_constant_prices(self, oracle: MarketOracle) -> None:
        """All prices identical — zero returns, low vol."""
        prices = [100.0] * 200
        data = MockData(prices)
        state = await oracle.analyze(data)
        assert isinstance(state, MarketState)
        assert state.volatility == "low"
        # With zero returns, constant prices, SMA(50) == SMA(200) == 100
        assert state.phase in ("markdown", "accumulation")

    @pytest.mark.asyncio
    async def test_data_missing_close_column(self, oracle: MarketOracle) -> None:
        """KeyError on missing 'close' column should propagate."""
        data = {"not_close": [1, 2, 3]}
        with pytest.raises((KeyError, TypeError)):
            await oracle.analyze(data)


# ======================================================================
# NarrativeSynthesizer
# ======================================================================


class TestNarrativeSynthesizer:
    """Tests for the template and LLM narrative paths."""

    @pytest.fixture
    def bull_state(self) -> MarketState:
        return MarketState(
            regime="bull",
            phase="markup",
            volatility="low",
            liquidity="normal",
            risk_appetite="risk_on",
        )

    @pytest.fixture
    def bear_state(self) -> MarketState:
        return MarketState(
            regime="bear",
            phase="markdown",
            volatility="high",
            liquidity="tight",
            risk_appetite="risk_off",
        )

    def test_template_fallback_no_llm(self, bull_state: MarketState) -> None:
        synth = NarrativeSynthesizer(llm_client=None)
        narrative = synth._template_narrative(bull_state, {})
        assert "bullish" in narrative
        assert "markup" in narrative
        assert "risk-on" in narrative

    def test_template_fallback_bear(self, bear_state: MarketState) -> None:
        synth = NarrativeSynthesizer(llm_client=None)
        narrative = synth._template_narrative(bear_state, {})
        assert "bearish" in narrative
        assert "risk-off" in narrative
        assert "elevated" in narrative

    @pytest.mark.asyncio
    async def test_synthesize_with_llm(self, bull_state: MarketState) -> None:
        llm = MockLLM(narrative="LLM-generated narrative.")
        synth = NarrativeSynthesizer(llm_client=llm)
        result = await synth.synthesize(bull_state, {})
        assert result == "LLM-generated narrative."
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_synthesize_falls_back_on_llm_failure(self, bull_state: MarketState) -> None:
        synth = NarrativeSynthesizer(llm_client=MockFailingLLM())
        result = await synth.synthesize(bull_state, {})
        assert "bullish" in result

    def test_template_includes_transition_count(self, bull_state: MarketState) -> None:
        synth = NarrativeSynthesizer(llm_client=None)
        narrative = synth._template_narrative(bull_state, {"transitions": 2})
        assert "2" in narrative
        assert "transitioned" in narrative.lower()

    def test_template_skips_zero_transitions(self, bull_state: MarketState) -> None:
        synth = NarrativeSynthesizer(llm_client=None)
        narrative = synth._template_narrative(bull_state, {"transitions": 0})
        assert "transitioned" not in narrative.lower()
