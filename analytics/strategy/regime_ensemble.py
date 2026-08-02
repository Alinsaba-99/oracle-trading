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
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from analytics.research.memory import ResearchMemory

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
        memory: ResearchMemory | None = None,
    ) -> None:
        """Args:
        specialists: map ``SpecialistId → signal computer``; must
            expose ``compute(data) -> pl.Series`` (Int8: -1/0/1).
        regime_detector: optional; if None, a simple SMA-based
            heuristic is used (fast, deterministic).
        min_confidence: below this, force ``SpecialistId.FLAT``.
        memory: optional ``ResearchMemory`` for tracking decisions
            and outcomes (BL-090).
        """
        if not specialists:
            raise ValueError("specialists must be non-empty")
        self._specialists = dict(specialists)
        self._regime_detector = regime_detector
        self._min_confidence = min_confidence
        self._last_decision: RoutingDecision | None = None
        self._memory = memory

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

        If ``memory`` is configured, records the routing decision and
        the last signal value for post-hoc outcome tracking.
        """
        decision = self.route(data)
        if decision.specialist == SpecialistId.FLAT:
            sig = pl.Series("signal", [0] * len(data), dtype=pl.Int8)
            _record_decision(self._memory, decision, data)
            return sig
        spec = self._specialists.get(decision.specialist)
        if spec is None:
            logger.warning(f"specialist {decision.specialist} not registered — flat")
            sig = pl.Series("signal", [0] * len(data), dtype=pl.Int8)
            _record_decision(self._memory, decision, data)
            return sig
        result: pl.Series = spec.compute(data)  # type: ignore[attr-defined]
        _record_decision(
            self._memory, decision, data, signal=int(result[-1]) if len(result) > 0 else 0
        )
        return result

    # ── compute_specialist ──────────────────────────────────────────────
    def compute_specialist(self, data: pl.DataFrame, specialist_id: SpecialistId) -> pl.Series:
        """Compute signal from a single named specialist, bypassing routing.

        Used by AdaptiveEnsemble to get individual signals for weighted
        combination instead of binary routing.

        Args:
            data: OHLCV DataFrame with close column.
            specialist_id: Which specialist to invoke.

        Returns:
            Signal Series from that specialist.  Returns zeros if the
            specialist is not registered.
        """
        spec = self._specialists.get(specialist_id)
        if spec is None:
            return pl.Series("signal", [0] * len(data), dtype=pl.Int8)
        try:
            result = spec.compute(data)  # type: ignore[attr-defined]
        except Exception:
            return pl.Series("signal", [0] * len(data), dtype=pl.Int8)
        return pl.Series("signal", result) if not isinstance(result, pl.Series) else result

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

    def _try_pick(self, cand: SpecialistId, data: pl.DataFrame | None) -> SpecialistId | None:
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


#: SMA separation, in units of per-bar volatility, above which the market is
#: called trending. Expressing the gate in vol units rather than raw percent is
#: what makes it timeframe-invariant: a 2.5% SMA50/SMA100 gap is a strong daily
#: trend but a huge, near-unreachable move on 1h bars, so the old absolute
#: thresholds classified ~92% of 1h data as choppy and starved every
#: trend specialist of routing. See G6 regime-bias finding.
#: Calibrated by sweeping thresholds over EURUSD/XAUUSD/USDJPY/BTCUSDT at 1h
#: and 1d (~48k windows) against the documented target mix
#: bull 10-30% / bear 5-20% / choppy 40-60% / volatile 10-20%. These land at
#: bull 18% / bear 16% / choppy 56% / volatile 10%, and hold on every
#: instrument/timeframe pair tested without per-market retuning.
_TREND_LONG_SIGMA = 0.45
_TREND_SHORT_SIGMA = 0.60
_VOL_RATIO_TREND = 1.35


def _confidence(value: float, threshold: float) -> float:
    """Map a metric that just cleared ``threshold`` onto [0.55, 1.0].

    A regime is only reported once its gate is passed, so the weakest possible
    reading still deserves usable confidence. Scaling by ``value / (3 *
    threshold)`` instead put a freshly-triggered trend at ~0.33 — under the
    0.5 routing gate — so detected trends were immediately forced back to FLAT
    and no trend specialist could ever be selected.
    """
    excess = (value - threshold) / max(threshold, 1e-9)
    return max(0.55, min(1.0, 0.55 + 0.45 * min(1.0, excess)))


def _sma_regime_heuristic(data: pl.DataFrame) -> tuple[RegimeLabel, float]:
    """Deterministic regime heuristic: SMA fast vs SMA slow + realized vol.

    Trend gates are scaled by realized per-bar volatility, so the same
    thresholds hold on 1h, 4h, and 1d without recalibration. An SMA gap is
    compared against how far price typically drifts over the averaging span
    (``sigma * sqrt(span)``), which is the scale a random walk would produce
    by chance — so exceeding it is evidence of actual directional drift.
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

    # Expected drift of an SMA pair separated by ~span bars under a random
    # walk of per-bar vol `long_vol`. Guarded so a flat series cannot make
    # every comparison trivially true.
    long_scale = max(long_vol * math.sqrt(50.0), 1e-9)
    short_scale = max(long_vol * math.sqrt(20.0), 1e-9)
    long_sigma = trend_strength_long / long_scale
    short_sigma = trend_strength / short_scale

    if vol_ratio > _VOL_RATIO_TREND:
        return RegimeLabel.VOLATILE, _confidence(vol_ratio, _VOL_RATIO_TREND)
    if long_sigma > _TREND_LONG_SIGMA:
        label = RegimeLabel.BULL if sma50 > sma100 else RegimeLabel.BEAR
        return label, _confidence(long_sigma, _TREND_LONG_SIGMA)
    if short_sigma > _TREND_SHORT_SIGMA:
        label = RegimeLabel.BULL if sma20 > sma50 else RegimeLabel.BEAR
        return label, _confidence(short_sigma, _TREND_SHORT_SIGMA)
    # Further below the trend gate = more clearly rangebound.
    return RegimeLabel.CHOPPY, max(0.55, min(1.0, 1.0 - long_sigma / _TREND_LONG_SIGMA * 0.45))


# ── ResearchMemory hook (BL-090) ────────────────────────────────────────


def _record_decision(
    memory: ResearchMemory | None, decision: RoutingDecision, data: pl.DataFrame, signal: int = 0
) -> None:
    """Record the routing decision in ResearchMemory if configured."""
    if memory is None:
        return
    close_col = next((c for c in data.columns if c.lower() in ("close", "adj_close")), None)
    close = float(data[close_col][-1]) if close_col is not None and len(data) > 0 else None
    vol: float | None = None
    if close_col is not None and len(data) > 20:
        returns = (data[close_col].to_numpy()[1:] / data[close_col].to_numpy()[:-1]) - 1.0
        vol = float(returns[-20:].std()) if len(returns) >= 20 else None
    features = {}
    if close is not None:
        features["close"] = close
    if vol is not None:
        features["volatility"] = vol
    features["n_bars"] = len(data)
    memory.record_decision(
        regime=decision.regime.value,
        regime_confidence=decision.regime_confidence,
        specialist=decision.specialist.value,
        reason=decision.reason,
        signal=signal,
        features=features,
    )


__all__ = ["RegimeAwareEnsemble", "RegimeLabel", "RoutingDecision", "SpecialistId"]
