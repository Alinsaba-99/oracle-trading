"""Tests for the genetics operators module — selection, crossover, mutation, and toolbox factory."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import pytest
from deap import base, creator

from genetics.genome.parameters import (
    CategoricalParameter,
    ContinuousParameter,
    GenomeParameter,
    IntParameter,
)
from genetics.genome.signal import GenomeConfig
from genetics.operators import (
    categorical_mutation,
    create_toolbox,
    crossover_with_validation,
    environmental_selection,
    mutation_with_validation,
    nsga2_selection,
    polynomial_mutation,
    sbx_crossover,
    tournament_selection,
)

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Module-level DEAP type setup  (singleton — double-create is a no-op)
# ---------------------------------------------------------------------------

try:
    creator.create("TestFitness", base.Fitness, weights=(1.0,))
    creator.create("TestFitnessMO", base.Fitness, weights=(1.0, 1.0, 1.0, -1.0))
    creator.create("TestFitness2Obj", base.Fitness, weights=(1.0, 1.0))
    creator.create("TestIndividual", list)
except TypeError:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ind(values: list[float], fvalues: tuple[float, ...] | None = None) -> Any:
    ind = creator.TestIndividual(values)
    ind.fitness = creator.TestFitness()
    if fvalues is not None:
        ind.fitness.values = fvalues
    return ind


def _make_ind_mo(values: list[float], fvalues: tuple[float, float, float, float]) -> Any:
    ind = creator.TestIndividual(values)
    ind.fitness = creator.TestFitnessMO()
    ind.fitness.values = fvalues
    return ind

def _make_ind_2obj(values: list[float], fvalues: tuple[float, float]) -> Any:
    ind = creator.TestIndividual(values)
    ind.fitness = creator.TestFitness2Obj()
    ind.fitness.values = fvalues
    return ind


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_defs() -> list[GenomeParameter]:
    return [
        ContinuousParameter("weight_momentum", low=-2.0, high=2.0),
        ContinuousParameter("weight_vol", low=0.0, high=1.0),
        IntParameter("lookback", low=5, high=50),
        CategoricalParameter("direction", categories=["long", "short"]),
    ]


@pytest.fixture
def genome_config(simple_defs: list[GenomeParameter]) -> GenomeConfig:
    return GenomeConfig(n_params=len(simple_defs), param_defs=simple_defs)


@pytest.fixture
def pop_with_fitness() -> list[Any]:
    pop: list[Any] = []
    for i in range(10):
        ind = _make_ind([random.random() for _ in range(4)], (i / 10.0,))
        pop.append(ind)
    return pop


# ===================================================================
# Crossover tests
# ===================================================================


class TestCrossover:
    """SBX crossover — basic bounds and validated variant."""

    def test_sbx_offspring_in_bounds(self) -> None:
        """Offspring values must stay within [0, 1]."""
        parent_a: list[float] = [0.2, 0.8, 0.4, 0.1]
        parent_b: list[float] = [0.6, 0.3, 0.9, 0.7]
        c1, c2 = sbx_crossover(parent_a[:], parent_b[:])
        for val in c1 + c2:
            assert 0.0 <= val <= 1.0

    def test_crossover_validation_returns_valid(self, genome_config: GenomeConfig) -> None:
        """Validated crossover wrapper returns offspring within [0, 1]."""
        parent_a: list[float] = [0.1, 0.9, 0.3, 0.5]
        parent_b: list[float] = [0.8, 0.2, 0.7, 0.4]
        c1, c2 = crossover_with_validation(parent_a[:], parent_b[:], genome_config)
        for val in c1 + c2:
            assert 0.0 <= val <= 1.0

    def test_crossover_fallback_on_repeated_failure(self) -> None:
        """When all retries produce invalid offspring, original parents are returned."""
        # Use a config whose param_defs has FEWER entries than the individuals
        # so validate_genome always fails (length mismatch).
        bad_defs: list[GenomeParameter] = [
            ContinuousParameter("x", low=0.0, high=1.0),
        ]
        bad_config = GenomeConfig(n_params=1, param_defs=bad_defs)
        parent_a: list[float] = [0.1, 0.9, 0.3, 0.5]
        parent_b: list[float] = [0.8, 0.2, 0.7, 0.4]
        c1, c2 = crossover_with_validation(parent_a[:], parent_b[:], bad_config)
        # Fallback returns pristine copies of originals
        assert c1 == [0.1, 0.9, 0.3, 0.5]
        assert c2 == [0.8, 0.2, 0.7, 0.4]


# ===================================================================
# Mutation tests
# ===================================================================


class TestMutation:
    """Polynomial mutation — bounds and validated variant."""

    def test_polynomial_mutation_bounds(self) -> None:
        """Mutated values must stay within [0, 1]."""
        ind: list[float] = [0.3, 0.5, 0.7, 0.2]
        (mutated,) = polynomial_mutation(ind[:], eta=20.0, indpb=1.0)
        for val in mutated:
            assert 0.0 <= val <= 1.0

    def test_mutation_validation_returns_valid(self, genome_config: GenomeConfig) -> None:
        """Validated mutation returns offspring within [0, 1]."""
        ind: list[float] = [0.3, 0.5, 0.7, 0.2]
        (mutated,) = mutation_with_validation(ind[:], genome_config, eta=20.0, indpb=1.0)
        for val in mutated:
            assert 0.0 <= val <= 1.0

    def test_mutation_validation_fallback(self) -> None:
        """When all retries fail, original individual is returned."""
        bad_defs: list[GenomeParameter] = [
            ContinuousParameter("x", low=0.0, high=1.0),
        ]
        bad_config = GenomeConfig(n_params=1, param_defs=bad_defs)
        ind: list[float] = [0.3, 0.5, 0.7, 0.2]
        (mutated,) = mutation_with_validation(ind[:], bad_config, eta=20.0, indpb=1.0)
        assert mutated == ind

    def test_categorical_mutation_swaps(self) -> None:
        """Categorical mutation actually changes categories with high probability."""
        # 2 categories at index 3 → normalised values are 0.0 or 1.0
        ind: list[float] = [0.5, 0.5, 0.5, 0.0]
        original = ind[:]

        cat_indices = {3: 2}  # index 3 has 2 categories
        (mutated,) = categorical_mutation(ind[:], cat_indices, indpb=1.0)
        # Must have swapped from category 0 (0.0) to category 1 (1.0)
        assert mutated[3] == 1.0
        # Non-categorical positions must be unchanged — but sbx/mutation may
        # also touch them; we just verify the categorical position changed.
        assert mutated[3] != original[3]

    def test_categorical_mutation_noop_on_single_category(self) -> None:
        """A single category leaves the value unchanged."""
        ind: list[float] = [0.5, 0.5, 0.5, 0.0]
        cat_indices = {3: 1}  # only 1 category — no valid swap
        (mutated,) = categorical_mutation(ind[:], cat_indices, indpb=1.0)
        assert mutated[3] == 0.0


# ===================================================================
# Selection tests
# ===================================================================


class TestSelection:
    """Tournament and NSGA-II selection."""

    def test_tournament_selection_count(self, pop_with_fitness: list[Any]) -> None:
        """Tournament selection must return exactly k individuals."""
        selected = tournament_selection(pop_with_fitness, k=5, tournsize=3)
        assert len(selected) == 5

    def test_tournament_selection_pop_size_one(self) -> None:
        """With a single individual, selection returns it repeatedly."""
        ind = _make_ind([0.5, 0.5, 0.5, 0.5], (0.8,))
        selected = tournament_selection([ind], k=3, tournsize=1)
        assert len(selected) == 3
        assert selected[0] is ind
        assert selected[1] is ind
        assert selected[2] is ind

    def test_tournament_selection_all_identical(self) -> None:
        """All-identical individuals should still be selectable."""
        inds = [_make_ind([0.5, 0.5], (1.0,)) for _ in range(10)]
        selected = tournament_selection(inds, k=5, tournsize=3)
        assert len(selected) == 5

    def test_tournament_selection_extreme_fitness(self) -> None:
        """Best individual dominates selection under strong fitness gradient."""
        best = _make_ind([0.9], (1.0,))
        worst = _make_ind([0.1], (0.0,))
        population = [worst] * 9 + [best]
        selected = tournament_selection(population, k=10, tournsize=3)
        # The best individual should be selected at least once with high
        # probability (virtually guaranteed with tournsize=3 and 10 picks).
        assert best in selected

    def test_nsga2_selection_basic(self) -> None:
        """NSGA-II crowded tournament runs without error."""
        population = [_make_ind([0.5, 0.5], (i / 10.0,)) for i in range(10)]
        # selTournamentDCD requires crowding_dist — assign it
        for ind in population:
            ind.fitness.crowding_dist = 1.0
        selected = nsga2_selection(population, k=4)
        assert len(selected) == 4

    def test_environmental_selection_preserves_pareto_front(self) -> None:
        """Environmental selection retains Pareto-optimal individuals."""
        # 2-objective maximisation (weights = (+1.0, +1.0))
        # Pareto front (3 individuals, non-dominated w.r.t. each other):
        front_fvals = [(0.9, 0.1), (0.6, 0.5), (0.2, 0.9)]
        # Dominated (3 individuals, dominated by at least one front member):
        dominated_fvals = [(0.4, 0.3), (0.3, 0.4), (0.5, 0.2)]

        population: list[Any] = []
        for fv in front_fvals + dominated_fvals:
            population.append(_make_ind_2obj([0.0, 0.0], fv))

        selected = environmental_selection(population, k=3)
        assert len(selected) == 3
        # All selected individuals should be from the Pareto front
        for ind in selected:
            assert ind.fitness.values in front_fvals  # type: ignore[attr-defined]


# ===================================================================
# Toolbox factory
# ===================================================================


class TestToolboxFactory:
    """create_toolbox builds a correctly configured DEAP Toolbox."""

    def test_create_toolbox(self, genome_config: GenomeConfig) -> None:
        """All expected aliases are registered and produce valid data."""
        toolbox = create_toolbox(genome_config, use_validation=False)

        # Aliases present
        for alias in (
            "individual",
            "population",
            "mate",
            "mutate",
            "select",
            "select_dcd",
            "select_nsga2",
        ):
            assert hasattr(toolbox, alias), f"Missing alias {alias!r}"

        # Individual has correct length and bounds
        ind = toolbox.individual()
        assert len(ind) == genome_config.n_params
        assert all(0.0 <= v <= 1.0 for v in ind)

        # Population has correct size
        pop = toolbox.population(n=7)
        assert len(pop) == 7
        for member in pop:
            assert len(member) == genome_config.n_params

    def test_create_toolbox_with_validation(self, genome_config: GenomeConfig) -> None:
        """Validation-flagged toolbox registers different mates/mutates."""
        toolbox = create_toolbox(genome_config, use_validation=True)
        assert toolbox.individual
        assert toolbox.population
        # Mate and mutate are registered (we just check they don't raise)
        toolbox.mate(toolbox.individual(), toolbox.individual())
        toolbox.mutate(toolbox.individual())

    def test_create_toolbox_empty_config(self) -> None:
        """Zero-parameter genome produces length-0 individuals."""
        config = GenomeConfig(n_params=0, param_defs=[])
        toolbox = create_toolbox(config)
        ind = toolbox.individual()
        assert len(ind) == 0
        pop = toolbox.population(n=3)
        assert all(len(m) == 0 for m in pop)
