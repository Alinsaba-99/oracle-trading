"""Mutation operators for the GA engine.

Provides polynomial mutation in normalised space, a validated variant,
and a specialised categorical-swap mutator.
"""

from __future__ import annotations

import copy
import random
from typing import TYPE_CHECKING

import numpy as np
from deap import tools

from genetics.genome.signal import Genome, validate_genome

if TYPE_CHECKING:
    from collections.abc import Mapping

    from genetics.genome.signal import GenomeConfig

__all__ = ["categorical_mutation", "mutation_with_validation", "polynomial_mutation"]


def polynomial_mutation(
    individual: list[float],
    eta: float = 20.0,
    indpb: float = 0.15,
    low: float = 0.0,
    up: float = 1.0,
) -> tuple[list[float], ...]:
    """Polynomial mutation bounded to *[low, up]*.

    Mutates each gene with probability *indpb* using a polynomial
    probability distribution.  Operates in-place and returns the
    modified individual.

    Args:
        individual: Individual to mutate (normalised genome in *[0, 1]*).
        eta: Distribution index; larger values create offspring closer to
            the original (default 20.0).
        indpb: Independent probability of mutating each gene (default 0.15).
        low: Lower bound (default 0.0).
        up: Upper bound (default 1.0).

    Returns:
        Tuple containing the mutated individual.
    """
    return tools.mutPolynomialBounded(individual, eta, low, up, indpb)  # type: ignore[no-any-return]


def mutation_with_validation(
    individual: list[float], genome_config: GenomeConfig, eta: float = 20.0, indpb: float = 0.15
) -> tuple[list[float], ...]:
    """Polynomial mutation with post-hoc genome validation.

    Applies polynomial mutation on a copy of *individual*, then validates
    with :func:`~genetics.genome.signal.validate_genome`.  Retries up to 3
    times on failure, then returns the original individual unchanged.

    Args:
        individual: Individual to mutate (normalised genome in *[0, 1]*).
        genome_config: Genome configuration providing ``param_defs`` for
            :func:`~genetics.genome.signal.validate_genome`.
        eta: Polynomial mutation distribution index.
        indpb: Per-gene mutation probability.

    Returns:
        Tuple containing the mutated (or original) individual.
    """
    for _ in range(3):
        mut = copy.copy(individual)
        tools.mutPolynomialBounded(mut, eta, 0.0, 1.0, indpb)

        g = Genome(np.array(mut, dtype=np.float64), genome_config.param_defs)
        if validate_genome(g):
            return (mut,)

    return (list(individual),)


def categorical_mutation(
    individual: list[float], cat_indices: Mapping[int, int], indpb: float = 0.1
) -> tuple[list[float], ...]:
    """Mutate categorical parameters by swapping to a different category.

    Operates on the normalised *[0, 1]* representation held by *individual*.
    For each categorical parameter, with probability *indpb*, the current
    normalised value is replaced with the normalised value of a randomly
    chosen *different* category.

    Args:
        individual: Individual whose categorical genes are mutated in-place.
        cat_indices: Mapping from normalised-vector index to the number of
            categories for that categorical parameter.
            E.g. ``{3: 3, 5: 2}`` means index 3 has 3 categories and
            index 5 has 2 categories.
        indpb: Per-gene mutation probability (default 0.1).

    Returns:
        Tuple containing the mutated individual.
    """
    for idx, n_cats in cat_indices.items():
        if random.random() < indpb:
            if n_cats <= 1:
                continue
            current = round(individual[idx] * (n_cats - 1))
            others = [c for c in range(n_cats) if c != current]
            new_cat = random.choice(others)
            individual[idx] = new_cat / (n_cats - 1)

    return (individual,)
