"""Population statistics — diversity, Pareto front, and aggregate fitness metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from deap import tools

__all__ = ["PopulationStats", "compute_diversity", "compute_stats", "pareto_front_individuals"]


@dataclass
class PopulationStats:
    """Aggregate statistics for a GA population at a given generation.

    Attributes:
        mean_fitness: Mean of each objective across the population
            (Sharpe, Sortino, Calmar, MaxDD).
        max_fitness: Maximum of each objective.
        min_fitness: Minimum of each objective.
        diversity: Mean pairwise Euclidean distance between individuals
            in normalised [0, 1]^n genome space.
        pareto_front_size: Number of non-dominated individuals.
        generation: Generation at which these stats were computed.
        pop_size: Total number of individuals in the population.
        best_fitness: Best (frontier) fitness values per objective.
        n_evaluated: Number of individuals evaluated this generation.
    """

    mean_fitness: tuple[float, ...]
    max_fitness: tuple[float, ...]
    min_fitness: tuple[float, ...]
    diversity: float
    pareto_front_size: int
    generation: int
    pop_size: int = 0
    best_fitness: tuple[float, ...] = ()
    n_evaluated: int = 0

    @property
    def n_pareto(self) -> int:
        """Alias for ``pareto_front_size`` (backwards compatibility)."""
        return self.pareto_front_size


def compute_diversity(population: list[Any]) -> float:
    """Mean pairwise Euclidean distance in normalised genome space.

    Accepts DEAP individuals or raw genome value lists.
    For large populations (n > 100), samples 100 random pairs to avoid O(n^2).
    """
    if len(population) < 2:
        return 0.0

    # Convert to numpy array for vectorised distance computation
    genomes = np.asarray(population, dtype=np.float64)  # shape (n, d)

    n = len(genomes)
    if n > 100:
        # Sample 100 random pairs
        rng = np.random.default_rng(42)
        idx_pairs = rng.integers(0, n, size=(100, 2))
        # Avoid self-pairs
        idx_pairs = idx_pairs[idx_pairs[:, 0] != idx_pairs[:, 1]]
        if len(idx_pairs) == 0:
            return 0.0
        diffs = genomes[idx_pairs[:, 0]] - genomes[idx_pairs[:, 1]]
        distances = np.sqrt(np.sum(diffs**2, axis=1))
        return float(np.mean(distances))

    # Full pairwise for n <= 100
    # Compute all pairwise distances without O(n^2) explicit loops
    # ||a - b||^2 = ||a||^2 + ||b||^2 - 2*a·b
    sq_norms = np.sum(genomes**2, axis=1, keepdims=True)  # (n, 1)
    dist_sq = sq_norms + sq_norms.T - 2.0 * (genomes @ genomes.T)
    # Numerical noise can produce tiny negatives
    dist_sq = np.maximum(dist_sq, 0.0)
    distances = np.sqrt(dist_sq)

    # Upper triangle excludes diagonal and duplicates
    triu = np.triu_indices(n, k=1)
    return float(np.mean(distances[triu]))


def _aggregate_fitness(
    population: list[Any],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Compute per-objective mean, max, min across a population."""
    all_fitness: list[tuple[float, ...]] = [
        tuple(float(v) for v in ind.fitness.values) for ind in population
    ]

    arr = np.asarray(all_fitness, dtype=np.float64)

    mean = tuple(float(v) for v in np.mean(arr, axis=0))
    max_v = tuple(float(v) for v in np.max(arr, axis=0))
    min_v = tuple(float(v) for v in np.min(arr, axis=0))

    return mean, max_v, min_v


def compute_stats(population: list[Any], generation: int) -> PopulationStats:
    """Compute aggregate statistics for a population.

    Args:
        population: List of DEAP individuals with ``.fitness.values`` set.
        generation: Current generation number.

    Returns:
        A :class:`PopulationStats` instance.
    """
    n = len(population)
    if n == 0:
        return PopulationStats(
            mean_fitness=(0.0, 0.0, 0.0, 0.0),
            max_fitness=(0.0, 0.0, 0.0, 0.0),
            min_fitness=(0.0, 0.0, 0.0, 0.0),
            diversity=0.0,
            pareto_front_size=0,
            generation=generation,
            pop_size=0,
            n_evaluated=0,
        )

    mean_f, max_f, min_f = _aggregate_fitness(population)
    diversity = compute_diversity(population)
    pareto_front = pareto_front_individuals(population)
    n_evaluated = sum(1 for ind in population if ind.fitness.valid)

    return PopulationStats(
        mean_fitness=mean_f,
        max_fitness=max_f,
        min_fitness=min_f,
        diversity=diversity,
        pareto_front_size=len(pareto_front),
        generation=generation,
        pop_size=n,
        best_fitness=max_f,
        n_evaluated=n_evaluated,
    )


def pareto_front_individuals(population: list[Any]) -> list[Any]:
    """Extract Pareto-optimal (non-dominated) individuals.

    Uses DEAP's multi-objective sorting (:func:`deap.tools.sortLogNondominated`)
    and returns only the first (best) rank.

    Args:
        population: List of DEAP individuals with ``.fitness.values`` set.

    Returns:
        List of non-dominated individuals.
    """
    if len(population) < 2:
        return list(population)

    try:
        fronts = tools.sortLogNondominated(population, len(population))
        if fronts:
            return list(fronts[0])
        return list(population)
    except (TypeError, ValueError):
        return list(population)
