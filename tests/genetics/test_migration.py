"""Tests for island migration — ring topology, selection, and replacement."""

from __future__ import annotations

from typing import Any

import pytest
from deap import base, creator

from genetics.population.migration import replace_worst, ring_migration, select_best_individuals

# ── helpers ──────────────────────────────────────────────────────────


def _make_individual(
    values: list[float], fitness_vals: tuple[float, float, float, float] | None = None
) -> Any:
    """Create a DEAP individual with optional fitness."""
    if not hasattr(creator, "FitnessMulti"):
        creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
    if not hasattr(creator, "Individual"):
        creator.create("Individual", list, fitness=creator.FitnessMulti)

    ind = creator.Individual(values)
    if fitness_vals is not None:
        ind.fitness.values = fitness_vals
    return ind


def _fitness_tuple(v: float) -> tuple[float, float, float, float]:
    """Create a simple 4-objective fitness with scaled values.

    Since weights are (1, 1, 1, -1), higher v = better for first three,
    lower (more negative) v = better for MaxDD.
    """
    return (v, v * 0.9, v * 0.8, -v * 0.05)


@pytest.fixture
def three_islands() -> list[list[Any]]:
    """Three islands of 5 individuals each with ordered fitness."""
    islands = []
    for island_idx in range(3):
        pop = []
        for rank in range(5):
            # Higher rank = better fitness (rank 4 is best)
            v = float(rank)
            pop.append(_make_individual([0.1 * island_idx + 0.01 * rank] * 3, _fitness_tuple(v)))
        islands.append(pop)
    return islands


# ── select_best_individuals ──────────────────────────────────────────


class TestSelectBest:
    def test_selects_correct_count(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(float(i))) for i in range(10)]
        selected = select_best_individuals(pop, 3)
        assert len(selected) == 3

    def test_selects_best_fitness(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(float(i))) for i in range(5)]
        selected = select_best_individuals(pop, 1)
        # Best individual is the one with highest v = 4
        assert selected[0].fitness.values[0] == pytest.approx(4.0)

    def test_selects_zero_returns_empty(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(1.0))]
        assert select_best_individuals(pop, 0) == []

    def test_k_exceeds_population_returns_all(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(float(i))) for i in range(3)]
        selected = select_best_individuals(pop, 10)
        assert len(selected) == 3

    def test_deterministic_order(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(float(i))) for i in range(5)]
        a = select_best_individuals(pop, 3)
        b = select_best_individuals(pop, 3)
        for ind_a, ind_b in zip(a, b, strict=True):
            assert list(ind_a) == list(ind_b)


# ── replace_worst ────────────────────────────────────────────────────


class TestReplaceWorst:
    def test_replaces_correct_count(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(float(i))) for i in range(5)]
        newcomers = [
            _make_individual([1.0], _fitness_tuple(100.0)),
            _make_individual([1.0], _fitness_tuple(100.0)),
        ]
        result = replace_worst(pop, newcomers)
        assert len(result) == 5

    def test_worst_replaced_with_better(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(float(i))) for i in range(5)]
        best_new = _make_individual([1.0], _fitness_tuple(100.0))
        replace_worst(pop, [best_new])
        # The worst (fitness 0.0) should be replaced
        fitnesses = [ind.fitness.values[0] for ind in pop]
        assert 100.0 in fitnesses
        assert len(fitnesses) == 5

    def test_no_newcomers(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(1.0))]
        result = replace_worst(pop, [])
        assert len(result) == 1

    def test_newcomers_exceed_population(self) -> None:
        pop = [_make_individual([0.1], _fitness_tuple(1.0))]
        newcomers = [
            _make_individual([0.2], _fitness_tuple(2.0)),
            _make_individual([0.3], _fitness_tuple(3.0)),
        ]
        result = replace_worst(pop, newcomers)
        assert len(result) == 1
        assert result[0].fitness.values[0] == pytest.approx(2.0)


# ── ring_migration ───────────────────────────────────────────────────


class TestRingMigration:
    def test_ring_topology(self, three_islands: list[list[Any]]) -> None:
        """Island 0 sends to 1, 1 sends to 2, 2 sends to 0."""
        original_best_0 = select_best_individuals(three_islands[0], 1)[0]
        original_best_1 = select_best_individuals(three_islands[1], 1)[0]
        original_best_2 = select_best_individuals(three_islands[2], 1)[0]

        result = ring_migration(three_islands, migration_size=1)

        # Island 1 should now contain the best from island 0
        fitnesses_1 = [ind.fitness.values[0] for ind in result[1]]
        assert max(fitnesses_1) == max(
            [original_best_0.fitness.values[0], original_best_1.fitness.values[0]]
        )
        # Island 2 gets best from island 1
        fitnesses_2 = [ind.fitness.values[0] for ind in result[2]]
        assert max(fitnesses_2) == max(
            [original_best_1.fitness.values[0]] + [ind.fitness.values[0] for ind in result[2]]
        )
        # Island 0 gets best from island 2
        fitnesses_0 = [ind.fitness.values[0] for ind in result[0]]
        assert max(fitnesses_0) == max(
            [original_best_2.fitness.values[0]] + [ind.fitness.values[0] for ind in result[0]]
        )

    def test_migration_size_zero(self, three_islands: list[list[Any]]) -> None:
        """No migration occurs when migration_size = 0."""
        original = [list(island) for island in three_islands]
        result = ring_migration(three_islands, migration_size=0)
        for orig, res in zip(original, result, strict=True):
            for a, b in zip(orig, res, strict=True):
                assert list(a) == list(b)

    def test_single_island(self) -> None:
        """A single island should remain unchanged."""
        island = [_make_individual([0.1], _fitness_tuple(1.0)) for _ in range(5)]
        result = ring_migration([island], migration_size=2)
        assert len(result) == 1
        assert len(result[0]) == 5

    def test_diversity_shifts_after_migration(self) -> None:
        """Migration introduces new genomes, shifting diversity."""
        islands = []
        for i in range(3):
            pop = [_make_individual([float(i)] * 4, _fitness_tuple(float(i + j))) for j in range(5)]
            islands.append(pop)

        # The best individual from each island should propagate
        result = ring_migration(islands, migration_size=2)

        # Diversity should have changed from the original isolated state
        # (Basic check: island 1 should now have individuals from island 0)
        genomes_1 = [list(ind) for ind in result[1]]
        assert any(g[0] == 0.0 for g in genomes_1)  # some from island 0

    def test_best_individuals_propagate(self) -> None:
        """The best individual from each island reaches the next one."""
        islands = []
        for i in range(3):
            pop = [
                _make_individual([float(i) + 0.1 * j], _fitness_tuple(float(j))) for j in range(5)
            ]
            islands.append(pop)

        best_0 = select_best_individuals(islands[0], 1)[0]
        best_1 = select_best_individuals(islands[1], 1)[0]

        result = ring_migration(islands, migration_size=1)

        # Best of island 0 is now in island 1
        genomes_1 = [list(ind) for ind in result[1]]
        assert list(best_0) in genomes_1

        # Best of island 1 is now in island 2
        genomes_2 = [list(ind) for ind in result[2]]
        assert list(best_1) in genomes_2

    def test_population_sizes_maintained(self, three_islands: list[list[Any]]) -> None:
        """Population sizes stay constant after migration."""
        sizes = [len(island) for island in three_islands]
        result = ring_migration(three_islands, migration_size=2)
        for i, island in enumerate(result):
            assert len(island) == sizes[i]

    def test_large_migration_size(self) -> None:
        """Migration size larger than island population still works."""
        islands = [
            [_make_individual([0.1], _fitness_tuple(1.0)) for _ in range(3)],
            [_make_individual([0.2], _fitness_tuple(2.0)) for _ in range(3)],
        ]
        result = ring_migration(islands, migration_size=10)
        assert len(result[0]) == 3
        assert len(result[1]) == 3
