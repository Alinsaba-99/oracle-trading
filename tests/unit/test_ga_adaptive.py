"""Tests for the adaptive multi-objective GA."""

from __future__ import annotations

import math

import pytest

from analytics.strategy.fitness import EvalMode, FitnessReport
from analytics.strategy.ga_adaptive import (
    AdaptiveGAConfig,
    Individual,
    Objectives,
    adaptive_mutation_rate,
    assign_crowding_distance,
    crowded_compare,
    dominates,
    fast_non_dominated_sort,
    objectives_from,
    population_diversity,
    select_survivors,
    spec_signature,
)
from analytics.strategy.spec import StrategySpec


def _ind(
    fitness: float = 0.5,
    drawdown: float = 0.1,
    sharpe: float = 1.0,
    trades: int = 100,
    *,
    instrument: str = "GOLD",
    entry: str = "ema_trend",
    timeframe: str = "1d",
) -> Individual:
    report = FitnessReport(
        mode=EvalMode.FIRM,
        fitness=fitness,
        max_drawdown=drawdown,
        sharpe=sharpe,
        total_trades=trades,
    )
    spec = StrategySpec(
        name=f"t_{instrument}_{entry}", instrument=instrument, entry=entry, timeframe=timeframe
    )
    return Individual(spec=spec, report=report, objectives=objectives_from(report))


class TestObjectives:
    def test_drawdown_is_negated(self) -> None:
        report = FitnessReport(mode=EvalMode.FIRM, fitness=1.0, max_drawdown=0.25)
        assert objectives_from(report).neg_drawdown == -0.25

    def test_drawdown_sign_is_normalised(self) -> None:
        # Some engines report drawdown negative; both must score identically.
        pos = objectives_from(FitnessReport(mode=EvalMode.FIRM, fitness=0.5, max_drawdown=0.3))
        neg = objectives_from(FitnessReport(mode=EvalMode.FIRM, fitness=0.5, max_drawdown=-0.3))
        assert pos.neg_drawdown == neg.neg_drawdown == -0.3

    def test_trades_are_log_scaled(self) -> None:
        few = objectives_from(FitnessReport(mode=EvalMode.FIRM, fitness=0.5, total_trades=30))
        many = objectives_from(FitnessReport(mode=EvalMode.FIRM, fitness=0.5, total_trades=3000))
        assert few.log_trades < many.log_trades
        # Saturating: a 100x trade count is well under 3x the objective value.
        assert many.log_trades < few.log_trades * 3


class TestDominance:
    def test_strictly_better_dominates(self) -> None:
        better = Objectives(1.0, -0.1, 2.0, 5.0)
        worse = Objectives(0.5, -0.2, 1.0, 4.0)
        assert dominates(better, worse)
        assert not dominates(worse, better)

    def test_identical_does_not_dominate(self) -> None:
        a = Objectives(1.0, -0.1, 2.0, 5.0)
        assert not dominates(a, Objectives(1.0, -0.1, 2.0, 5.0))

    def test_trade_off_is_non_dominated(self) -> None:
        # High return, deep drawdown vs. low return, shallow drawdown.
        aggressive = Objectives(1.0, -0.4, 2.0, 5.0)
        conservative = Objectives(0.6, -0.05, 1.2, 5.0)
        assert not dominates(aggressive, conservative)
        assert not dominates(conservative, aggressive)

    def test_deep_drawdown_cannot_dominate_on_return_alone(self) -> None:
        """The whole point of multi-objective: return alone must not win."""
        reckless = _ind(fitness=0.9, drawdown=0.60, sharpe=0.5, trades=100)
        safe = _ind(fitness=0.5, drawdown=0.05, sharpe=0.5, trades=100)
        assert not dominates(reckless.objectives, safe.objectives)


class TestNonDominatedSort:
    def test_assigns_ranks(self) -> None:
        pop = [
            _ind(fitness=1.0, drawdown=0.05, sharpe=2.0),
            _ind(fitness=0.5, drawdown=0.20, sharpe=1.0),
            _ind(fitness=0.2, drawdown=0.40, sharpe=0.5),
        ]
        fronts = fast_non_dominated_sort(pop)
        assert len(fronts) == 3
        assert pop[0].rank == 0
        assert pop[1].rank == 1
        assert pop[2].rank == 2

    def test_all_in_one_front_when_mutually_non_dominated(self) -> None:
        pop = [
            _ind(fitness=1.0, drawdown=0.40),
            _ind(fitness=0.5, drawdown=0.05),
            _ind(fitness=0.7, drawdown=0.20),
        ]
        fronts = fast_non_dominated_sort(pop)
        assert len(fronts) == 1
        assert len(fronts[0]) == 3

    def test_every_member_is_assigned_to_exactly_one_front(self) -> None:
        pop = [_ind(fitness=i / 10, drawdown=i / 40, sharpe=i / 5) for i in range(12)]
        fronts = fast_non_dominated_sort(pop)
        assert sum(len(f) for f in fronts) == len(pop)

    def test_empty_population(self) -> None:
        assert fast_non_dominated_sort([]) == []


class TestCrowding:
    def test_boundaries_get_infinity(self) -> None:
        front = [_ind(fitness=f, drawdown=0.1) for f in (0.1, 0.5, 0.9)]
        assign_crowding_distance(front)
        assert any(math.isinf(ind.crowding) for ind in front)

    def test_isolated_beats_crowded_at_equal_rank(self) -> None:
        a, b = _ind(), _ind()
        a.rank = b.rank = 0
        a.crowding, b.crowding = 5.0, 1.0
        assert crowded_compare(a, b) is a

    def test_lower_rank_wins_regardless_of_crowding(self) -> None:
        a, b = _ind(), _ind()
        a.rank, b.rank = 0, 1
        a.crowding, b.crowding = 0.0, 99.0
        assert crowded_compare(a, b) is a

    def test_empty_front_is_safe(self) -> None:
        assign_crowding_distance([])


class TestSurvivorSelection:
    def test_truncates_to_requested_size(self) -> None:
        pop = [_ind(fitness=i / 20, drawdown=i / 50) for i in range(20)]
        assert len(select_survivors(pop, 8)) == 8

    def test_returns_all_when_under_capacity(self) -> None:
        pop = [_ind(fitness=0.5) for _ in range(3)]
        assert len(select_survivors(pop, 10)) == 3

    def test_keeps_the_non_dominated_front(self) -> None:
        best = _ind(fitness=1.0, drawdown=0.02, sharpe=3.0, trades=500)
        pop = [best] + [_ind(fitness=0.1, drawdown=0.5, sharpe=0.1, trades=10) for _ in range(10)]
        assert best in select_survivors(pop, 4)


class TestDiversity:
    def test_signature_ignores_parameter_values(self) -> None:
        a = StrategySpec(name="a", instrument="GOLD", entry="ema_trend", entry_params={"fast": 10})
        b = StrategySpec(name="b", instrument="GOLD", entry="ema_trend", entry_params={"fast": 30})
        assert spec_signature(a) == spec_signature(b)

    def test_signature_separates_instruments(self) -> None:
        a = StrategySpec(name="a", instrument="GOLD", entry="ema_trend")
        b = StrategySpec(name="b", instrument="EURUSD", entry="ema_trend")
        assert spec_signature(a) != spec_signature(b)

    def test_all_identical_is_minimum_diversity(self) -> None:
        pop = [_ind() for _ in range(10)]
        assert population_diversity(pop) == pytest.approx(0.1)

    def test_all_distinct_is_full_diversity(self) -> None:
        instruments = ["GOLD", "SILVER", "EURUSD", "GBPUSD", "USDJPY"]
        pop = [_ind(instrument=i) for i in instruments]
        assert population_diversity(pop) == 1.0

    def test_empty_population(self) -> None:
        assert population_diversity([]) == 0.0


class TestAdaptiveMutation:
    def test_rises_as_diversity_falls(self) -> None:
        high = adaptive_mutation_rate(0.9, 0.25)
        low = adaptive_mutation_rate(0.1, 0.25)
        assert low > high

    def test_respects_bounds(self) -> None:
        for diversity in (0.0, 0.25, 0.5, 0.75, 1.0):
            rate = adaptive_mutation_rate(diversity, 0.25, floor=0.15, ceiling=0.85)
            assert 0.15 <= rate <= 0.85

    def test_handles_out_of_range_diversity(self) -> None:
        assert 0.15 <= adaptive_mutation_rate(-1.0, 0.25) <= 0.85
        assert 0.15 <= adaptive_mutation_rate(2.0, 0.25) <= 0.85


class TestConfig:
    def test_defaults_are_sane(self) -> None:
        cfg = AdaptiveGAConfig()
        assert cfg.n_islands >= 2, "island model needs at least two islands"
        assert cfg.pop_per_island > cfg.migration_size
        assert 0.0 < cfg.base_mutation_rate < 1.0
