"""Population management — initialisation, statistics, migration, and Hall of Fame."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from deap import base, creator, tools

from genetics.population.migration import (
    MigrationPolicy,
    MigrationTopology,
    replace_worst,
    ring_migration,
    select_best_individuals,
)
from genetics.population.seeding import random_individual, seeded_individuals
from genetics.population.stats import PopulationStats, compute_stats, pareto_front_individuals

if TYPE_CHECKING:
    from genetics.genome.signal import GenomeConfig

__all__ = [
    "HallOfFameWrapper",
    "MigrationPolicy",
    "MigrationTopology",
    "PopulationStats",
    "compute_stats",
    "initialize_population",
    "pareto_front_individuals",
    "random_individual",
    "replace_worst",
    "ring_migration",
    "seeded_individuals",
    "select_best_individuals",
]

_INDIVIDUAL_CLASS_REGISTERED = False
_FITNESS_CLASS_REGISTERED = False


def _ensure_types() -> None:
    """Register DEAP creator types if not already done (idempotent)."""
    global _FITNESS_CLASS_REGISTERED, _INDIVIDUAL_CLASS_REGISTERED

    if not _FITNESS_CLASS_REGISTERED:
        if not hasattr(creator, "FitnessMulti"):
            creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
        _FITNESS_CLASS_REGISTERED = True

    if not _INDIVIDUAL_CLASS_REGISTERED:
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list, fitness=creator.FitnessMulti)
        _INDIVIDUAL_CLASS_REGISTERED = True


def initialize_population(
    pop_size: int,
    genome_config: GenomeConfig,
    seed_ratio: float = 0.2,
    rng_seed: int = 42,
    seed_genomes: list[list[float]] | None = None,
) -> tuple[list[Any], base.Toolbox]:
    """Create an initial GA population with a mix of seeded and random individuals.

    ``seed_ratio * pop_size`` individuals are created via biased seeding
    (known strategy templates), and the rest are uniformly random.

    If *seed_genomes* is provided, these pre-encoded genomes are injected
    into the population first (replacing random individuals), ensuring the
    GA starts from known-good parameter combinations.

    Args:
        pop_size: Total population size.
        genome_config: Genome definition (parameter count and definitions).
        seed_ratio: Fraction of the population to seed with strategy templates
            (default 0.2 = 20%).
        rng_seed: Seed for reproducible random generation.
        seed_genomes: Optional list of pre-encoded normalized parameter vectors
            (each a list of floats in [0,1]) to inject into the population.

    Returns:
        A tuple of ``(population, toolbox)`` where *population* is a list of
        DEAP individuals and *toolbox* is a configured :class:`deap.base.Toolbox`.
    """
    _ensure_types()

    rng = np.random.default_rng(rng_seed)
    n = genome_config.n_params

    # Build a minimal toolbox for individual creation
    toolbox = base.Toolbox()
    toolbox.register("attr_float", rng.uniform, 0.0, 1.0)
    toolbox.register(
        "individual",
        tools.initRepeat,
        creator.Individual,
        toolbox.attr_float,
        n,
    )
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    n_seeded = max(0, min(pop_size, int(pop_size * seed_ratio)))
    n_random = pop_size - n_seeded

    # Build population
    population: list[Any] = []

    # Pre-encoded seed genomes (injected first, highest priority)
    n_seed_inject = len(seed_genomes) if seed_genomes else 0
    if n_seed_inject > 0:
        for vec in seed_genomes:
            if len(vec) != n:
                continue  # skip mismatched vectors
            ind = creator.Individual(vec)
            population.append(ind)

    # Seeded individuals (strategy templates)
    remaining = pop_size - len(population)
    n_seeded_actual = max(0, min(remaining, n_seeded))
    if n_seeded_actual > 0:
        seeded_vecs = seeded_individuals(
            genome_config.param_defs,
            n_params=n,
            rng=rng,
        )
        for i in range(n_seeded_actual):
            vec = seeded_vecs[i % len(seeded_vecs)]
            ind = creator.Individual(vec)
            population.append(ind)

    # Random individuals (fill remaining)
    remaining = pop_size - len(population)
    for _ in range(remaining):
        vec = random_individual(n, rng=rng)
        ind = creator.Individual(vec)
        population.append(ind)

    return population, toolbox


class HallOfFameWrapper:
    """Wrapper around DEAP's :class:`~deap.tools.HallOfFame`.

    Maintains the best *maxsize* individuals ever seen across generations.
    """

    def __init__(self, maxsize: int = 10) -> None:
        """Initialise the Hall of Fame.

        Args:
            maxsize: Maximum number of distinct individuals to archive.
        """
        self._hof = tools.HallOfFame(maxsize)

    def update(self, population: list[Any]) -> None:
        """Update the Hall of Fame with the current population.

        Args:
            population: List of DEAP individuals with ``.fitness.values`` set.
        """
        self._hof.update(population)

    @property
    def items(self) -> list[Any]:
        """Access the archived individuals (ordered by fitness, best first)."""
        return list(self._hof)

    @property
    def maxsize(self) -> int:
        """Maximum capacity of the Hall of Fame."""
        return self._hof.maxsize  # type: ignore[no-any-return]

    def __len__(self) -> int:
        """Number of individuals currently in the Hall of Fame."""
        return len(self._hof)

    def __getitem__(self, index: int) -> Any:
        """Access the *i*-th best individual."""
        return self._hof[index]
