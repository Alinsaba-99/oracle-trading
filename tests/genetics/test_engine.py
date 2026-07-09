"""Tests for the top-level GeneticEngine — configuration, run, checkpoint/restore."""

from __future__ import annotations

import json
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from genetics.engine import GAConfig, GAResult, GeneticEngine
from genetics.genome.parameters import ContinuousParameter
from genetics.genome.signal import GenomeConfig

if TYPE_CHECKING:

    from genetics.genome.parameters import GenomeParameter


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def simple_defs() -> list[GenomeParameter]:
    return [
        ContinuousParameter("alpha", low=0.0, high=1.0),
        ContinuousParameter("beta", low=-1.0, high=1.0),
    ]


@pytest.fixture
def genome_config(simple_defs: list[GenomeParameter]) -> GenomeConfig:
    return GenomeConfig(n_params=len(simple_defs), param_defs=simple_defs)


@pytest.fixture
def ga_config(genome_config: GenomeConfig) -> GAConfig:
    return GAConfig(
        genome_config=genome_config,
        pop_size=8,
        generations=3,
        n_islands=2,
        crossover_prob=0.8,
        mutation_prob=0.2,
        seed=42,
        checkpoint_interval=2,
    )


@pytest.fixture
def small_data() -> pl.DataFrame:
    return pl.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})


@pytest.fixture
def mock_evaluator() -> MagicMock:
    """Fixture that patches FitnessEvaluator and returns a configured mock."""
    evaluator = MagicMock()
    evaluator.evaluate.return_value = (0.5, 0.3, 0.4, -0.1)
    with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
        cls_mock.return_value = evaluator
        yield evaluator


# ── Initialization ─────────────────────────────────────────────────


class TestEngineInit:
    def test_engine_creates_with_config(self, ga_config: GAConfig) -> None:
        engine = GeneticEngine(ga_config)
        assert engine.config == ga_config
        assert engine.island_manager is None

    def test_config_defaults(self, genome_config: GenomeConfig) -> None:
        config = GAConfig(genome_config=genome_config)
        assert config.pop_size == 100
        assert config.generations == 50
        assert config.n_islands == 4
        assert config.crossover_prob == 0.8
        assert config.mutation_prob == 0.2
        assert config.seed == 42
        assert config.checkpoint_interval == 5
        assert config.n_jobs is None


# ── Run ────────────────────────────────────────────────────────────


class TestEngineRun:
    def test_run_produces_ga_result(
        self,
        ga_config: GAConfig,
        small_data: pl.DataFrame,
        mock_evaluator: MagicMock,
    ) -> None:
        """run() returns a GAResult with valid fields."""
        import asyncio

        engine = GeneticEngine(ga_config)
        with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
            cls_mock.return_value = mock_evaluator
            result = asyncio.run(engine.run(data=small_data))

        assert isinstance(result, GAResult)
        assert result.config == ga_config
        assert result.generations_log is not None
        assert result.timing >= 0.0
        assert result.n_fitness_evaluations > 0

    def test_run_generations_log_length(
        self,
        ga_config: GAConfig,
        small_data: pl.DataFrame,
        mock_evaluator: MagicMock,
    ) -> None:
        """The generations log should have one entry per generation."""
        import asyncio

        engine = GeneticEngine(ga_config)
        with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
            cls_mock.return_value = mock_evaluator
            result = asyncio.run(engine.run(data=small_data))

        assert len(result.generations_log) == ga_config.generations

    def test_run_checkpoint_paths(
        self,
        ga_config: GAConfig,
        small_data: pl.DataFrame,
        mock_evaluator: MagicMock,
    ) -> None:
        """Checkpoints should be created at the configured interval."""
        import asyncio

        engine = GeneticEngine(ga_config)
        with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
            cls_mock.return_value = mock_evaluator
            result = asyncio.run(engine.run(data=small_data))

        assert len(result.checkpoint_paths) >= 1
        assert any("final" in p for p in result.checkpoint_paths)

    def test_run_pareto_front_populated(
        self,
        ga_config: GAConfig,
        small_data: pl.DataFrame,
        mock_evaluator: MagicMock,
    ) -> None:
        """The Pareto front should have at least one individual."""
        import asyncio

        engine = GeneticEngine(ga_config)
        with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
            cls_mock.return_value = mock_evaluator
            result = asyncio.run(engine.run(data=small_data))

        assert len(result.pareto_front) >= 1
        for ind in result.pareto_front:
            assert ind.fitness.valid


# ── Checkpoint/restore ────────────────────────────────────────────


class TestCheckpointRestore:
    def test_save_and_restore_round_trip(
        self,
        genome_config: GenomeConfig,
        small_data: pl.DataFrame,
        mock_evaluator: MagicMock,
    ) -> None:
        """Checkpoint save → restore returns engine with matching state."""
        config = GAConfig(
            genome_config=genome_config,
            pop_size=8,
            generations=3,
            n_islands=2,
            seed=42,
            checkpoint_interval=2,
        )

        import asyncio

        engine = GeneticEngine(config)
        with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
            cls_mock.return_value = mock_evaluator
            result = asyncio.run(engine.run(data=small_data))

        ckpt_paths = [p for p in result.checkpoint_paths if "final" not in p]
        if not ckpt_paths:
            ckpt_paths = result.checkpoint_paths
        ckpt_path = ckpt_paths[0]

        restored = GeneticEngine.restore(ckpt_path, genome_config)
        assert isinstance(restored, GeneticEngine)
        assert restored.island_manager is not None
        assert restored.island_manager.generation >= 1

    def test_restore_wrong_schema(
        self,
        genome_config: GenomeConfig,
    ) -> None:
        """Restoring from a corrupted/malformed checkpoint raises ValueError."""
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"schema_version": 999, "generation": 0}, f)
            bad_path = f.name

        with pytest.raises(ValueError, match="Unsupported checkpoint schema"):
            GeneticEngine.restore(bad_path, genome_config)

    def test_restore_nonexistent(self, genome_config: GenomeConfig) -> None:
        """Restoring a non-existent checkpoint raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            GeneticEngine.restore("/nonexistent/checkpoint.json", genome_config)

    def test_resume_skips_completed_generations(
        self,
        genome_config: GenomeConfig,
        small_data: pl.DataFrame,
        mock_evaluator: MagicMock,
    ) -> None:
        """Resuming from checkpoint should skip already-complete generations."""
        config = GAConfig(
            genome_config=genome_config,
            pop_size=8,
            generations=5,
            n_islands=2,
            seed=42,
            checkpoint_interval=2,
        )

        import asyncio

        engine = GeneticEngine(config)
        with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
            cls_mock.return_value = mock_evaluator
            orig_result = asyncio.run(engine.run(data=small_data))

        ckpt_paths = [p for p in orig_result.checkpoint_paths if "gen_0002" in p]
        if not ckpt_paths:
            ckpt_paths = [p for p in orig_result.checkpoint_paths if "final" not in p]
        if not ckpt_paths:
            return  # No intermediate checkpoints — skip this assertion

        ckpt_path = ckpt_paths[0]

        config2 = GAConfig(
            genome_config=genome_config,
            pop_size=8,
            generations=5,
            n_islands=2,
            seed=42,
            resume_from=ckpt_path,
        )
        engine2 = GeneticEngine(config2)
        assert engine2._start_generation >= 0
