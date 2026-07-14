"""Monte Carlo challenge evaluation — estimate true pass-probability.

A single backtest that "passes" a prop-firm challenge proves nothing: it
is one historical path.  This module estimates the *probability* that a
strategy passes by sliding a challenge-length window across the full
backtest equity curve, normalising each window to start at the initial
balance, and running the :class:`ChallengeSimulator` on every window.

Rolling-window (not trade-bootstrap) is chosen deliberately: it uses the
strategy's *real* equity paths and therefore captures regime / path
dependence.  Trade bootstrap would assume IID trades and hide serial
structure.  The trade-off is fewer samples — surfaced as ``mc_total`` so
the estimate's weight is visible.

Headline metric: ``mc_pass_rate`` = passes / total windows.  Also
reported: daily-fail rate, overall-fail rate, in-progress (undecided)
rate, mean max drawdown, and median bars-to-resolve.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import polars as pl

from analytics.backtest.challenge import ChallengeSimulator
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult
from analytics.strategy.signals import DEFAULT_STRATEGIES
from policy.prop_firm import THE5ERS
from policy.prop_firm.profile import PropFirmProfile

#: Default challenge window length in bars (~6 months of daily trading).
DEFAULT_WINDOW = 130
#: Stride between window start positions (weekly for daily data).
DEFAULT_STRIDE = 5


@dataclass
class MonteCarloReport:
    """Aggregated outcomes over many simulated challenge windows."""

    total: int = 0
    passes: int = 0
    failed_daily: int = 0
    failed_overall: int = 0
    in_progress: int = 0
    max_drawdowns: list[float] = field(default_factory=list)
    days_to_resolve: list[int] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passes / self.total if self.total else 0.0

    @property
    def failed_daily_rate(self) -> float:
        return self.failed_daily / self.total if self.total else 0.0

    @property
    def failed_overall_rate(self) -> float:
        return self.failed_overall / self.total if self.total else 0.0

    @property
    def in_progress_rate(self) -> float:
        return self.in_progress / self.total if self.total else 0.0

    @property
    def mean_max_drawdown(self) -> float:
        return sum(self.max_drawdowns) / len(self.max_drawdowns) if self.max_drawdowns else 0.0

    @property
    def median_days(self) -> int:
        if not self.days_to_resolve:
            return 0
        ordered = sorted(self.days_to_resolve)
        return ordered[len(ordered) // 2]


def monte_carlo_pass_rate(
    result: BacktestResult,
    profile: PropFirmProfile,
    initial_balance: float = 100_000.0,
    window: int = DEFAULT_WINDOW,
    stride: int = DEFAULT_STRIDE,
) -> MonteCarloReport:
    """Estimate challenge pass-probability by rolling-window simulation.

    Each window is normalised so its first equity value equals
    *initial_balance* (a fresh challenge), then replayed through the
    :class:`ChallengeSimulator`.
    """
    eq = result.equity_curve
    n = len(eq)
    if n < 2:
        return MonteCarloReport()

    if n <= window:
        windows: list[tuple[int, int]] = [(0, n)]
    else:
        windows = [(i, min(i + window, n)) for i in range(0, n - window + 1, stride)]

    report = MonteCarloReport()
    for start, end in windows:
        seg = eq[start:end]
        base = seg[0]
        if base <= 0:
            continue
        normalized = [initial_balance * (v / base) for v in seg]
        outcome = ChallengeSimulator(profile, initial_balance).run(normalized)
        report.total += 1
        report.max_drawdowns.append(outcome.max_drawdown_pct)
        report.days_to_resolve.append(outcome.days_elapsed)
        if outcome.passed:
            report.passes += 1
        elif outcome.status.value == "failed_daily":
            report.failed_daily += 1
        elif outcome.status.value == "failed_overall":
            report.failed_overall += 1
        else:
            report.in_progress += 1
    return report


def monte_carlo_calendar_windows(
    dates: list[date],
    equity: list[float],
    profile: PropFirmProfile,
    initial_balance: float = 100_000.0,
    window_days: int = 60,
    stride_days: int = 5,
) -> MonteCarloReport:
    """Rolling-window Monte Carlo with CALENDAR-DAY windows (multi-timeframe).

    Unlike :func:`monte_carlo_pass_rate` (bar-based, daily only), this slices
    by calendar day so it works for any bar frequency (1d, 1h, ...).  Each
    window is normalised to start at ``initial_balance`` and replayed through
    the :class:`ChallengeSimulator`, which day-rollovers on real dates so the
    daily-loss rule reflects intraday lows for sub-daily data.
    """
    points = list(zip(dates, equity, strict=True))
    unique = sorted({d for d, _ in points})
    report = MonteCarloReport()
    for i in range(0, max(1, len(unique) - window_days + 1), stride_days):
        start_day = unique[i]
        end_day = unique[min(i + window_days, len(unique) - 1)]
        seg = [(d, e) for d, e in points if start_day <= d <= end_day]
        if len(seg) < 2 or seg[0][1] <= 0:
            continue
        norm = [initial_balance * (e / seg[0][1]) for _, e in seg]
        out = ChallengeSimulator(profile, initial_balance).run(
            norm, dates=[d for d, _ in seg]
        )
        report.total += 1
        report.max_drawdowns.append(out.max_drawdown_pct)
        report.days_to_resolve.append(out.days_elapsed)
        if out.passed:
            report.passes += 1
        elif out.status.value == "failed_daily":
            report.failed_daily += 1
        elif out.status.value == "failed_overall":
            report.failed_overall += 1
        else:
            report.in_progress += 1
    return report


@dataclass
class EvalRow:
    """One strategy/instrument with single-path + Monte Carlo metrics."""

    strategy: str
    instrument: str
    single_return: float
    single_status: str
    mc_total: int
    mc_pass_rate: float
    mc_failed_daily_rate: float
    mc_failed_overall_rate: float
    mc_mean_maxdd: float
    mc_median_days: int

    def brief(self) -> str:
        return (
            f"{self.strategy:<22} {self.instrument:<8} "
            f"pass={self.mc_pass_rate * 100:>5.1f}% "
            f"(fail_d={self.mc_failed_daily_rate * 100:>4.1f}% "
            f"fail_o={self.mc_failed_overall_rate * 100:>4.1f}%) "
            f"meanDD={self.mc_mean_maxdd * 100:>5.1f}% "
            f"n={self.mc_total:<3} medDays={self.mc_median_days}"
        )


@dataclass
class EvalReport:
    """Ranked evaluation report — sorted by Monte Carlo pass-rate."""

    rows: list[EvalRow] = field(default_factory=list)

    def as_text(self) -> str:
        lines = ["=== Monte Carlo challenge evaluation (ranked by pass-rate) ==="]
        for r in self.rows:
            lines.append(r.brief())
        return "\n".join(lines)


def evaluate_strategies(
    data_by_inst: dict[str, pl.DataFrame],
    strategies: dict[str, type[BacktestSignal]] | None = None,
    profile: PropFirmProfile | None = None,
    initial_balance: float = 100_000.0,
    window: int = DEFAULT_WINDOW,
    stride: int = DEFAULT_STRIDE,
    backtest_fn: Callable[[pl.DataFrame, BacktestSignal, str], BacktestResult] | None = None,
) -> EvalReport:
    """Evaluate every strategy/instrument with Monte Carlo pass-rate.

    Same shape as :func:`run_sweep` but adds the rolling-window
    pass-probability.  Backtest each combo once, then Monte Carlo the
    equity curve.
    """
    from analytics.strategy.sweep import _default_backtest

    strategies = strategies or DEFAULT_STRATEGIES
    profile = profile or THE5ERS
    backtest_fn = backtest_fn or _default_backtest

    rows: list[EvalRow] = []
    for sname, signal_cls in strategies.items():
        for instrument, data in data_by_inst.items():
            if data.is_empty():
                continue
            result = backtest_fn(data, signal_cls(), instrument)
            mc = monte_carlo_pass_rate(result, profile, initial_balance, window, stride)
            rows.append(
                EvalRow(
                    strategy=sname,
                    instrument=instrument,
                    single_return=result.total_return,
                    single_status=(
                        ChallengeSimulator(profile, initial_balance)
                        .run(result.equity_curve)
                        .status.value
                    ),
                    mc_total=mc.total,
                    mc_pass_rate=mc.pass_rate,
                    mc_failed_daily_rate=mc.failed_daily_rate,
                    mc_failed_overall_rate=mc.failed_overall_rate,
                    mc_mean_maxdd=mc.mean_max_drawdown,
                    mc_median_days=mc.median_days,
                )
            )

    rows.sort(key=lambda r: r.mc_pass_rate, reverse=True)
    return EvalReport(rows=rows)
