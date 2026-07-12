"""Island model migration — policies and topology for population exchange."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = [
    "MigrationPolicy",
    "MigrationTopology",
    "replace_worst",
    "ring_migration",
    "select_best_individuals",
]


class MigrationTopology(Enum):
    """Communication topology between islands."""

    RING = "ring"
    FULLY_CONNECTED = "fully_connected"


@dataclass
class MigrationPolicy:
    """Configuration for island model migration.

    Attributes:
        topology: Topology of inter-island communication.
        interval: Number of generations between migrations.
        size: Number of individuals to exchange per migration.
    """

    topology: MigrationTopology = MigrationTopology.RING
    interval: int = 5
    size: int = 3


def _total_weighted_fitness(individual: Any, weights: tuple[float, ...] | None = None) -> float:
    """Compute total weighted fitness for an individual.

    Uses fitness weights from the DEAP creator if not explicitly given.
    By default the NSGA-II weights are (1.0, 1.0, 1.0, -1.0) for the
    four objectives (Sharpe, Sortino, Calmar, MaxDD).
    """
    values = tuple(float(v) for v in individual.fitness.values)
    if not values:
        return 0.0
    if weights is None:
        # Use the fitness weights from the individual's type
        w = individual.fitness.weights if hasattr(individual.fitness, "weights") else None
        if w is not None:
            weights = tuple(float(v) for v in w)

    n = min(len(values), len(weights)) if weights else len(values)
    if weights:
        return sum(values[i] * weights[i] for i in range(n))
    return sum(values)


def select_best_individuals(population: list[Any], k: int) -> list[Any]:
    """Select the top-*k* individuals by total weighted fitness.

    Args:
        population: List of DEAP individuals with ``.fitness.values`` set.
        k: Number of individuals to select.

    Returns:
        The *k* best individuals (highest total weighted fitness).
    """
    if k >= len(population):
        return sorted(population, key=_total_weighted_fitness, reverse=True)

    scored = [(ind, _total_weighted_fitness(ind)) for ind in population]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [ind for ind, _ in scored[:k]]


def replace_worst(population: list[Any], newcomers: list[Any]) -> list[Any]:
    """Replace the worst individuals with newcomers.

    The worst individuals are those with lowest total weighted fitness.

    Args:
        population: Population to modify (will be mutated in-place).
        newcomers: Individuals to insert.

    Returns:
        The updated population (same list object, possibly with replaced
        elements; also returned for convenience).
    """
    if not newcomers:
        return population

    n_replace = min(len(newcomers), len(population))

    # Find indices of the n_replace worst individuals
    scored = [(i, _total_weighted_fitness(population[i])) for i in range(len(population))]
    scored.sort(key=lambda x: x[1])
    worst_indices = sorted(scored[i][0] for i in range(n_replace))

    for idx, new_ind in zip(worst_indices, newcomers, strict=False):
        population[idx] = new_ind

    return population


def ring_migration(islands: list[list[Any]], migration_size: int) -> list[list[Any]]:
    """Perform ring-topology migration between islands.

    Each island *i* sends its best *migration_size* individuals to island
    *(i + 1) mod N*. Incoming individuals replace the worst individuals
    in the receiving island.

    Args:
        islands: List of populations (each a list of DEAP individuals).
        migration_size: Number of individuals to exchange.

    Returns:
        Updated island populations after migration.
    """
    if len(islands) < 2 or migration_size <= 0:
        return islands

    n = len(islands)

    # Extract emigrants: best individuals from each island
    emigrants: list[list[Any]] = [[] for _ in range(n)]
    for i in range(n):
        emigrants[i] = select_best_individuals(islands[i], min(migration_size, len(islands[i])))

    # Each island i sends to island (i+1) mod n
    for i in range(n):
        sender = i
        receiver = (i + 1) % n
        if emigrants[sender]:
            replace_worst(islands[receiver], list(emigrants[sender]))

    return islands
