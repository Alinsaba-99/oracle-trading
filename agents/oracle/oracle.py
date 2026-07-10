"""MarketOracle — regime-aware market state analysis with LLM narrative synthesis.

The regime detection is 100% deterministic (Phase 1 HMM + BOCD + PELT ensemble).
The LLM is used ONLY for narrative text — never for regime decisions.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog
from pydantic import BaseModel

from analytics.regime.config import RegimeSettings
from analytics.regime.detector import RegimeDetector

logger = structlog.get_logger(__name__)


class MarketState(BaseModel, frozen=True):
    """Immutable snapshot of the inferred market state."""

    regime: str
    phase: str
    volatility: str
    liquidity: str
    risk_appetite: str
    narrative: str | None = None


class MarketOracle:
    """Synthesises market state from deterministic regime detection + LLM narrative.

    Parameters
    ----------
    llm_client :
        An async object with a ``structured_call(system, user, return_type)``
        method used for narrative generation.
    regime_detector :
        Pre-configured ``RegimeDetector``.  When ``None`` a default instance
        is created (which is *not* fitted — the first call to ``analyse()``
        will fit it).
    """

    def __init__(
        self,
        llm_client: Any,
        regime_detector: Any | None = None,
        config: Any | None = None,  # noqa: ARG002 — reserved for MASConfig
    ) -> None:
        self._llm = llm_client
        self._detector = regime_detector or RegimeDetector(
            RegimeSettings(hmm_n_states=4, ensemble_min_confidence=0.6)
        )
        self._fitted: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(self, data: Any) -> MarketState:
        """Run regime detection, build state, call LLM for narrative.

        Parameters
        ----------
        data :
            A DataFrame-like object exposing ``data["close"]`` (or
            ``data.close``) as a 1-D numeric sequence.  If the object
            provides a ``.to_numpy()`` method it will be used.

        Returns
        -------
        MarketState
        """
        closes = self._extract_closes(data)

        # Prepare arrays for the RegimeDetector
        returns: np.ndarray = np.diff(closes) / closes[:-1] if len(closes) > 1 else np.array([0.0])
        prices_2d = closes.reshape(-1, 1)

        # Fit on first call
        if not self._fitted:
            self._detector.fit(returns, prices_2d)
            self._fitted = True

        # Deterministic regime detection
        regime_label, _confidence, details = self._detector.detect(returns, prices_2d)

        # Build state from deterministic results
        state = MarketState(
            regime=regime_label,
            phase=self._infer_phase(data),
            volatility=self._infer_volatility(data),
            liquidity="normal",
            risk_appetite="risk_on" if regime_label in ("bull",) else "risk_off",
        )

        # LLM narrative — read-only, never changes state
        try:
            narrative = await self._synthesize_narrative(state, details)
            state = state.model_copy(update={"narrative": narrative})
        except Exception:
            logger.warning("oracle.narrative.failed")

        return state

    # ------------------------------------------------------------------
    # Phase / volatility helpers
    # ------------------------------------------------------------------

    def _infer_phase(self, data: Any) -> str:
        """Simple phase inference from SMA slope.

        Uses two SMA windows over the close series:
        - SMA(50) / SMA(200) comparison for markup / markdown detection.
        """
        closes = self._extract_closes(data)
        if len(closes) < 100:
            return "unknown"

        sma_50 = float(np.mean(closes[-50:]))
        sma_200_short = float(np.mean(closes[-50:]))
        sma_200_long = float(np.mean(closes[:50])) if len(closes) >= 50 else float(np.mean(closes))
        if sma_50 > sma_200_short > sma_200_long:
            return "markup"
        if sma_50 < sma_200_short < sma_200_long:
            return "markdown"
        return "accumulation"

    def _infer_volatility(self, data: Any) -> str:
        """Categorise recent realised volatility as low / medium / high."""
        closes = self._extract_closes(data)
        if len(closes) < 2:
            return "low"

        returns = np.diff(closes) / closes[:-1]
        lookback = min(20, len(returns))
        vol = float(np.std(returns[-lookback:]))

        if vol > 0.03:
            return "high"
        if vol > 0.015:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # LLM narrative
    # ------------------------------------------------------------------

    async def _synthesize_narrative(self, state: MarketState, _details: dict[str, object]) -> str:
        """Call LLM for market narrative — text only, never affects state."""
        system = "Sei un analista di mercato. Descrivi le condizioni attuali in 3-4 frasi."
        user = f"Regime: {state.regime}, Fase: {state.phase}, Volatilita: {state.volatility}"
        result: str = await self._llm.structured_call(system, user, str)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_closes(data: Any) -> np.ndarray:
        """Extract a 1-D numpy array of close prices from *data*."""
        if hasattr(data, "to_numpy"):
            raw = data["close"].to_numpy()
        elif isinstance(data, dict):
            raw = np.asarray(data["close"])
        else:
            raw = np.asarray(data["close"])

        arr: np.ndarray = raw.ravel().astype(np.float64)
        return arr
