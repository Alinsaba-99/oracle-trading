"""NarrativeSynthesizer — builds structured market narratives from regime state + scores.

Can run with or without an LLM client.  When no client is available or the
call fails, a template-based fallback narrative is returned.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from agents.protocol import MarketState
from core.logging import get_logger


class _NarrativeResponse(BaseModel):
    text: str


logger = get_logger(__name__)


class NarrativeSynthesizer:
    """Builds human-readable market narratives.

    Parameters
    ----------
    llm_client :
        Optional async client with a ``structured_call(system, user, return_type)``
        method.  When ``None`` only the template fallback is used.
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def synthesize(self, state: MarketState, details: dict[str, object]) -> str:
        """Return a narrative string for the given market state.

        Attempts an LLM-generated narrative when a client is available;
        falls back to a deterministic template on failure or when no LLM
        is configured.
        """
        if self._llm is not None:
            try:
                return await self._llm_narrative(state, details)
            except Exception:
                logger.warning("synthesizer.llm.failed")

        return self._template_narrative(state, details)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    async def _llm_narrative(self, state: MarketState, details: dict[str, object]) -> str:
        """Build and issue an LLM prompt for the narrative."""
        system = (
            "You are a senior financial analyst. "
            "Describe the current market conditions in 3-4 concise sentences. "
            "Be specific about regime, phase, and risk posture."
        )
        user = (
            f"Regime: {state.regime}\n"
            f"Phase: {state.phase}\n"
            f"Volatility: {state.volatility}\n"
            f"Risk appetite: {state.risk_appetite}\n"
            f"Liquidity: {state.liquidity}\n"
        )
        if details:
            scores = {k: v for k, v in details.items() if isinstance(v, (int, float))}
            if scores:
                user += f"Scores: {scores}\n"
        assert self._llm is not None
        result = await self._llm.structured_call(
            system_prompt=system, user_prompt=user, response_model=_NarrativeResponse
        )
        return result.text  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Template fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _template_narrative(state: MarketState, details: dict[str, object]) -> str:
        """Deterministic template narrative based solely on *state*."""
        regime_desc = {
            "bull": "The market is in a bullish regime with strong upward momentum.",
            "bear": "The market is in a bearish regime with persistent selling pressure.",
            "choppy": "The market is range-bound with no clear directional bias.",
            "volatile": "The market is experiencing elevated volatility and uncertainty.",
        }.get(state.regime, f"The market regime is {state.regime}.")

        phase_desc = {
            "markup": "Prices are in a markup phase, suggesting accumulation is complete.",
            "markdown": "Prices are in a markdown phase, indicating distribution is underway.",
            "accumulation": "The market appears to be in an accumulation phase.",
            "unknown": "The phase is not yet determinable from available data.",
        }.get(state.phase, "")

        vol_desc = {
            "high": "Volatility is elevated. Wider stops and reduced sizing are advisable.",
            "medium": "Volatility is moderate — normal risk parameters apply.",
            "low": "Volatility is low, which may precede a breakout expansion.",
        }.get(state.volatility, "")

        risk_line = (
            "The environment favours risk-on positioning."
            if state.risk_appetite == "risk_on"
            else "A defensive, risk-off posture is warranted."
        )

        transitions = details.get("transitions", 0)
        transition_line = (
            f" The regime has transitioned {transitions} time(s) in the lookback window."
            if isinstance(transitions, int) and transitions > 0
            else ""
        )

        return " ".join(
            part for part in (regime_desc, phase_desc, vol_desc, risk_line, transition_line) if part
        )
