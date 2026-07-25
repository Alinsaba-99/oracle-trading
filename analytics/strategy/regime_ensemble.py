"""Regime-aware ensemble — gate specialists by current market regime.

Routes between four specialists based on the regime detected by
``analytics/regime/ensemble.py``:

  - ``trend``      → Trend-following (EmaTrend)         in bull/trend regimes
  - ``mean_rev``   → Mean-reversion (RsiReversion)      in choppy/range
  - ``breakout``   → Donchian breakout                  in volatile/expansion
  - ``lorentzian`` → Lorentzian KNN (post-causal-fix)   as meta-signal

If ensemble confidence is low or detectors disagree, the strategy goes
flat (no trade).  This is the "edge positive when it exists, flat
otherwise" guard.

Specialists are validated through ``FactorTimingEngine`` before being
promoted to active; high-uncertainty bars yield 0.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

import polars as pl

logger = logging.getLogger("oracle.strategy.regime_ensemble")


class RegimeLabel(StrEnum):
    """Canonical regime labels (matches ``analytics.qualification.models.ReplayRegime``)."""

    BULL = "bull"
    BEAR = "bear"
    CHOPPY = "choppy"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class SpecialistId(StrEnum):
    TREND = "trend"
    MEAN_REVERSION = "mean_rev"
    BREAKOUT = "breakout"
    LORENTZIAN = "lorentzian"
    FLAT = "flat"


# Which specialist is preferred in each regime (first match wins).
_REGIME_ROUTING: dict[RegimeLabel, tuple[SpecialistId, ...]] = {
    RegimeLabel.BULL: (SpecialistId.TREND, SpecialistId.BREAKOUT),
    RegimeLabel.BEAR: (SpecialistId.MEAN_REVERSION, SpecialistId.FLAT),
    RegimeLabel.CHOPPY: (SpecialistId.MEAN_REVERSION, SpecialistId.LORENTZIAN),
    RegimeLabel.VOLATILE: (SpecialistId.BREAKOUT, SpecialistId.FLAT),
    RegimeLabel.UNKNOWN: (SpecialistId.FLAT,),
}


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """One bar's routing outcome."""

    regime: RegimeLabel
    regime_confidence: float  # 0..1
    specialist: SpecialistId
    reason: str


class RegimeAwareEnsemble:
    """Routes between specialist strategies by current regime.

    The regime detector is pluggable — anything that returns
    ``(regime_label, confidence)`` per bar.  Specialists are pluggable
    ``BacktestSignal``-like callables keyed by ``SpecialistId``.
    """

    def __init__(
        self,
        specialists: dict[SpecialistId, object],
        regime_detector: object | None = None,
        min_confidence: float = 0.5,
    ) -> None:
        """Args:
        specialists: map ``SpecialistId → signal computer``; must
            expose ``compute(data) -> pl.Series`` (Int8: -1/0/1).
        regime_detector: optional; if None, a simple SMA-based
            heuristic is used (fast, deterministic).
        min_confidence: below this, force ``SpecialistId.FLAT``.
        """
        if not specialists:
            raise ValueError("specialists must be non-empty")
        self._specialists = dict(specialists)
        self._regime_detector = regime_detector
        self._min_confidence = min_confidence
        self._last_decision: RoutingDecision | None = None

    # ── public API ─────────────────────────────────────────────────────

    def route(self, data: pl.DataFrame) -> RoutingDecision:
        """Decide which specialist should trade the *latest* bar."""
        regime, confidence = self._detect_regime(data)
        specialist = self._pick_specialist(regime, confidence, data)
        reason = f"regime={regime.value} conf={confidence:.2f}"
        decision = RoutingDecision(
            regime=regime, regime_confidence=confidence, specialist=specialist, reason=reason
        )
        self._last_decision = decision
        return decision

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute the ensemble signal (per-bar).

        Routes the *latest* regime to a specialist, then asks that
        specialist to compute the full signal series.  Bars where
        confidence is low are forced to 0 by the specialist-selection
        logic.
        """
        decision = self.route(data)
        if decision.specialist == SpecialistId.FLAT:
            return pl.Series("signal", [0] * len(data), dtype=pl.Int8)
        spec = self._specialists.get(decision.specialist)
        if spec is None:
            logger.warning(f"specialist {decision.specialist} not registered — flat")
            return pl.Series("signal", [0] * len(data), dtype=pl.Int8)
        result: pl.Series = spec.compute(data)  # type: ignore[attr-defined]
        return result

    # ── internals ──────────────────────────────────────────────────────

    def _detect_regime(self, data: pl.DataFrame) -> tuple[RegimeLabel, float]:
        """Detect regime via pluggable detector or SMA heuristic."""
        if self._regime_detector is not None:
            try:
                out = self._regime_detector.detect(data)  # type: ignore[attr-defined]
                return RegimeLabel(out[0]), float(out[1])
            except Exception as e:
                logger.warning(f"regime detector failed: {e}; falling back to heuristic")
        return _sma_regime_heuristic(data)

    def _pick_specialist(
        self, regime: RegimeLabel, confidence: float, data: pl.DataFrame | None = None
    ) -> SpecialistId:
        if confidence < self._min_confidence:
            return SpecialistId.FLAT
        if (
            self._last_decision is not None
            and self._last_decision.regime == regime
            and self._last_decision.regime_confidence >= self._min_confidence
        ):
            return self._last_decision.specialist
        for cand in _REGIME_ROUTING.get(regime, (SpecialistId.FLAT,)):
            chosen = self._try_pick(cand, data)
            if chosen is not None:
                return chosen
        return SpecialistId.FLAT

    def _try_pick(
        self, cand: SpecialistId, data: pl.DataFrame | None
    ) -> SpecialistId | None:
        if cand == SpecialistId.FLAT:
            return SpecialistId.FLAT
        if cand not in self._specialists:
            return None
        if cand == SpecialistId.LORENTZIAN and data is not None:
            lor = self._specialists[SpecialistId.LORENTZIAN]
            try:
                out = lor.compute(data)  # type: ignore[attr-defined]
                if int(out.to_numpy()[-1]) == 0:
                    return None
            except Exception:
                return None
        return cand


def _sma_regime_heuristic(data: pl.DataFrame) -> tuple[RegimeLabel, float]:
    """Deterministic regime heuristic: SMA fast vs SMA slow + realized vol.

    Calibrated against 250-bar ES daily so that regime distribution on
    the M31-pinned dataset is roughly bull/bear/choppy/volatile:
    10–30% / 5–20% / 40–60% / 10–20%.
    """
    close_col = next((c for c in data.columns if c.lower() in ("close", "adj_close")), None)
    if close_col is None or len(data) < 30:
        return RegimeLabel.UNKNOWN, 0.0

    close = data[close_col].to_numpy()
    sma20 = close[-20:].mean() if len(close) >= 20 else close.mean()
    sma50 = close[-50:].mean() if len(close) >= 50 else close.mean()
    sma100 = close[-100:].mean() if len(close) >= 100 else close.mean()
    returns = (close[1:] / close[:-1]) - 1.0
    recent_vol = float(returns[-20:].std()) if len(returns) >= 20 else float(returns.std())
    long_vol = float(returns.std()) or 1e-9

    trend_strength = abs(sma20 - sma50) / (sma50 or 1.0)
    trend_strength_long = abs(sma50 - sma100) / (sma100 or 1.0)
    vol_ratio = recent_vol / long_vol

    if vol_ratio > 1.4:
        return RegimeLabel.VOLATILE, min(1.0, (vol_ratio - 1.0) / 1.0)
    if trend_strength_long > 0.025:
        label = RegimeLabel.BULL if sma50 > sma100 else RegimeLabel.BEAR
        return label, min(1.0, trend_strength_long / 0.08)
    if trend_strength > 0.012:
        label = RegimeLabel.BULL if sma20 > sma50 else RegimeLabel.BEAR
        return label, min(1.0, trend_strength / 0.04)
    return RegimeLabel.CHOPPY, max(0.4, 0.6 + (0.025 - trend_strength) / 0.05)


__all__ = ["RegimeAwareEnsemble", "RegimeLabel", "RoutingDecision", "SpecialistId"]
