"""Fitness evaluation module — GA fitness functions for genetic optimisation.

Exports the primary :class:`FitnessEvaluator`, the :class:`FitnessCache`
for LRU eviction, and the :class:`WalkForwardConfig` dataclass.
"""

from __future__ import annotations

from genetics.fitness.cache import FitnessCache
from genetics.fitness.evaluator import FitnessEvaluator, WalkForwardConfig

__all__ = [
    "FitnessCache",
    "FitnessEvaluator",
    "WalkForwardConfig",
]
