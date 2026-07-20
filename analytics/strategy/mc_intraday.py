"""Intraday-honest Monte Carlo pass-rate (R3.2).

Standard ``monte_carlo_pass_rate`` in ``analytics.strategy.evaluation``
rolls a daily equity curve through :class:`ChallengeSimulator`, which
measures daily loss close-to-close. Real prop firms mark intraday: a
5-minute dip through the daily limit fails the challenge even if the
session closes flat. This module extends the Monte Carlo to sub-daily
TFs using :func:`analytics.backtest.challenge_intraday.run_intraday`.

The interface mirrors ``monte_carlo_pass_rate``: take a BacktestResult
(equity + matching timestamps), slice into rolling windows, normalize
each to ``initial_balance``, and replay through ``run_intraday``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from analytics.backtest.challenge import ChallengeResult
from analytics.backtest.challenge_intraday import run_intraday
from analytics.backtest.result import BacktestResult
from policy.prop_firm.governor import ChallengeStatus
from policy.prop_firm.profile import PropFirmProfile


@dataclass
class IntradayMCReport:
    """Aggregated intraday Monte Carlo outcome."""

    total: int = 0
    passed: int = 0
    failed_daily: int = 0
    failed_overall: int = 0
    in_progress: int = 0
    max_drawdowns: list[float] | None = None
    days_elapsed: list[int] | None = None

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def failed_daily_rate(self) -> float:
        return self.failed_daily / self.total if self.total else 0.0

    @property
    def failed_overall_rate(self) -> float:
        return self.failed_overall / self.total if self.total else 0.0

    @property
    def mean_max_drawdown(self) -> float:
        if not self.max_drawdowns:
            return 0.0
        return sum(self.max_drawdowns) / len(self.max_drawdowns)

    @property
    def median_days(self) -> int:
        if not self.days_elapsed:
            return 0
        s = sorted(self.days_elapsed)
        return s[len(s) // 2]


def monte_carlo_intraday_pass_rate(
    result: BacktestResult,
    timestamps: list[datetime],
    profile: PropFirmProfile,
    initial_balance: float = 100_000.0,
    *,
    window: int = 130,
    stride: int = 5,
    rollover_hour_utc: int = 0,
) -> IntradayMCReport:
    """Rolling-window intraday Monte Carlo.

    Args:
        result: backtest result with ``equity_curve``.
        timestamps: UTC datetimes aligned with ``result.equity_curve``
            (same length). Required for sub-daily honesty.
        profile: prop-firm profile (e.g. THE5ERS).
        initial_balance: starting balance each window is normalized to.
        window: bars per window (in the equity curve's bar size).
        stride: step between consecutive windows.
        rollover_hour_utc: session boundary for daily reset.

    Returns:
        :class:`IntradayMCReport` aggregated over all windows.
    """
    equity = list(result.equity_curve)
    if len(equity) != len(timestamps):
        raise ValueError(
            f"equity and timestamps length mismatch: {len(equity)} vs {len(timestamps)}"
        )

    report = IntradayMCReport(max_drawdowns=[], days_elapsed=[])
    if len(equity) < window:
        return report

    for start in range(0, len(equity) - window + 1, stride):
        window_eq = equity[start : start + window]
        window_ts = timestamps[start : start + window]
        if not window_eq or window_eq[0] == 0:
            continue
        # Normalize window so it starts at initial_balance.
        scale = initial_balance / window_eq[0]
        normalized = [e * scale for e in window_eq]
        res: ChallengeResult = run_intraday(
            profile, initial_balance, normalized, window_ts, rollover_hour_utc=rollover_hour_utc
        )
        report.total += 1
        assert report.max_drawdowns is not None
        assert report.days_elapsed is not None
        report.max_drawdowns.append(res.max_drawdown_pct)
        report.days_elapsed.append(res.days_elapsed)
        if res.status == ChallengeStatus.PASSED:
            report.passed += 1
        elif res.status == ChallengeStatus.FAILED_DAILY:
            report.failed_daily += 1
        elif res.status == ChallengeStatus.FAILED_OVERALL:
            report.failed_overall += 1
        else:
            report.in_progress += 1

    return report
