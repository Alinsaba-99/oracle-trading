"""Unified fitness function (R3.3) — one scalar per (spec, mode).

Two evaluation modes (user decision 2026-07-14):

- **FIRM**: maximize Monte Carlo pass-rate (probability of +10% before
  any breach). Sharpe ratio as tiebreak. Designed for prop-firm evals
  where breaching once = losing the fee.
- **FREE**: maximize a risk-adjusted return composite (Sharpe/Sortino/CAGR).
  No challenge constraints; used for unconstrained research.

The function returns both a scalar (for ranking/GA fitness) and a
structured :class:`FitnessReport` (for logging / research feedback).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from analytics.backtest.result import BacktestResult
from analytics.strategy.evaluation import MonteCarloReport, monte_carlo_pass_rate
from analytics.strategy.mc_intraday import IntradayMCReport, monte_carlo_intraday_pass_rate
from policy.prop_firm import THE5ERS
from policy.prop_firm.profile import PropFirmProfile


class EvalMode(StrEnum):
    FIRM = "firm"
    FREE = "free"


@dataclass
class FitnessReport:
    """Detailed evaluation of one spec under one mode."""

    mode: EvalMode
    fitness: float  # the scalar, higher = better
    # Backtest metrics
    total_return: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    cagr: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    # MC metrics (FIRM only; populated when timestamps+profile given)
    mc_total: int = 0
    mc_pass_rate: float = 0.0
    mc_failed_daily_rate: float = 0.0
    mc_failed_overall_rate: float = 0.0
    mc_mean_maxdd: float = 0.0
    mc_median_days: int = 0
    # Mode-specific composite for FREE mode
    free_composite: float = 0.0
    extras: dict[str, Any] = field(default_factory=dict)


def fitness(
    result: BacktestResult,
    mode: EvalMode | str,
    *,
    profile: PropFirmProfile | None = None,
    initial_balance: float = 100_000.0,
    timestamps: list[datetime] | None = None,
    mc_window: int = 130,
    mc_stride: int = 5,
    rollover_hour_utc: int = 0,
) -> FitnessReport:
    """Compute the fitness scalar + report for a backtest result.

    Args:
        result: output of a backtest (any engine).
        mode: ``EvalMode.FIRM`` or ``EvalMode.FREE``.
        profile: prop-firm profile for FIRM mode (default THE5ERS).
        initial_balance: MC normalization base.
        timestamps: UTC datetimes aligned with ``result.equity_curve``.
            Required for sub-daily honesty (intraday MC). If omitted,
            daily-bar MC is used (close-to-close).
        mc_window: rolling window size in bars.
        mc_stride: stride between windows.
        rollover_hour_utc: session boundary hour for intraday MC.

    Returns:
        :class:`FitnessReport` with ``fitness`` scalar and detail fields.
    """
    mode = EvalMode(mode)
    profile = profile or THE5ERS

    # Common metrics from the backtest result.
    total_return = float(result.total_return)
    sharpe = float(result.sharpe_ratio)
    sortino = float(result.sortino_ratio)
    cagr = float(result.cagr)
    max_dd = float(result.max_drawdown)
    total_trades = int(result.total_trades)

    if mode == EvalMode.FREE:
        # Composite: prefer high Sharpe, then Sortino (downside), then CAGR.
        # Penalize large drawdown (FREE still wants risk-adjusted, not raw).
        dd_penalty = 1.0 / (1.0 + abs(max_dd))
        composite = (0.5 * sharpe + 0.3 * sortino + 0.2 * (cagr * 10.0)) * dd_penalty
        return FitnessReport(
            mode=mode,
            fitness=composite,
            total_return=total_return,
            sharpe=sharpe,
            sortino=sortino,
            cagr=cagr,
            max_drawdown=max_dd,
            total_trades=total_trades,
            free_composite=composite,
        )

    # FIRM mode: MC pass-rate with Sharpe tiebreak.
    if timestamps is not None:
        mc: MonteCarloReport | IntradayMCReport = monte_carlo_intraday_pass_rate(
            result,
            timestamps,
            profile,
            initial_balance,
            window=mc_window,
            stride=mc_stride,
            rollover_hour_utc=rollover_hour_utc,
        )
    else:
        mc = monte_carlo_pass_rate(result, profile, initial_balance, mc_window, mc_stride)

    pass_rate = mc.pass_rate
    sharpe_tiebreak = sharpe * 0.01  # small nudge
    firm_score = pass_rate + sharpe_tiebreak
    return FitnessReport(
        mode=mode,
        fitness=firm_score,
        total_return=total_return,
        sharpe=sharpe,
        sortino=sortino,
        cagr=cagr,
        max_drawdown=max_dd,
        total_trades=total_trades,
        mc_total=mc.total,
        mc_pass_rate=pass_rate,
        mc_failed_daily_rate=mc.failed_daily_rate,
        mc_failed_overall_rate=mc.failed_overall_rate,
        mc_mean_maxdd=mc.mean_max_drawdown,
        mc_median_days=mc.median_days,
    )
