"""Evolving weight optimizer — dynamic specialist weights from recent performance.

Updates the AdaptiveEnsemble weight matrix in real-time based on
per-specialist Sharpe over a rolling window.  This gives the ensemble
the "evolutiva" property: weights shift as market conditions change.

Usage::

    from analytics.strategy.weight_evolver import WeightEvolver

    evolver = WeightEvolver(window=50, min_data=20)
    evolver.update("ES", "1d", sharpes_by_specialist)
    weights = evolver.get_weights("ES", "1d", regime)
"""

from __future__ import annotations

from collections import defaultdict

from analytics.strategy.regime_ensemble import RegimeLabel, SpecialistId


class WeightEvolver:
    """Rolling-window performance tracker that evolves specialist weights.

    Maintains a per-(asset, tf, regime, specialist) performance history
    and computes optimal weights from recent Sharpe scores.

    The decay factor ensures older performance data is gradually
    forgotten, making the system responsive to changing conditions.

    Args:
        window: Number of recent performance records to keep.
        min_data: Minimum records before using evolved weights.
        decay: Exponential decay factor for old records (0..1).
    """

    def __init__(self, window: int = 50, min_data: int = 20, decay: float = 0.95) -> None:
        self._window = window
        self._min_data = min_data
        self._decay = decay
        # Key: (asset, tf, regime, specialist) → list of Sharpe values
        self._history: dict[tuple[str, str, RegimeLabel, SpecialistId], list[float]] = defaultdict(
            list
        )

    def update(
        self,
        asset: str,
        timeframe: str,
        specialist: SpecialistId,
        regime: RegimeLabel,
        sharpe: float,
    ) -> None:
        """Record a Sharpe value for a (asset, tf, regime, specialist) combo.

        Args:
            asset: Trading symbol (e.g. "ES").
            timeframe: Bar timeframe (e.g. "1d").
            specialist: Which specialist was used.
            regime: Regime at the time of trading.
            sharpe: Realised Sharpe for that session/period.
        """
        key = (asset.upper(), timeframe, regime, specialist)
        history = self._history[key]
        history.append(sharpe)
        # Keep only recent window
        if len(history) > self._window:
            self._history[key] = history[-self._window :]

    def get_average_sharpe(
        self, asset: str, timeframe: str, regime: RegimeLabel, specialist: SpecialistId
    ) -> float:
        """Compute average Sharpe for a combo, with exponential decay."""
        key = (asset.upper(), timeframe, regime, specialist)
        history = self._history.get(key, [])
        if len(history) < 3:
            return 0.0

        # Weighted average with decay (more recent = higher weight)
        weights = [self._decay ** (len(history) - i - 1) for i in range(len(history))]
        total_w = sum(weights)
        if total_w <= 0:
            return 0.0
        avg = sum(s * w for s, w in zip(history, weights, strict=False)) / total_w
        return avg

    def get_weights(
        self, asset: str, timeframe: str, regime: RegimeLabel
    ) -> dict[SpecialistId, float]:
        """Compute evolved weights for (asset, tf, regime).

        Uses recent performance data to adjust from static weights.
        If insufficient data, falls back to the static weight matrix.

        Args:
            asset: Trading symbol.
            timeframe: Bar timeframe.
            regime: Current market regime.

        Returns:
            Dict of {specialist: weight} summing to 1.
        """
        # Start from static weights
        key = (asset.upper(), timeframe)
        # Lazy import to avoid circular dependency
        from analytics.strategy.adaptive_ensemble import _WEIGHT_MATRIX

        static = _WEIGHT_MATRIX.get(key, {}).get(regime, {})
        if not static:
            # No entry for this combo — equal weights
            return dict.fromkeys(SpecialistId, 1.0 / 4)

        # Compute evolved weights from recent performance
        candidates = list(static.keys())
        sharpes = {s: self.get_average_sharpe(asset, timeframe, regime, s) for s in candidates}

        # Check if we have enough data
        valid = {s: sh for s, sh in sharpes.items() if abs(sh) > 1e-6}
        if len(valid) < 2:
            # Fall back to static
            return static

        # Convert to weights: positive Sharpe = higher weight
        # Negative Sharpe = reduce or zero
        raw_weights = {}
        for s, sh in valid.items():
            raw_weights[s] = max(0.0, sh)  # clamp negative to zero

        total = sum(raw_weights.values())
        if total <= 0:
            return static

        # Normalise
        evolved = {s: w / total for s, w in raw_weights.items()}
        return evolved


__all__ = ["WeightEvolver"]
