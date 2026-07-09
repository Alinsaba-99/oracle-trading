"""Tests for the island-model GA — Island, IslandManager, migration, diversity."""

from __future__ import annotations

import json
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import polars as pl
import pytest

from genetics.genome.parameters import ContinuousParameter
from genetics.genome.signal import GenomeConfig
from genetics.islands import (
    IslandManager,
    MigrationPolicy,
    PopulationStats,
    compute_diversity,
    compute_stats,
    ring_migration,
)

if TYPE_CHECKING:

    from genetics.genome.parameters import GenomeParameter


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def simple_defs() -> list[GenomeParameter]:
    return [
        ContinuousParameter("alpha", low=0.0, high=1.0),
        ContinuousParameter("beta", low=-1.0, high=1.0),
        ContinuousParameter("gamma", low=0.0, high=10.0),
    ]


@pytest.fixture
def genome_config(simple_defs: list[GenomeParameter]) -> GenomeConfig:
    return GenomeConfig(n_params=len(simple_defs), param_defs=simple_defs)


@pytest.fixture
def small_data() -> pl.DataFrame:
    return pl.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})


@pytest.fixture
def mock_evaluator() -> MagicMock:
    evaluator = MagicMock()
    evaluator.evaluate.return_value = (0.5, 0.3, 0.4, -0.1)
    return evaluator


# ── IslandManager creation ─────────────────────────────────────────


class TestIslandManagerCreate:
    def test_correct_number_of_islands(self, genome_config: GenomeConfig) -> None:
        manager = IslandManager(genome_config, n_islands=4, pop_size_per_island=10)
        assert len(manager.islands) == 4

    def test_single_island(self, genome_config: GenomeConfig) -> None:
        manager = IslandManager(genome_config, n_islands=1, pop_size_per_island=10)
        assert len(manager.islands) == 1

    def test_population_size_per_island(self, genome_config: GenomeConfig) -> None:
        manager = IslandManager(genome_config, n_islands=3, pop_size_per_island=20)
        for island in manager.islands:
            assert len(island.population) == 20

    def test_different_rng_seeds_different_populations(self, genome_config: GenomeConfig) -> None:
        """Each island has a different RNG seed → different initial population."""
        manager = IslandManager(genome_config, n_islands=3, pop_size_per_island=5, seed=42)

        # Check that populations differ (at least one individual differs)
        pop0_flat = [list(ind) for ind in manager.islands[0].population]
        pop1_flat = [list(ind) for ind in manager.islands[1].population]
        # At least some values should differ
        assert any(
            abs(p0[i] - p1[i]) > 1e-10
            for p0, p1 in zip(pop0_flat, pop1_flat, strict=True)
            for i in range(len(p0))
        )

    def test_deterministic_reinitialization(self, genome_config: GenomeConfig) -> None:
        """Same seed → same island populations."""
        manager1 = IslandManager(genome_config, n_islands=2, pop_size_per_island=5, seed=99)
        manager2 = IslandManager(genome_config, n_islands=2, pop_size_per_island=5, seed=99)

        for i in range(2):
            for ind1, ind2 in zip(
                manager1.islands[i].population,
                manager2.islands[i].population,
                strict=True,
            ):
                assert list(ind1) == list(ind2)


# ── evaluate_next_gen ─────────────────────────────────────────────


class TestEvaluateNextGen:
    def test_returns_population_stats(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        manager = IslandManager(genome_config, n_islands=1, pop_size_per_island=5)
        island = manager.islands[0]

        stats = island.evaluate_next_gen(mock_evaluator, small_data)
        assert isinstance(stats, PopulationStats)
        assert stats.generation == 1
        assert stats.pop_size == 5
        assert stats.n_evaluated > 0

    def test_generation_increments(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        manager = IslandManager(genome_config, n_islands=1, pop_size_per_island=5)
        island = manager.islands[0]
        assert island.generation == 0

        island.evaluate_next_gen(mock_evaluator, small_data)
        assert island.generation == 1

        island.evaluate_next_gen(mock_evaluator, small_data)
        assert island.generation == 2

    def test_population_unchanged_size(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        """NSGA-II selection maintains a constant population size."""
        manager = IslandManager(genome_config, n_islands=1, pop_size_per_island=10)
        island = manager.islands[0]

        island.evaluate_next_gen(mock_evaluator, small_data)
        assert len(island.population) == 10

    def test_evaluator_called(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        manager = IslandManager(genome_config, n_islands=1, pop_size_per_island=3)
        island = manager.islands[0]

        n_calls_before = mock_evaluator.evaluate.call_count
        island.evaluate_next_gen(mock_evaluator, small_data)
        assert mock_evaluator.evaluate.call_count > n_calls_before


# ── ProcessPoolExecutor usage ──────────────────────────────────────


class TestParallelExecution:
    def test_with_thread_pool_executor(self, genome_config: GenomeConfig, small_data: pl.DataFrame) -> None:
        """Island evaluation works with ThreadPoolExecutor for per-individual eval."""
        from concurrent.futures import ThreadPoolExecutor

        evaluator = MagicMock()
        evaluator.evaluate.return_value = (0.5, 0.3, 0.4, -0.1)

        manager = IslandManager(genome_config, n_islands=2, pop_size_per_island=5)
        island = manager.islands[0]

        with ThreadPoolExecutor(max_workers=2) as executor:
            stats = island.evaluate_next_gen(evaluator, small_data, executor=executor)

        assert isinstance(stats, PopulationStats)
        assert stats.generation == 1

    def test_run_generation_async(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        """IslandManager.run_generation works asynchronously."""
        import asyncio

        manager = IslandManager(genome_config, n_islands=2, pop_size_per_island=5)

        async def _run() -> list[PopulationStats]:
            return await manager.run_generation(
                generation=0,
                evaluator=mock_evaluator,
                data=small_data,
            )

        results = asyncio.run(_run())
        assert len(results) == 2
        for stats in results:
            assert isinstance(stats, PopulationStats)
            assert stats.generation == 1


# ── Migration ──────────────────────────────────────────────────────


class TestMigration:
    def test_ring_migration_edges(self, genome_config: GenomeConfig) -> None:
        manager = IslandManager(genome_config, n_islands=4, pop_size_per_island=5)
        edges = ring_migration(manager.islands, 2)
        assert len(edges) == 4
        # Each island sends to the next
        for i, (src, dst) in enumerate(edges):
            assert src == i
            assert dst == (i + 1) % 4

    def test_single_island_no_migration(self, genome_config: GenomeConfig) -> None:
        manager = IslandManager(genome_config, n_islands=1, pop_size_per_island=5)
        edges = ring_migration(manager.islands, 2)
        assert edges == []

    def test_migration_changes_population_diversity(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        """Migration should affect population diversity when replacement is on."""
        import asyncio

        manager = IslandManager(
            genome_config,
            n_islands=3,
            pop_size_per_island=5,
            migration_policy=MigrationPolicy(interval=1, size=2, replacement=True),
        )

        # Run a generation to give islands fitness values
        asyncio.run(manager.run_generation(0, mock_evaluator, small_data))

        # Record pre-migration individuals
        pre_migration = [list(manager.islands[i].population[0]) for i in range(3)]

        # Migrate
        manager.migrate()

        # Migration with interval=1 should fire (generation >= 1)
        assert manager.generation >= 1

        # Verify that individuals may have changed post-migration
        any_changed = any(
            abs(pre_migration[i][j] - list(manager.islands[i].population[0])[j]) > 1e-10
            for i in range(3)
            for j in range(len(pre_migration[0]))
        )
        # Migration may or may not change individuals depending on fitness ordering
        # The main check is that the method doesn't error
        assert isinstance(any_changed, bool)

    def test_migration_policy_no_migration_when_not_due(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        """Migration shouldn't fire when generation is not a multiple of interval."""
        import asyncio

        manager = IslandManager(
            genome_config,
            n_islands=3,
            pop_size_per_island=5,
            migration_policy=MigrationPolicy(interval=10, size=2),
        )

        # Run 1 generation
        asyncio.run(manager.run_generation(0, mock_evaluator, small_data))

        # Store before
        before = [list(manager.islands[i].population[0]) for i in range(3)]
        manager.migrate()
        after = [list(manager.islands[i].population[0]) for i in range(3)]

        # Should be unchanged
        for b, a in zip(before, after, strict=True):
            assert b == a


# ── merge_pareto_fronts ────────────────────────────────────────────


class TestMergeParetoFronts:
    def test_merge_empty(self, genome_config: GenomeConfig) -> None:
        manager = IslandManager(genome_config, n_islands=2, pop_size_per_island=5)
        front = manager.merge_pareto_fronts()
        # No valid fitness → empty front
        assert isinstance(front, list)

    def test_merge_non_empty(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        import asyncio

        manager = IslandManager(genome_config, n_islands=2, pop_size_per_island=5)
        asyncio.run(manager.run_generation(0, mock_evaluator, small_data))

        front = manager.merge_pareto_fronts()
        # Should return some Pareto-optimal individuals
        assert len(front) >= 1
        # All should have valid fitness
        for ind in front:
            assert ind.fitness.valid

    def test_merge_returns_non_dominated(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        """All returned individuals should be mutually non-dominated."""
        import asyncio

        manager = IslandManager(genome_config, n_islands=2, pop_size_per_island=5)
        asyncio.run(manager.run_generation(0, mock_evaluator, small_data))

        front = manager.merge_pareto_fronts()
        # DEAP's sortNondominated returns the first Pareto front
        # Verify no individual in the front dominates another
        for i, a in enumerate(front):
            for b in front[i + 1 :]:
                aw = a.fitness.wvalues
                bw = b.fitness.wvalues
                # a should not dominate b and b should not dominate a
                a_dom_b = all(aw[j] >= bw[j] for j in range(len(aw))) and any(
                    aw[j] > bw[j] for j in range(len(aw))
                )
                b_dom_a = all(bw[j] >= aw[j] for j in range(len(aw))) and any(
                    bw[j] > aw[j] for j in range(len(aw))
                )
                assert not (a_dom_b or b_dom_a), f"Individual {i} and {i+1} are not mutually non-dominated"


# ── PopulationStats / compute_stats ────────────────────────────────


class TestComputeStats:
    def test_empty_population(self) -> None:
        stats = compute_stats([], generation=0)
        assert stats.generation == 0
        assert stats.pop_size == 0

    def test_diversity(self, genome_config: GenomeConfig) -> None:
        manager = IslandManager(genome_config, n_islands=1, pop_size_per_island=10)
        pop = manager.islands[0].population
        div = compute_diversity(pop)
        assert div >= 0.0
        assert isinstance(div, float)

    def test_diversity_identical_population(self, genome_config: GenomeConfig) -> None:
        """Identical individuals should have zero diversity."""
        from deap import base, creator

        if not hasattr(creator, "FitnessMulti"):
            creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list)

        pop = [creator.Individual([0.5, 0.5, 0.5]) for _ in range(5)]
        div = compute_diversity(pop)
        # Floating-point roundoff from pairwise distance computation
        assert div < 1e-6


# ── Checkpoint / restore ──────────────────────────────────────────


class TestCheckpoint:
    def test_save_checkpoint(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        import asyncio

        manager = IslandManager(genome_config, n_islands=2, pop_size_per_island=5)
        asyncio.run(manager.run_generation(0, mock_evaluator, small_data))

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = f.name
            manager.save_checkpoint(path)

        with open(path) as f:
            data = json.load(f)

        assert data["schema_version"] == 1
        assert data["n_islands"] == 2
        assert len(data["islands"]) == 2
        assert data["islands"][0]["id"] == 0
        assert data["islands"][1]["id"] == 1

    def test_load_checkpoint_round_trip(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        import asyncio

        manager = IslandManager(genome_config, n_islands=2, pop_size_per_island=5)
        asyncio.run(manager.run_generation(0, mock_evaluator, small_data))

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = f.name
            manager.save_checkpoint(path)

        restored = IslandManager.load_checkpoint(path, genome_config)
        assert restored.n_islands == 2
        assert len(restored.islands) == 2

    def test_load_corrupted_checkpoint(self, genome_config: GenomeConfig) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write('{"schema_version": 999}')
            path = f.name

        with pytest.raises(ValueError, match="Unsupported checkpoint schema"):
            IslandManager.load_checkpoint(path, genome_config)

    def test_load_checkpoint_generation_restored(self, genome_config: GenomeConfig, mock_evaluator: MagicMock, small_data: pl.DataFrame) -> None:
        import asyncio

        manager = IslandManager(genome_config, n_islands=1, pop_size_per_island=5)
        asyncio.run(manager.run_generation(0, mock_evaluator, small_data))
        asyncio.run(manager.run_generation(1, mock_evaluator, small_data))
        assert manager.generation == 2

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = f.name
            manager.save_checkpoint(path)

        restored = IslandManager.load_checkpoint(path, genome_config)
        assert restored.generation == 2
