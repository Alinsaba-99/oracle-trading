"""Tests for the stress gauntlet's gating and scoring logic."""

from __future__ import annotations

import pytest

from analytics.strategy.fitness import EvalMode
from analytics.strategy.stress_gauntlet import (
    CRISIS_PERIODS,
    CrisisResult,
    GauntletReport,
    GauntletThresholds,
    _robustness_score,
    gauntlet_stats,
    rank_survivors,
)


def _report(
    *,
    passed: bool = True,
    mc: float = 0.7,
    wf_median: float = 0.5,
    stability: float = 0.5,
    crisis: float = 0.9,
    name: str = "spec",
) -> GauntletReport:
    report = GauntletReport(spec_name=name, instrument="GOLD", mode=EvalMode.FIRM)
    report.passed = passed
    report.baseline_mc_pass_rate = mc
    report.wf_median_fitness = wf_median
    report.wf_sharpe_stability = stability
    report.crisis_survival_rate = crisis
    report.robustness_score = _robustness_score(report)
    return report


class TestCrisisPeriods:
    def test_periods_are_chronological(self) -> None:
        starts = [p.start for p in CRISIS_PERIODS]
        assert starts == sorted(starts)

    def test_every_period_is_well_formed(self) -> None:
        for period in CRISIS_PERIODS:
            assert period.start < period.end, period.name
            assert period.note, f"{period.name} needs a rationale"

    def test_names_are_unique(self) -> None:
        names = [p.name for p in CRISIS_PERIODS]
        assert len(names) == len(set(names))

    def test_chf_depeg_is_scoped_to_chf_pairs(self) -> None:
        depeg = next(p for p in CRISIS_PERIODS if p.name == "chf_depeg_2015")
        assert depeg.applies_to("EURCHF")
        assert not depeg.applies_to("BTC")

    def test_unscoped_period_applies_everywhere(self) -> None:
        covid = next(p for p in CRISIS_PERIODS if p.name == "covid_2020")
        assert covid.applies_to("GOLD")
        assert covid.applies_to("EURUSD")
        assert covid.applies_to("BTC")

    def test_instrument_match_is_case_insensitive(self) -> None:
        depeg = next(p for p in CRISIS_PERIODS if p.name == "chf_depeg_2015")
        assert depeg.applies_to("eurchf")


class TestRobustnessScore:
    def test_zero_in_any_dimension_zeroes_the_score(self) -> None:
        """A single fatal weakness must not be averaged away."""
        assert _robustness_score(_report(crisis=0.0)) == 0.0
        assert _robustness_score(_report(mc=0.0)) == 0.0
        assert _robustness_score(_report(wf_median=0.0)) == 0.0
        assert _robustness_score(_report(stability=0.0)) == 0.0

    def test_all_perfect_is_one(self) -> None:
        score = _robustness_score(_report(mc=1.0, wf_median=1.0, stability=1.0, crisis=1.0))
        assert score == pytest.approx(1.0)

    def test_geometric_mean_punishes_imbalance(self) -> None:
        # Same arithmetic mean; the lopsided one must score lower.
        balanced = _robustness_score(_report(mc=0.5, wf_median=0.5, stability=0.5, crisis=0.5))
        lopsided = _robustness_score(_report(mc=0.95, wf_median=0.95, stability=0.05, crisis=0.05))
        assert lopsided < balanced

    def test_score_is_bounded(self) -> None:
        # Out-of-range inputs are clamped, not extrapolated.
        score = _robustness_score(_report(mc=5.0, wf_median=9.0, stability=3.0, crisis=2.0))
        assert 0.0 <= score <= 1.0


class TestRanking:
    def test_survivors_rank_above_failures(self) -> None:
        strong_failure = _report(passed=False, mc=0.99, wf_median=0.99, crisis=0.99)
        weak_pass = _report(passed=True, mc=0.61, wf_median=0.31, crisis=0.71)
        ranked = rank_survivors([strong_failure, weak_pass])
        assert ranked[0] is weak_pass, "a passing spec must outrank any rejected one"

    def test_survivors_ordered_by_robustness(self) -> None:
        low = _report(name="low", mc=0.62, wf_median=0.32, stability=0.2, crisis=0.72)
        high = _report(name="high", mc=0.95, wf_median=0.9, stability=0.8, crisis=1.0)
        ranked = rank_survivors([low, high])
        assert [r.spec_name for r in ranked] == ["high", "low"]

    def test_empty_input(self) -> None:
        assert rank_survivors([]) == []


class TestStats:
    def test_counts_and_fraction(self) -> None:
        reports = [_report(passed=True), _report(passed=False), _report(passed=False)]
        stats = gauntlet_stats(reports)
        assert stats["n_evaluated"] == 3
        assert stats["n_passed"] == 1
        assert stats["pass_fraction"] == pytest.approx(1 / 3)

    def test_empty_returns_empty(self) -> None:
        assert gauntlet_stats([]) == {}


class TestThresholds:
    def test_defaults_are_demanding(self) -> None:
        th = GauntletThresholds()
        # These are the numbers that make the gate meaningful; if they drift
        # down, the gauntlet stops rejecting overfit specs.
        assert th.min_mc_pass_rate >= 0.5
        assert th.min_crisis_survival >= 0.5
        assert th.min_total_trades >= 20
        assert th.max_drawdown <= 0.25

    def test_crisis_fitness_floor_allows_small_losses(self) -> None:
        # Surviving a crisis slightly down is acceptable; being wiped out is not.
        assert GauntletThresholds().min_crisis_fitness <= 0.0


class TestReportSummary:
    def test_pass_summary_mentions_pass(self) -> None:
        assert "[PASS]" in _report(passed=True).summary()

    def test_fail_summary_includes_reasons(self) -> None:
        report = _report(passed=False)
        report.failures = ["MC pass-rate 12.0% < 60%"]
        text = report.summary()
        assert "[FAIL]" in text
        assert "MC pass-rate" in text


class TestCrisisResult:
    def test_defaults_are_not_survived(self) -> None:
        # Absence of evidence must not read as success.
        result = CrisisResult(name="x")
        assert result.survived is False
        assert result.skipped is False
