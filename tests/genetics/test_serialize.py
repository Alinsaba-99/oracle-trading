"""Tests for serialization helpers — genome, population, config round-trips."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest

from genetics.genome.parameters import ContinuousParameter, IntParameter
from genetics.genome.signal import Genome, GenomeConfig
from genetics.serialize import (
    config_to_dict,
    dict_to_genome,
    genome_to_dict,
    pop_snapshot,
    population_to_dict,
    result_to_dict,
)

if TYPE_CHECKING:

    from genetics.genome.parameters import GenomeParameter


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def simple_defs() -> list[GenomeParameter]:
    return [
        ContinuousParameter("alpha", low=0.0, high=1.0),
        IntParameter("period", low=5, high=100),
        ContinuousParameter("threshold", low=-5.0, high=5.0),
    ]


@pytest.fixture
def genome_config(simple_defs: list[GenomeParameter]) -> GenomeConfig:
    return GenomeConfig(n_params=len(simple_defs), param_defs=simple_defs)


@pytest.fixture
def genome(simple_defs: list[GenomeParameter]) -> Genome:
    return Genome(
        normalized_params=np.array([0.5, 0.3, 0.9], dtype=np.float64),
        param_defs=simple_defs,
    )


# ── genome_to_dict / dict_to_genome round-trip ─────────────────────


class TestGenomeRoundTrip:
    def test_round_trip(self, genome: Genome) -> None:
        d = genome_to_dict(genome)
        assert "normalized_params" in d
        assert "param_names" in d
        assert d["normalized_params"] == [0.5, 0.3, 0.9]
        assert d["param_names"] == ["alpha", "period", "threshold"]

        restored = dict_to_genome(d, genome.param_defs)
        assert np.allclose(restored.normalized_params, genome.normalized_params)
        assert list(restored.names) == list(genome.names)

    def test_json_serializable(self, genome: Genome) -> None:
        d = genome_to_dict(genome)
        encoded = json.dumps(d)
        decoded = json.loads(encoded)
        restored = dict_to_genome(decoded, genome.param_defs)
        assert np.allclose(restored.normalized_params, genome.normalized_params)

    def test_dict_to_genome_wrong_size(self, simple_defs: list[GenomeParameter]) -> None:
        d = {"normalized_params": [0.1, 0.2], "param_names": ["a", "b"]}
        with pytest.raises(ValueError, match="Parameter count mismatch"):
            dict_to_genome(d, simple_defs)


# ── Population serialization ───────────────────────────────────────


class TestPopulationSerialization:
    def test_population_round_trip(self, genome_config: GenomeConfig) -> None:
        from deap import base, creator

        # Ensure creator types exist
        if not hasattr(creator, "FitnessMulti"):
            creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list)

        # Build a small population with fitness
        toolbox = base.Toolbox()
        toolbox.register("attr_float", np.random.random)
        toolbox.register(
            "individual",
            lambda: creator.Individual([toolbox.attr_float() for _ in range(3)]),
        )
        toolbox.register("population", lambda n: [toolbox.individual() for _ in range(n)])

        pop = toolbox.population(5)
        for i, ind in enumerate(pop):
            ind.fitness = creator.FitnessMulti()
            ind.fitness.values = (float(i), float(i * 2), float(i * 3), float(-i))

        serialized = population_to_dict(pop)
        assert len(serialized) == 5
        for entry in serialized:
            assert "values" in entry
            assert "fitness" in entry
            assert len(entry["fitness"]["values"]) == 4

        # JSON round-trip
        encoded = json.dumps(serialized)
        decoded = json.loads(encoded)
        assert len(decoded) == 5

    def test_population_no_fitness(self, genome_config: GenomeConfig) -> None:
        from deap import base, creator

        if not hasattr(creator, "FitnessMulti"):
            creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list)

        toolbox = base.Toolbox()
        toolbox.register("attr_float", np.random.random)
        toolbox.register(
            "individual",
            lambda: creator.Individual([toolbox.attr_float() for _ in range(3)]),
        )

        pop = [toolbox.individual() for _ in range(3)]
        serialized = population_to_dict(pop)
        for entry in serialized:
            assert "fitness" not in entry

    def test_pop_snapshot_shape(self, genome_config: GenomeConfig) -> None:
        from deap import base, creator

        if not hasattr(creator, "FitnessMulti"):
            creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list)

        toolbox = base.Toolbox()
        toolbox.register("attr_float", lambda: 0.5)
        toolbox.register(
            "individual",
            lambda: creator.Individual([toolbox.attr_float() for _ in range(3)]),
        )
        pop = [toolbox.individual() for _ in range(2)]

        snapshot = pop_snapshot(
            population=pop,
            generation=5,
            pareto_indices=[0],
            diversity=0.75,
        )
        assert snapshot["generation"] == 5
        assert snapshot["population_size"] == 2
        assert snapshot["pareto_indices"] == [0]
        assert snapshot["diversity"] == 0.75
        assert len(snapshot["population"]) == 2


# ── NaN / inf in fitness ───────────────────────────────────────────


class TestSanitizeFitness:
    def test_nan_and_inf_fitness(self) -> None:
        from deap import base, creator

        if not hasattr(creator, "FitnessMulti"):
            creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list)

        ind = creator.Individual([0.1, 0.2, 0.3])
        ind.fitness = creator.FitnessMulti()
        ind.fitness.values = (float("nan"), float("inf"), float("-inf"), 1.0)

        serialized = population_to_dict([ind])
        fit_vals = serialized[0]["fitness"]["values"]
        assert fit_vals[0] == 0.0  # nan → 0.0
        assert fit_vals[1] == 1e6  # inf → 1e6
        assert fit_vals[2] == -1e6  # -inf → -1e6
        assert fit_vals[3] == 1.0


# ── config_to_dict ─────────────────────────────────────────────────


class TestConfigToDict:
    def test_genome_config(self, genome_config: GenomeConfig) -> None:
        d = config_to_dict(genome_config)
        assert "n_params" in d
        assert d["n_params"] == 3
        assert "param_defs" in d
        assert len(d["param_defs"]) == 3

    def test_genome_config_json(self, genome_config: GenomeConfig) -> None:
        d = config_to_dict(genome_config)
        encoded = json.dumps(d, default=str)
        decoded = json.loads(encoded)
        assert decoded["n_params"] == 3


# ── result_to_dict ─────────────────────────────────────────────────


class TestResultToDict:
    def test_result_to_dict_type_check(self) -> None:
        with pytest.raises(TypeError, match="Expected GAResult"):
            result_to_dict("not_a_result")

    def test_result_to_dict_round_trip(self) -> None:
        from deap import base, creator

        if not hasattr(creator, "FitnessMulti"):
            creator.create("FitnessMulti", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list)

        from genetics.engine import GAConfig, GAResult

        config = GAConfig(
            genome_config=GenomeConfig(
                n_params=2,
                param_defs=[
                    ContinuousParameter("a", low=0.0, high=1.0),
                    ContinuousParameter("b", low=0.0, high=1.0),
                ],
            ),
            pop_size=10,
            generations=5,
        )

        hof: list = []
        result = GAResult(
            config=config,
            pareto_front=[],
            hall_of_fame=hof,
            generations_log=[
                {"generation": 0, "n_pareto": 3},
                {"generation": 1, "n_pareto": 4},
            ],
            timing=12.3456,
            checkpoint_paths=["ckpt1.json"],
            n_fitness_evaluations=100,
        )

        d = result_to_dict(result)
        assert d["timing"] == 12.3456
        assert len(d["generations_log"]) == 2
        assert d["n_fitness_evaluations"] == 100
