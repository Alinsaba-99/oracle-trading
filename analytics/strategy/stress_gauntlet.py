"""Hard-mode robustness gauntlet for strategy specs.

A spec that scores well on a single backtest has proved almost nothing: the
search evaluates tens of thousands of candidates, so the top of the ranking is
exactly where overfitting concentrates. This module is the adversarial filter
that stands between "looked good in search" and "worth risking a funded
account on".

Three independent pressures, each able to reject on its own:

1. **Crisis periods** — the spec is re-run on named historical regimes
   (2008 GFC, the 2015 CHF depeg, the 2020 COVID crash, the 2022 rate shock).
   These are not sampled; they are the specific dates that broke real systems.
2. **Walk-forward folds** — out-of-sample consistency, not just an average.
   A spec carried by one lucky fold is rejected.
3. **Monte Carlo under firm constraints** — pass-rate for reaching the profit
   target before breaching a daily or overall loss cap.

The gate is deliberately conjunctive. Passing on average while failing one
crisis outright is the signature of a curve-fit strategy, so ``GauntletReport``
reports the binding reason rather than a single blended score.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from analytics.backtest.providers import DataRegistry
from analytics.strategy.evaluator import evaluate_spec
from analytics.strategy.fitness import EvalMode, FitnessReport
from analytics.strategy.spec import StrategySpec
from analytics.strategy.walk_forward_spec import WalkForwardReport, walk_forward_spec

log = logging.getLogger("oracle.strategy.stress_gauntlet")


def _utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


@dataclass(frozen=True)
class CrisisPeriod:
    """A historical window that broke real trading systems."""

    name: str
    start: datetime
    end: datetime
    note: str
    #: Instruments this window is meaningful for; empty means all.
    instruments: tuple[str, ...] = ()

    def applies_to(self, instrument: str) -> bool:
        return not self.instruments or instrument.upper() in self.instruments


#: Ordered oldest-first. Chosen because each one is a *different* failure mode,
#: not merely a different date: liquidity collapse, a broken peg, a volatility
#: spike, and a sustained trend regime change.
CRISIS_PERIODS: tuple[CrisisPeriod, ...] = (
    CrisisPeriod(
        name="gfc_2008",
        start=_utc(2008, 6, 1),
        end=_utc(2009, 6, 30),
        note="Global financial crisis — correlations converge to 1, liquidity evaporates",
    ),
    CrisisPeriod(
        name="eurozone_2011",
        start=_utc(2011, 7, 1),
        end=_utc(2012, 6, 30),
        note="Eurozone sovereign debt — sustained EUR weakness with policy shocks",
    ),
    CrisisPeriod(
        name="chf_depeg_2015",
        start=_utc(2015, 1, 1),
        end=_utc(2015, 3, 31),
        note="SNB abandons the EUR/CHF floor — a 30% gap through every stop",
        instruments=("EURCHF", "GBPCHF", "USDCHF"),
    ),
    CrisisPeriod(
        name="brexit_2016",
        start=_utc(2016, 6, 1),
        end=_utc(2016, 12, 31),
        note="Brexit referendum — overnight GBP repricing",
        instruments=("GBPUSD", "GBPJPY", "GBPCHF", "GBPCAD", "GBPAUD", "EURGBP"),
    ),
    CrisisPeriod(
        name="covid_2020",
        start=_utc(2020, 2, 1),
        end=_utc(2020, 6, 30),
        note="COVID crash — fastest drawdown on record, then a V recovery",
    ),
    CrisisPeriod(
        name="rate_shock_2022",
        start=_utc(2022, 1, 1),
        end=_utc(2022, 12, 31),
        note="Synchronised hiking cycle — trend regime inverts versus the prior decade",
    ),
)


@dataclass
class GauntletThresholds:
    """Rejection thresholds. Defaults target a funded prop-firm account.

    ``min_crisis_fitness`` is allowed to be negative: surviving a crisis with a
    small loss is acceptable, being destroyed by one is not.
    """

    #: Monte Carlo probability of hitting the target before any breach.
    min_mc_pass_rate: float = 0.60
    #: Every walk-forward fold must clear this, not just the median.
    min_fold_fitness: float = 0.0
    #: Median across folds — the central expectation.
    min_median_fitness: float = 0.30
    #: min/max Sharpe across folds; low values mean one fold carried the result.
    min_sharpe_stability: float = 0.15
    #: Fraction of folds with a non-zero pass rate.
    min_pass_rate_consistency: float = 0.60
    #: Worst tolerated fitness inside a crisis window.
    min_crisis_fitness: float = -0.10
    #: Worst tolerated drawdown inside a crisis window.
    max_crisis_drawdown: float = 0.25
    #: Fraction of applicable crisis windows that must survive.
    min_crisis_survival: float = 0.70
    #: Too few trades means the metrics are noise, however good they look.
    min_total_trades: int = 30
    #: Guards against a spec whose entire edge is one outlier trade.
    max_drawdown: float = 0.20


@dataclass
class CrisisResult:
    name: str
    fitness: float = 0.0
    sharpe: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    mc_pass_rate: float = 0.0
    survived: bool = False
    skipped: bool = False
    reason: str = ""


@dataclass
class GauntletReport:
    """Verdict for one spec, with the binding rejection reasons."""

    spec_name: str
    instrument: str
    mode: EvalMode
    passed: bool = False
    #: Human-readable reasons the spec failed; empty when it passed.
    failures: list[str] = field(default_factory=list)

    # Baseline (full history)
    baseline_fitness: float = 0.0
    baseline_sharpe: float = 0.0
    baseline_max_drawdown: float = 0.0
    baseline_trades: int = 0
    baseline_mc_pass_rate: float = 0.0

    # Walk-forward
    wf_median_fitness: float = 0.0
    wf_min_fitness: float = 0.0
    wf_sharpe_stability: float = 0.0
    wf_pass_rate_consistency: float = 0.0
    wf_oos_sharpe: float = 0.0
    n_folds: int = 0

    # Crisis
    crisis_results: list[CrisisResult] = field(default_factory=list)
    crisis_survival_rate: float = 0.0
    worst_crisis: str = ""
    worst_crisis_fitness: float = 0.0

    #: Single number for ranking survivors — the weakest link, not the average.
    robustness_score: float = 0.0

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        line = (
            f"[{verdict}] {self.spec_name} ({self.instrument}) "
            f"robustness={self.robustness_score:.3f} "
            f"mc={self.baseline_mc_pass_rate * 100:.0f}% "
            f"wf_med={self.wf_median_fitness:.3f} "
            f"wf_min={self.wf_min_fitness:.3f} "
            f"crisis={self.crisis_survival_rate * 100:.0f}%"
        )
        if self.failures:
            line += "\n    " + "\n    ".join(self.failures)
        return line


def _run_crisis(
    spec: StrategySpec,
    registry: DataRegistry,
    mode: EvalMode,
    period: CrisisPeriod,
    thresholds: GauntletThresholds,
    eval_kwargs: dict[str, Any],
) -> CrisisResult:
    """Evaluate one spec inside one crisis window."""
    result = CrisisResult(name=period.name)
    if not period.applies_to(spec.instrument):
        result.skipped = True
        result.reason = "not applicable to this instrument"
        return result

    try:
        report = evaluate_spec(
            spec, registry, mode, start=period.start, end=period.end, **eval_kwargs
        )
    except Exception as exc:
        result.skipped = True
        result.reason = f"evaluation error: {exc}"
        log.debug("crisis %s failed for %s: %s", period.name, spec.name, exc)
        return result

    result.fitness = report.fitness
    result.sharpe = report.sharpe
    result.total_return = report.total_return
    result.max_drawdown = report.max_drawdown
    result.total_trades = report.total_trades
    result.mc_pass_rate = report.mc_pass_rate

    if report.total_trades == 0:
        # Sitting out a crisis is not a failure — a filter that stands aside
        # during chaos is doing its job. It just yields no evidence either way.
        result.skipped = True
        result.reason = "no trades in window"
        return result

    survived = (
        report.fitness >= thresholds.min_crisis_fitness
        and abs(report.max_drawdown) <= thresholds.max_crisis_drawdown
    )
    result.survived = survived
    if not survived:
        result.reason = f"fitness={report.fitness:.3f} dd={abs(report.max_drawdown) * 100:.1f}%"
    return result


def _check_baseline(base: FitnessReport, mode: EvalMode, th: GauntletThresholds) -> list[str]:
    """Threshold checks against the full-history backtest."""
    failures: list[str] = []
    if base.total_trades < th.min_total_trades:
        failures.append(f"too few trades: {base.total_trades} < {th.min_total_trades}")
    if abs(base.max_drawdown) > th.max_drawdown:
        failures.append(
            f"baseline drawdown {abs(base.max_drawdown) * 100:.1f}% > {th.max_drawdown * 100:.0f}%"
        )
    if mode == EvalMode.FIRM and base.mc_pass_rate < th.min_mc_pass_rate:
        failures.append(
            f"MC pass-rate {base.mc_pass_rate * 100:.1f}% < {th.min_mc_pass_rate * 100:.0f}%"
        )
    return failures


def _check_walk_forward(wf: WalkForwardReport, mode: EvalMode, th: GauntletThresholds) -> list[str]:
    """Threshold checks against out-of-sample fold consistency."""
    failures: list[str] = []
    if wf.median_fitness < th.min_median_fitness:
        failures.append(f"WF median fitness {wf.median_fitness:.3f} < {th.min_median_fitness:.2f}")
    if wf.min_fitness < th.min_fold_fitness:
        failures.append(
            f"worst fold {wf.min_fitness:.3f} < {th.min_fold_fitness:.2f} "
            "(one bad regime breaks it)"
        )
    if wf.sharpe_stability < th.min_sharpe_stability:
        failures.append(
            f"Sharpe stability {wf.sharpe_stability:.3f} < {th.min_sharpe_stability:.2f} "
            "(result concentrated in one fold)"
        )
    if mode == EvalMode.FIRM and wf.pass_rate_consistency < th.min_pass_rate_consistency:
        failures.append(
            f"pass-rate consistency {wf.pass_rate_consistency * 100:.0f}% "
            f"< {th.min_pass_rate_consistency * 100:.0f}%"
        )
    return failures


def run_gauntlet(
    spec: StrategySpec,
    registry: DataRegistry,
    mode: EvalMode | str = EvalMode.FIRM,
    *,
    thresholds: GauntletThresholds | None = None,
    n_splits: int = 6,
    purge_window: int = 10,
    crisis_periods: tuple[CrisisPeriod, ...] = CRISIS_PERIODS,
    eval_kwargs: dict[str, Any] | None = None,
) -> GauntletReport:
    """Put one spec through baseline, walk-forward, and crisis stress.

    Stages run cheapest-first and short-circuit: a spec that cannot clear the
    baseline is not worth six walk-forward folds plus six crisis windows.
    """
    mode = EvalMode(mode)
    th = thresholds or GauntletThresholds()
    kwargs = eval_kwargs or {}
    report = GauntletReport(spec_name=spec.name, instrument=spec.instrument, mode=mode)

    # ── stage 1: baseline over the full history ────────────────────────────
    try:
        base: FitnessReport = evaluate_spec(spec, registry, mode, **kwargs)
    except Exception as exc:
        report.failures.append(f"baseline evaluation failed: {exc}")
        return report

    report.baseline_fitness = base.fitness
    report.baseline_sharpe = base.sharpe
    report.baseline_max_drawdown = base.max_drawdown
    report.baseline_trades = base.total_trades
    report.baseline_mc_pass_rate = base.mc_pass_rate

    report.failures.extend(_check_baseline(base, mode, th))
    if report.failures:
        # Cheap rejection — skip the expensive stages entirely.
        return report

    # ── stage 2: walk-forward out-of-sample consistency ────────────────────
    try:
        wf = walk_forward_spec(
            spec, registry, mode, n_splits=n_splits, purge_window=purge_window, split_method="time"
        )
    except Exception as exc:
        report.failures.append(f"walk-forward failed: {exc}")
        return report

    report.wf_median_fitness = wf.median_fitness
    report.wf_min_fitness = wf.min_fitness
    report.wf_sharpe_stability = wf.sharpe_stability
    report.wf_pass_rate_consistency = wf.pass_rate_consistency
    report.wf_oos_sharpe = wf.oos_sharpe
    report.n_folds = len(wf.fold_reports)

    if report.n_folds == 0:
        report.failures.append("walk-forward produced no folds")
        return report
    report.failures.extend(_check_walk_forward(wf, mode, th))

    # ── stage 3: crisis windows ────────────────────────────────────────────
    # Always run these even if stage 2 failed, so the report explains the full
    # picture rather than stopping at the first tripwire.
    results = [_run_crisis(spec, registry, mode, period, th, kwargs) for period in crisis_periods]
    report.crisis_results = results

    tested = [r for r in results if not r.skipped]
    if tested:
        survivors = [r for r in tested if r.survived]
        report.crisis_survival_rate = len(survivors) / len(tested)
        worst = min(tested, key=lambda r: r.fitness)
        report.worst_crisis = worst.name
        report.worst_crisis_fitness = worst.fitness
        if report.crisis_survival_rate < th.min_crisis_survival:
            failed = ", ".join(f"{r.name}({r.reason})" for r in tested if not r.survived)
            report.failures.append(
                f"crisis survival {report.crisis_survival_rate * 100:.0f}% "
                f"< {th.min_crisis_survival * 100:.0f}% — failed: {failed}"
            )
    else:
        # No crisis window produced trades: the spec is untested, not proven.
        report.crisis_survival_rate = 0.0
        report.failures.append("no crisis window produced any trades (untested)")

    report.passed = not report.failures
    report.robustness_score = _robustness_score(report)
    return report


def _robustness_score(report: GauntletReport) -> float:
    """Rank survivors by their weakest dimension, not their average.

    A geometric-style combination is used deliberately: a spec that is superb
    out-of-sample but dies in one crisis should rank below a spec that is
    merely good at everything, because the former's failure mode is a blown
    account rather than a smaller profit.
    """
    components = [
        max(0.0, min(1.0, report.baseline_mc_pass_rate)),
        max(0.0, min(1.0, report.wf_median_fitness)),
        max(0.0, min(1.0, report.wf_sharpe_stability)),
        max(0.0, min(1.0, report.crisis_survival_rate)),
    ]
    if any(c <= 0.0 for c in components):
        return 0.0
    # Geometric mean: one near-zero dimension drags the whole score down.
    product = 1.0
    for c in components:
        product *= c
    return float(product ** (1.0 / len(components)))


def rank_survivors(reports: list[GauntletReport]) -> list[GauntletReport]:
    """Passing specs first, ordered by robustness."""
    return sorted(reports, key=lambda r: (r.passed, r.robustness_score), reverse=True)


def gauntlet_stats(reports: list[GauntletReport]) -> dict[str, float]:
    """Aggregate view over a batch — how selective was the gate?"""
    if not reports:
        return {}
    passed = [r for r in reports if r.passed]
    scores = [r.robustness_score for r in reports]
    return {
        "n_evaluated": float(len(reports)),
        "n_passed": float(len(passed)),
        "pass_fraction": len(passed) / len(reports),
        "median_robustness": float(statistics.median(scores)),
        "best_robustness": float(max(scores)),
    }
