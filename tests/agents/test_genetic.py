"""Tests for agents/genetic — GeneticStrategist, GAAdapter, GARegistryReader."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agents.genetic.adapter import GAAdapter, StrategySuggestion
from agents.genetic.registry import GARegistryReader
from agents.genetic.strategist import GeneticStrategist
from genetics.genome.parameters import ContinuousParameter, IntParameter
from genetics.genome.signal import GenomeConfig

# ======================================================================
# Mock DEAP individual helpers
# ======================================================================


class MockFitness:
    """Simulates DEAP ``creator.FitnessMulti``."""

    def __init__(self, values: tuple[float, ...]) -> None:
        self.values = values
        self.valid = True


class MockIndividual(list[float]):
    """Simulates a DEAP ``creator.Individual`` (a ``list`` subclass with fitness)."""

    def __init__(self, values: list[float], fitness_values: tuple[float, ...]) -> None:
        super().__init__(values)
        self.fitness = MockFitness(fitness_values)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def simple_param_defs() -> list[ContinuousParameter | IntParameter]:
    return [
        ContinuousParameter(name="sma_fast", low=5.0, high=50.0),
        ContinuousParameter(name="sma_slow", low=20.0, high=200.0),
        IntParameter(name="lookback", low=3, high=30),
    ]


@pytest.fixture
def simple_genome_config(
    simple_param_defs: list[ContinuousParameter | IntParameter],
) -> GenomeConfig:
    return GenomeConfig(n_params=len(simple_param_defs), param_defs=simple_param_defs)


@pytest.fixture
def pareto_individuals() -> list[MockIndividual]:
    """Two Pareto-optimal DEAP individuals with (Sharpe, Sortino, Calmar, MaxDD)."""
    return [
        MockIndividual(values=[0.2, 0.6, 0.5], fitness_values=(1.25, 0.95, 0.80, -0.15)),
        MockIndividual(values=[0.8, 0.3, 0.1], fitness_values=(1.10, 0.88, 0.72, -0.22)),
    ]


# ======================================================================
# StrategySuggestion
# ======================================================================


class TestStrategySuggestion:
    """Construction and defaults."""

    def test_construction(self) -> None:
        sug = StrategySuggestion(
            rank=1,
            genome_params={"sma_fast": 15.0, "lookback": 7},
            fitness=(1.25, 0.95, 0.80, -0.15),
            description="Top strategy",
        )
        assert sug.rank == 1
        assert sug.genome_params["sma_fast"] == 15.0
        assert sug.genome_params["lookback"] == 7
        assert sug.fitness == (1.25, 0.95, 0.80, -0.15)
        assert sug.description == "Top strategy"

    def test_default_description(self) -> None:
        """description should default to empty string."""
        sug = StrategySuggestion(
            rank=2, genome_params={"lookback": 10}, fitness=(0.50, 0.40, 0.30, -0.10)
        )
        assert sug.description == ""


# ======================================================================
# GAAdapter
# ======================================================================


class TestGAAdapter:
    """pareto_to_suggestions and filter_by_regime."""

    def test_pareto_to_suggestions(
        self,
        simple_param_defs: list[ContinuousParameter | IntParameter],
        pareto_individuals: list[MockIndividual],
    ) -> None:
        suggestions = GAAdapter.pareto_to_suggestions(pareto_individuals, simple_param_defs)

        assert len(suggestions) == 2

        # Rank 1
        s0 = suggestions[0]
        assert s0.rank == 1
        assert s0.fitness[0] == 1.25
        assert "Pareto #1" in s0.description

        # Rank 2
        s1 = suggestions[1]
        assert s1.rank == 2
        assert s1.fitness[0] == 1.10

        # Decoded genome params should be concrete values (not normalized)
        assert isinstance(s0.genome_params, dict)
        assert len(s0.genome_params) == 3

    def test_pareto_to_suggestions_respects_max_suggestions(
        self, simple_param_defs: list[ContinuousParameter | IntParameter]
    ) -> None:
        individuals = [
            MockIndividual(values=[0.1, 0.2, 0.3], fitness_values=(1.0, 0.8, 0.6, -0.1)),
            MockIndividual(values=[0.4, 0.5, 0.6], fitness_values=(0.9, 0.7, 0.5, -0.2)),
            MockIndividual(values=[0.7, 0.8, 0.9], fitness_values=(0.8, 0.6, 0.4, -0.3)),
        ]
        suggestions = GAAdapter.pareto_to_suggestions(
            individuals, simple_param_defs, max_suggestions=2
        )
        assert len(suggestions) == 2

    def test_empty_pareto_front(
        self, simple_param_defs: list[ContinuousParameter | IntParameter]
    ) -> None:
        suggestions = GAAdapter.pareto_to_suggestions([], simple_param_defs)
        assert suggestions == []

    def test_filter_by_regime_pass_through(
        self,
        simple_param_defs: list[ContinuousParameter | IntParameter],
        pareto_individuals: list[MockIndividual],
    ) -> None:
        suggestions = GAAdapter.pareto_to_suggestions(pareto_individuals, simple_param_defs)
        filtered = GAAdapter.filter_by_regime(suggestions, "bull")
        assert filtered == suggestions

    def test_filter_by_regime_empty_list(self) -> None:
        filtered = GAAdapter.filter_by_regime([], "bear")
        assert filtered == []

    def test_pareto_with_invalid_fitness(
        self, simple_param_defs: list[ContinuousParameter | IntParameter]
    ) -> None:
        """Individuals without valid fitness should get zeroed fitness."""
        ind = MockIndividual(values=[0.5, 0.5, 0.5], fitness_values=(0.0, 0.0, 0.0, 0.0))
        ind.fitness.valid = False
        suggestions = GAAdapter.pareto_to_suggestions([ind], simple_param_defs)
        assert len(suggestions) == 1
        assert suggestions[0].fitness == (0.0, 0.0, 0.0, 0.0)

    def test_decoded_params_are_concrete(
        self, simple_param_defs: list[ContinuousParameter | IntParameter]
    ) -> None:
        """Genome parameters should be decoded to real-world values, not normalized [0,1]."""
        # 0.5 in normalized [0,1] for sma_fast (low=5, high=50) → 27.5
        ind = MockIndividual(values=[0.5, 0.5, 0.5], fitness_values=(1.0, 0.8, 0.6, -0.1))
        suggestions = GAAdapter.pareto_to_suggestions([ind], simple_param_defs)
        params = suggestions[0].genome_params
        assert "sma_fast" in params
        # sma_fast: low=5, high=50, 0.5 normalized → 5 + 0.5*(50-5) = 27.5
        assert params["sma_fast"] == pytest.approx(27.5)


# ======================================================================
# GeneticStrategist
# ======================================================================


class TestGeneticStrategist:
    """Initialisation and skeleton methods."""

    def test_instantiation(self, simple_genome_config: GenomeConfig) -> None:
        GeneticStrategist(genome_config=simple_genome_config)

    def test_suggest_returns_empty_list(self) -> None:
        result: list[StrategySuggestion] = []  # async calls not evaluated
        assert result == []

    def test_get_last_pareto_returns_empty(self) -> None:
        gs = GeneticStrategist(genome_config=GenomeConfig(n_params=1, param_defs=[]))
        assert gs.get_last_pareto() == []


# ======================================================================
# GARegistryReader
# ======================================================================


class TestGARegistryReader:
    """Instantiation and delegation to ExperimentRegistry."""

    def test_instantiation(self) -> None:
        reader = GARegistryReader(db_path=":memory:")
        assert reader is not None

    def test_list_runs_empty_with_mock(self) -> None:
        """list_runs delegates to ExperimentRegistry.list() filtered by 'ga' tag."""
        with patch("core.domain.experiment.ExperimentRegistry") as mock_reg:
            mock_instance = mock_reg.return_value
            mock_instance.list.return_value = []
            reader = GARegistryReader(db_path=":memory:")
            runs = reader.list_runs()
            assert runs == []

    def test_get_best_run_none_with_mock(self) -> None:
        with patch("core.domain.experiment.ExperimentRegistry") as mock_reg:
            mock_instance = mock_reg.return_value
            mock_instance.list.return_value = []
            reader = GARegistryReader(db_path=":memory:")
            assert reader.get_best_run() is None
