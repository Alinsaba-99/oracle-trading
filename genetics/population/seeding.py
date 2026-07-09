"""Seeded strategy initialisation — creates 10 strategy-biased genome templates.

Each seeded strategy encodes a known trading strategy family as a bias vector
in normalised parameter space, with random perturbation for diversity.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from genetics.genome.parameters import GenomeParameter

__all__ = ["random_individual", "seeded_individuals"]


def random_individual(
    n_params: int,
    rng: np.random.Generator,
) -> list[float]:
    """Generate a single random normalised genome vector in [0, 1]^n."""
    return [float(v) for v in rng.uniform(0.0, 1.0, size=n_params)]


def _make_bias_vector(
    n_params: int,
    *,
    momentum_weight: float = 0.0,
    sma_weight: float = 0.0,
    rsi_weight: float = 0.0,
    vol_weight: float = 0.0,
    seasonal_weight: float = 0.0,
    carry_weight: float = 0.0,
    quality_weight: float = 0.0,
    lowvol_weight: float = 0.0,
    volume_weight: float = 0.0,
    hedge_weight: float = 0.0,
    rng: np.random.Generator,
) -> list[float]:
    """Build a bias vector biased toward a strategy archetype.

    Each factor weight is allocated to a group of consecutive parameters
    (roughly n_params // 10 per group). Parameters in 'favoured' groups
    get values pulled toward 0.8-1.0, others toward 0.0-0.3.
    """
    # Build per-parameter weights by spreading each strategy weight
    # across approximately equal-sized blocks.
    group_size = max(1, n_params // 10)
    weights = np.zeros(n_params, dtype=np.float64)

    factor_weights = [
        momentum_weight,
        sma_weight,
        rsi_weight,
        vol_weight,
        seasonal_weight,
        carry_weight,
        quality_weight,
        lowvol_weight,
        volume_weight,
        hedge_weight,
    ]

    for i, fw in enumerate(factor_weights):
        start = i * group_size
        end = min(start + group_size, n_params)
        if start < end:
            weights[start:end] = fw

    # Derive each parameter from the bias weight plus random noise
    vec = np.empty(n_params, dtype=np.float64)
    for i in range(n_params):
        # Higher weight -> expected value closer to 1.0
        expected = 0.1 + 0.8 * weights[i]
        # Perturb with noise that scales with distance from bounds
        noise = rng.normal(0.0, 0.15)
        raw = expected + noise
        vec[i] = np.clip(raw, 0.0, 1.0)

    return vec.tolist()


def seeded_individuals(
    param_defs: Sequence[GenomeParameter],
    n_params: int,
    rng: np.random.Generator,
) -> list[list[float]]:
    """Create 10 seeded strategy templates encoded as normalised vectors.

    Each strategy has a specific bias profile that weights certain
    parameter groups more heavily than others, creating individuals
    that represent known trading strategy families while still being
    randomised enough to maintain diversity.

    Args:
        param_defs: Parameter definitions for the genome.
        n_params: Number of parameters.
        rng: Reproducible random generator.

    Returns:
        List of 10 normalised genome vectors (each a ``list[float]`` in [0,1]).
    """
    del param_defs  # Used for future parameter-type-aware seeding.

    strategies = [
        # 1. Trend-following (SMA crossover 20/50)
        _make_bias_vector(n_params, sma_weight=1.0, rng=rng),
        # 2. Mean-reversion (RSI <30 >70)
        _make_bias_vector(n_params, rsi_weight=1.0, rng=rng),
        # 3. Momentum (12m-1m)
        _make_bias_vector(n_params, momentum_weight=1.0, rng=rng),
        # 4. Volatility breakout (Bollinger 2 sigma)
        _make_bias_vector(n_params, vol_weight=1.0, rng=rng),
        # 5. Pairs trading hedge ratio
        _make_bias_vector(n_params, hedge_weight=1.0, rng=rng),
        # 6. Carry trade basis
        _make_bias_vector(n_params, carry_weight=1.0, rng=rng),
        # 7. Seasonal (month-of-year)
        _make_bias_vector(n_params, seasonal_weight=1.0, rng=rng),
        # 8. Volume-weighted momentum
        _make_bias_vector(n_params, momentum_weight=0.7, volume_weight=0.7, rng=rng),
        # 9. Low-volatility
        _make_bias_vector(n_params, lowvol_weight=1.0, rng=rng),
        # 10. Quality (DivYield + ROE)
        _make_bias_vector(n_params, quality_weight=1.0, rng=rng),
    ]

    return strategies
