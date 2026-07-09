"""Crossover operators for the GA engine.

Wraps DEAP's simulated binary crossover (SBX) with bounded support and
provides a validated variant that retries on invalid offspring.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import numpy as np
from deap import tools

from genetics.genome.signal import Genome, validate_genome

if TYPE_CHECKING:
    from genetics.genome.signal import GenomeConfig

__all__ = ["crossover_with_validation", "sbx_crossover"]


def sbx_crossover(
    ind1: list[float], ind2: list[float], eta: float = 15.0, low: float = 0.0, up: float = 1.0
) -> tuple[list[float], list[float]]:
    """Simulated Binary Crossover (SBX) bounded to *[low, up]*.

    Operates in-place on the input individuals — parents are consumed and
    become the offspring.  Works directly on the normalised *[0, 1]*
    genome representation.

    Args:
        ind1: First parent (normalised genome in *[0, 1]*).
        ind2: Second parent.
        eta: Distribution index; larger values create offspring closer to
            parents (default 15.0).
        low: Lower bound for offspring values (default 0.0).
        up: Upper bound for offspring values (default 1.0).

    Returns:
        Tuple of two offspring individuals.
    """
    return tools.cxSimulatedBinaryBounded(ind1, ind2, eta, low, up)  # type: ignore[no-any-return]


def crossover_with_validation(
    ind1: list[float], ind2: list[float], genome_config: GenomeConfig, eta: float = 15.0
) -> tuple[list[float], list[float]]:
    """SBX crossover with post-hoc genome validation.

    Applies SBX on copies of the parents, then validates offspring with
    :func:`~genetics.genome.signal.validate_genome`.  If validation fails,
    retries up to 3 times.  Returns unmodified copies of the original
    parents on repeated failure.

    Args:
        ind1: First parent (normalised genome in *[0, 1]*).
        ind2: Second parent.
        genome_config: Genome configuration providing ``param_defs`` used
            for :func:`~genetics.genome.signal.validate_genome`.
        eta: SBX distribution index.

    Returns:
        Tuple of two validated offspring (or original-parent copies).
    """
    for _ in range(3):
        c1 = copy.copy(ind1)
        c2 = copy.copy(ind2)
        tools.cxSimulatedBinaryBounded(c1, c2, eta, 0.0, 1.0)

        g1 = Genome(np.array(c1, dtype=np.float64), genome_config.param_defs)
        g2 = Genome(np.array(c2, dtype=np.float64), genome_config.param_defs)

        if validate_genome(g1) and validate_genome(g2):
            return c1, c2

    # Fallback: return pristine copies of the original parents
    return list(ind1), list(ind2)
