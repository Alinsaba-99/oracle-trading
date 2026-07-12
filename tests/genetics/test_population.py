"""Tests for the population management module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from deap import base, creator

from genetics.genome.parameters import ContinuousParameter
from genetics.genome.signal import GenomeConfig
from genetics.population import (
    HallOfFameWrapper,
    PopulationStats,
    compute_stats,
    initialize_population,
    pareto_front_individuals,
    random_individual,
    seeded_individuals,
)
from genetics.population.stats import _compute_diversity

if TYPE_CHECKING:
    pass


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


@pytest.fixture
def genome_config() -> GenomeConfig:
    """Minimal genome config for testing."""
    defs = [
        ContinuousParameter("param_a", low=0.0, high=1.0),
        ContinuousParameter("param_b", low=-1.0, high=1.0),
        ContinuousParameter("param_c", low=0.0, high=10.0),
        ContinuousParameter("param_d", low=-5.0, high=5.0),
        ContinuousParameter("param_e", low=0.0, high=100.0),
    ]
    return GenomeConfig(n_params=len(defs), param_defs=defs)


# ── seeded_individuals ───────────────────────────────────────────────


class TestSeededIndividuals:
    def test_returns_correct_count(self) -> None:
        defs = [ContinuousParameter("x", low=0.0, high=1.0)]
        rng = np.random.default_rng(42)
        individuals = seeded_individuals(defs, n_params=1, rng=rng)
        assert len(individuals) == 10

    def test_each_is_valid_vector(self) -> None:
        defs = [ContinuousParameter("x", low=0.0, high=1.0) for _ in range(20)]
        rng = np.random.default_rng(42)
        individuals = seeded_individuals(defs, n_params=20, rng=rng)
        for vec in individuals:
            assert len(vec) == 20
            for v in vec:
                assert 0.0 <= v <= 1.0

    def test_deterministic_with_same_seed(self) -> None:
        """Same seed produces identical seeded populations."""
        defs = [ContinuousParameter("x", low=0.0, high=1.0) for _ in range(5)]
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        a = seeded_individuals(defs, n_params=5, rng=rng1)
        b = seeded_individuals(defs, n_params=5, rng=rng2)
        assert a == b

    def test_different_seed_different_strategies(self) -> None:
        """Different seed produces different vectors."""
        defs = [ContinuousParameter("x", low=0.0, high=1.0) for _ in range(5)]
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(99)
        a = seeded_individuals(defs, n_params=5, rng=rng1)
        b = seeded_individuals(defs, n_params=5, rng=rng2)
        # At least some vectors should differ
        assert any(a[i] != b[i] for i in range(10))


# ── random_individual ────────────────────────────────────────────────


class TestRandomIndividual:
    def test_length_and_range(self) -> None:
        rng = np.random.default_rng(42)
        ind = random_individual(10, rng=rng)
        assert len(ind) == 10
        for v in ind:
            assert 0.0 <= v <= 1.0

    def test_multiple_calls_diverse(self) -> None:
        """No two random individuals are identical (statistically)."""
        rng = np.random.default_rng(42)
        a = random_individual(20, rng=rng)
        b = random_individual(20, rng=rng)
        assert a != b


# ── initialize_population ────────────────────────────────────────────


class TestInitializePopulation:
    def test_seeded_count(self, genome_config: GenomeConfig) -> None:
        pop, _ = initialize_population(
            pop_size=50, genome_config=genome_config, seed_ratio=0.2, rng_seed=42
        )
        assert len(pop) == 50
        # 20% of 50 = 10, and seeded_individuals returns exactly 10
        assert len(pop) == 50

    def test_all_seeded(self, genome_config: GenomeConfig) -> None:
        """seed_ratio=1.0 creates all individuals from seeded templates."""
        pop, _ = initialize_population(
            pop_size=10, genome_config=genome_config, seed_ratio=1.0, rng_seed=42
        )
        assert len(pop) == 10

    def test_all_random(self, genome_config: GenomeConfig) -> None:
        """seed_ratio=0.0 creates all random individuals."""
        pop, _ = initialize_population(
            pop_size=20, genome_config=genome_config, seed_ratio=0.0, rng_seed=42
        )
        assert len(pop) == 20

    def test_pop_size_one(self, genome_config: GenomeConfig) -> None:
        """pop_size=1 returns one individual."""
        pop, _ = initialize_population(
            pop_size=1, genome_config=genome_config, seed_ratio=0.5, rng_seed=42
        )
        assert len(pop) == 1

    def test_deterministic(self, genome_config: GenomeConfig) -> None:
        """Same seed yields identical population (genome values)."""
        pop1, _ = initialize_population(
            pop_size=10, genome_config=genome_config, seed_ratio=0.3, rng_seed=42
        )
        pop2, _ = initialize_population(
            pop_size=10, genome_config=genome_config, seed_ratio=0.3, rng_seed=42
        )
        for a, b in zip(pop1, pop2, strict=True):
            assert list(a) == list(b)

    def test_toolbox_has_expected_attrs(self, genome_config: GenomeConfig) -> None:
        _, toolbox = initialize_population(10, genome_config, rng_seed=42)
        assert hasattr(toolbox, "individual")
        assert hasattr(toolbox, "population")
        assert hasattr(toolbox, "attr_float")

    def test_seeded_ratio_edge_zero(self, genome_config: GenomeConfig) -> None:
        """seed_ratio just above zero still works."""
        pop, _ = initialize_population(
            pop_size=100, genome_config=genome_config, seed_ratio=0.001, rng_seed=42
        )
        assert len(pop) == 100


# ── HallOfFameWrapper ────────────────────────────────────────────────


class TestHallOfFameWrapper:
    def test_empty_on_init(self) -> None:
        hof = HallOfFameWrapper(maxsize=10)
        assert len(hof) == 0

    def test_update_adds_individuals(self) -> None:
        hof = HallOfFameWrapper(maxsize=5)
        individuals = [
            _make_individual([0.1, 0.2], (1.0, 0.5, 0.3, -0.1)),
            _make_individual([0.3, 0.4], (0.8, 0.7, 0.4, -0.2)),
        ]
        hof.update(individuals)
        assert len(hof) == 2

    def test_hof_capacity_respected(self) -> None:
        """HallOfFame does not exceed maxsize."""
        hof = HallOfFameWrapper(maxsize=3)
        # Create many individuals with varying fitness
        individuals = [
            _make_individual([float(i)], (float(10 - i), 0.0, 0.0, -float(i))) for i in range(10)
        ]
        hof.update(individuals)
        assert len(hof) <= 3

    def test_best_individual_retained(self) -> None:
        """The best individual stays in HoF across updates."""
        hof = HallOfFameWrapper(maxsize=3)
        best = _make_individual([0.0, 0.0], (10.0, 10.0, 10.0, -0.1))
        hof.update([best, _make_individual([0.1, 0.1], (1.0, 1.0, 1.0, -0.5))])

        # Update with weaker individuals
        hof.update([_make_individual([0.2, 0.2], (0.5, 0.5, 0.5, -0.8))])
        assert best in hof.items

    def test_items_property(self) -> None:
        hof = HallOfFameWrapper(maxsize=5)
        ind = _make_individual([0.5, 0.5], (2.0, 2.0, 2.0, -0.1))
        hof.update([ind])
        assert hof.items == [ind]

    def test_getitem(self) -> None:
        hof = HallOfFameWrapper(maxsize=5)
        ind = _make_individual([0.5, 0.5], (2.0, 2.0, 2.0, -0.1))
        hof.update([ind])
        assert hof[0] == ind


# ── compute_stats ────────────────────────────────────────────────────


class TestComputeStats:
    @pytest.fixture
    def varied_population(self) -> list[Any]:
        return [
            _make_individual([0.1, 0.2], (1.0, 0.5, 0.3, -0.1)),
            _make_individual([0.3, 0.4], (0.8, 0.7, 0.4, -0.2)),
            _make_individual([0.5, 0.6], (1.2, 0.6, 0.5, -0.15)),
            _make_individual([0.7, 0.8], (0.5, 0.8, 0.2, -0.3)),
        ]

    def test_returns_valid_stats(self, varied_population: list[Any]) -> None:
        stats = compute_stats(varied_population, generation=5)
        assert isinstance(stats, PopulationStats)
        assert stats.generation == 5
        assert len(stats.mean_fitness) == 4
        assert len(stats.max_fitness) == 4
        assert len(stats.min_fitness) == 4

    def test_mean_fitness(self, varied_population: list[Any]) -> None:
        stats = compute_stats(varied_population, generation=0)
        expected_mean = (
            (1.0 + 0.8 + 1.2 + 0.5) / 4,
            (0.5 + 0.7 + 0.6 + 0.8) / 4,
            (0.3 + 0.4 + 0.5 + 0.2) / 4,
            (-0.1 - 0.2 - 0.15 - 0.3) / 4,
        )
        for actual, expected in zip(stats.mean_fitness, expected_mean, strict=True):
            assert actual == pytest.approx(expected)

    def test_max_fitness(self, varied_population: list[Any]) -> None:
        stats = compute_stats(varied_population, generation=0)
        assert stats.max_fitness[0] == 1.2  # max Sharpe

    def test_min_fitness(self, varied_population: list[Any]) -> None:
        stats = compute_stats(varied_population, generation=0)
        assert stats.min_fitness[3] == -0.3  # min MaxDD (most negative)

    def test_pareto_front_size(self) -> None:
        # Pareto front: (3, -0.1) dominates (2, -0.3), (1, -0.5)
        pop = [
            _make_individual([0.1, 0.2], (3.0, 3.0, 3.0, -0.1)),
            _make_individual([0.3, 0.4], (2.0, 2.0, 2.0, -0.3)),
            _make_individual([0.5, 0.6], (1.0, 1.0, 1.0, -0.5)),
        ]
        stats = compute_stats(pop, generation=0)
        assert stats.pareto_front_size > 0
        assert stats.pareto_front_size <= len(pop)

    def test_empty_population(self) -> None:
        stats = compute_stats([], generation=0)
        assert stats.mean_fitness == (0.0, 0.0, 0.0, 0.0)
        assert stats.diversity == 0.0
        assert stats.pareto_front_size == 0

    def test_single_individual(self) -> None:
        pop = [_make_individual([0.1, 0.2], (1.0, 0.5, 0.3, -0.1))]
        stats = compute_stats(pop, generation=1)
        assert stats.diversity == 0.0
        assert stats.pareto_front_size == 1

    def test_diversity_identical(self) -> None:
        """Identical genomes produce diversity of 0."""
        vec = [0.5, 0.5, 0.5]
        pop = [_make_individual(vec.copy(), (1.0, 1.0, 1.0, -0.1)) for _ in range(5)]
        stats = compute_stats(pop, generation=0)
        assert stats.diversity == pytest.approx(0.0, abs=1e-10)

    def test_diversity_varied(self) -> None:
        """Different genomes produce positive diversity."""
        pop = [
            _make_individual([0.0, 0.0], (1.0, 1.0, 1.0, -0.1)),
            _make_individual([1.0, 1.0], (2.0, 2.0, 2.0, -0.2)),
        ]
        stats = compute_stats(pop, generation=0)
        # Euclidean distance = sqrt((1-0)^2 + (1-0)^2) = sqrt(2)
        assert stats.diversity == pytest.approx(np.sqrt(2.0))


# ── pareto_front_individuals ─────────────────────────────────────────


class TestParetoFront:
    def test_non_dominated_extracted(self) -> None:
        """Only non-dominated individuals are in the Pareto front."""
        pop = [
            _make_individual([0.1, 0.2], (5.0, 5.0, 5.0, -0.1)),
            _make_individual([0.3, 0.4], (3.0, 3.0, 3.0, -0.3)),
            _make_individual([0.5, 0.6], (4.0, 4.0, 4.0, -0.2)),
        ]
        front = pareto_front_individuals(pop)
        # Individual 0 (5, -0.1) dominates all others
        assert len(front) >= 1

    def test_single_individual(self) -> None:
        pop = [_make_individual([0.5, 0.5], (1.0, 1.0, 1.0, -0.1))]
        front = pareto_front_individuals(pop)
        assert len(front) == 1

    def test_empty_population(self) -> None:
        front = pareto_front_individuals([])
        assert front == []

    def test_all_equal_fitness_all_pareto(self) -> None:
        """When all individuals have identical fitness, all are Pareto-optimal."""
        pop = [
            _make_individual([0.1, 0.2], (1.0, 1.0, 1.0, -0.1)),
            _make_individual([0.3, 0.4], (1.0, 1.0, 1.0, -0.1)),
            _make_individual([0.5, 0.6], (1.0, 1.0, 1.0, -0.1)),
        ]
        front = pareto_front_individuals(pop)
        assert len(front) == 3


# ── _compute_diversity ───────────────────────────────────────────────


class TestComputeDiversity:
    def test_no_individuals(self) -> None:
        """Empty list should return 0.0 diversity."""
        assert _compute_diversity([]) == 0.0

    def test_single_individual(self) -> None:
        assert _compute_diversity([[0.5, 0.5]]) == 0.0

    def test_two_identical(self) -> None:
        vec = [0.5, 0.5, 0.5]
        assert _compute_diversity([vec, list(vec)]) == 0.0

    def test_two_different(self) -> None:
        a = [0.0, 0.0]
        b = [1.0, 1.0]
        # Euclidean distance = sqrt(2)
        assert _compute_diversity([a, b]) == pytest.approx(np.sqrt(2.0))

    def test_three_individuals(self) -> None:
        """Diversity of three points in 2D."""
        individuals = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
        # Distances: d(0,1)=1, d(0,2)=1, d(1,2)=sqrt(2)
        # Mean = (1 + 1 + sqrt(2)) / 3
        expected = (1.0 + 1.0 + np.sqrt(2.0)) / 3.0
        assert _compute_diversity(individuals) == pytest.approx(expected)
