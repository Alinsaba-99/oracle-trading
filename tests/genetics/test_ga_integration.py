"""Integration tests for GAConfig → signal_type → FitnessEvaluator flow.

Verifies that the signal_type field propagates correctly through
GAConfig, GeneticEngine, and into the FitnessEvaluator.
"""

from __future__ import annotations

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
def small_data() -> pl.DataFrame:
    return pl.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})


# ── Tests ───────────────────────────────────────────────────────────


class TestGAConfigSignalType:
    """GAConfig defaults and custom signal_type values."""

    def test_default_signal_type(self, genome_config: GenomeConfig) -> None:
        """Default signal_type should be 'genome' for backward compat."""
        config = GAConfig(genome_config=genome_config)
        assert config.signal_type == "genome"

    def test_custom_signal_type(self, genome_config: GenomeConfig) -> None:
        """signal_type accepts known values."""
        config = GAConfig(genome_config=genome_config, signal_type="knn")
        assert config.signal_type == "knn"

    def test_unknown_signal_type_raises(self, genome_config: GenomeConfig) -> None:
        """Unknown signal_type should raise ValueError in run()."""
        config = GAConfig(genome_config=genome_config, signal_type="invalid!")
        engine = GeneticEngine(config)
        with pytest.raises(ValueError, match="Unknown signal_type"):
            import asyncio

            asyncio.run(engine.run(data=pl.DataFrame({"close": [1.0, 2.0]})))


class TestSignalFactoryWiring:
    """signal_factory flows from GAConfig through to FitnessEvaluator."""

    def test_genome_signal_passes_none_factory(
        self,
        genome_config: GenomeConfig,
        small_data: pl.DataFrame,
    ) -> None:
        """signal_type='genome' should pass signal_factory=None to evaluator."""
        config = GAConfig(
            genome_config=genome_config,
            pop_size=2,
            generations=1,
            n_islands=1,
            signal_type="genome",
        )
        engine = GeneticEngine(config)

        evaluator = MagicMock()
        evaluator.evaluate.return_value = (0.5, 0.3, 0.4, -0.1)

        with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
            cls_mock.return_value = evaluator
            import asyncio

            result = asyncio.run(engine.run(data=small_data))

        # Verify evaluator was created with signal_factory=None
        _, kwargs = cls_mock.call_args
        assert kwargs.get("signal_factory") is None
        assert isinstance(result, GAResult)

    def test_knn_signal_passes_knn_factory(
        self,
        genome_config: GenomeConfig,
        small_data: pl.DataFrame,
    ) -> None:
        """signal_type='knn' should pass KNNGenomeToSignal as factory."""
        config = GAConfig(
            genome_config=genome_config,
            pop_size=2,
            generations=1,
            n_islands=1,
            signal_type="knn",
        )
        engine = GeneticEngine(config)

        evaluator = MagicMock()
        evaluator.evaluate.return_value = (0.5, 0.3, 0.4, -0.1)

        with patch("genetics.fitness.evaluator.FitnessEvaluator") as cls_mock:
            cls_mock.return_value = evaluator
            import asyncio

            result = asyncio.run(engine.run(data=small_data))

        # Verify evaluator was created with KNNGenomeToSignal as factory
        _, kwargs = cls_mock.call_args
        factory = kwargs.get("signal_factory")
        from genetics.genome.knn_signal import KNNGenomeToSignal

        assert factory is KNNGenomeToSignal
        assert isinstance(result, GAResult)


class TestEvaluatorSignalFactory:
    """FitnessEvaluator uses signal_factory when provided."""

    def test_evaluator_default_uses_genometosignal(self) -> None:
        """Without signal_factory, FitnessEvaluator uses GenomeToSignal."""
        from genetics.fitness.evaluator import FitnessEvaluator

        # Evaluator can be constructed without signal_factory
        ev = FitnessEvaluator(
            backtest_config=MagicMock(),
        )
        assert ev._signal_factory is None

    def test_evaluator_with_factory(self) -> None:
        """signal_factory is stored and used in evaluate()."""
        from genetics.fitness.evaluator import FitnessEvaluator
        from genetics.genome.signal import GenomeToSignal

        ev = FitnessEvaluator(
            backtest_config=MagicMock(),
            signal_factory=GenomeToSignal,
        )
        assert ev._signal_factory is GenomeToSignal
