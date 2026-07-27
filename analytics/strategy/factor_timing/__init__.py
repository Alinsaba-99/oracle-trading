"""Factor Timing — public API.

Ranks the 50 alpha factors in ``genetics/alpha/factors.py`` by their
current predictive power (Rank IC vs forward returns), with decay
detection, ICIR stability, and a null benchmark for selection-effect
control.

Usage::

    from analytics.strategy.factor_timing import FactorTimingEngine
    engine = FactorTimingEngine()
    ranking = engine.rank(close_df, horizon=5)
    top = ranking[:10]
"""

from analytics.strategy.factor_timing.effectiveness import (
    FactorEffectiveness,
    bh_adjust,
    decay_state,
    ic_pvalue,
    null_ic_benchmark,
    score_factor,
)
from analytics.strategy.factor_timing.rank import FactorRanking, FactorTimingEngine

__all__ = [
    "FactorEffectiveness",
    "FactorRanking",
    "FactorTimingEngine",
    "bh_adjust",
    "decay_state",
    "ic_pvalue",
    "null_ic_benchmark",
    "score_factor",
]
