"""Strategy sweep — rank strategies/instruments by challenge pass-probability.

For each (strategy, instrument) pair: backtest on real data, then replay
the equity curve through the :class:`ChallengeSimulator` under a
:class:`PropFirmProfile`.  Results are ranked by pass-first then total
return — because for a prop-firm challenge the only thing that matters
is hitting +target% before breaching the daily/overall limits.

This is the Fase 6 search tool: it surfaces which style (trend vs
mean-reversion vs breakout) and which instrument has any edge at all
under the prop-firm rules, guiding where to focus the GA / strategy
iteration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import polars as pl

from analytics.backtest.challenge import ChallengeSimulator
from analytics.backtest.orchestrator import BacktestOrchestrator
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult
from analytics.strategy.signals import DEFAULT_STRATEGIES
from policy.prop_firm import THE5ERS
from policy.prop_firm.profile import PropFirmProfile


@dataclass
class SweepRow:
    """One (strategy, instrument) evaluation result."""

    strategy: str
    instrument: str
    sharpe: float
    total_return: float
    max_drawdown: float
    profit_factor: float
    total_trades: int
    challenge_status: str
    challenge_days: int
    failure_reason: str
    passed: bool

    def brief(self) -> str:
        flag = "PASS" if self.passed else "    "
        return (
            f"{flag} {self.strategy:<22} {self.instrument:<8} "
            f"sharpe={self.sharpe:>6.2f} ret={self.total_return * 100:>6.2f}% "
            f"dd={self.max_drawdown * 100:>5.2f}% pf={self.profit_factor:>5.2f} "
            f"trades={self.total_trades:>3} -> {self.challenge_status}"
        )


@dataclass
class SweepReport:
    """Ranked collection of sweep rows."""

    rows: list[SweepRow] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.rows if r.passed)

    def as_text(self) -> str:
        lines = [f"=== Strategy sweep: {self.pass_count}/{len(self.rows)} pass ==="]
        for r in self.rows:
            lines.append(r.brief())
        return "\n".join(lines)


def _default_backtest(
    data: pl.DataFrame, signal: BacktestSignal, instrument_id: str
) -> BacktestResult:
    """Backtest via the orchestrator (real vectorized engine)."""
    return BacktestOrchestrator().run(
        signal, engine="vectorized", instrument_id=instrument_id, data=data
    )


def run_sweep(
    data_by_inst: dict[str, pl.DataFrame],
    strategies: dict[str, type[BacktestSignal]] | None = None,
    profile: PropFirmProfile | None = None,
    initial_balance: float = 100_000.0,
    backtest_fn: Callable[[pl.DataFrame, BacktestSignal, str], BacktestResult] | None = None,
) -> SweepReport:
    """Evaluate every strategy on every instrument; rank by challenge outcome.

    Args:
        data_by_inst: Pre-fetched OHLCV per instrument (caller fetches, so the
            sweep itself is network-free and unit-testable).
        strategies: Name -> signal class registry.  Defaults to
            :data:`DEFAULT_STRATEGIES`.
        profile: Prop-firm profile for the challenge simulator.
        initial_balance: Challenge starting balance.
        backtest_fn: ``(data, signal, instrument_id) -> BacktestResult``;
            defaults to the real orchestrator.  Inject a stub for tests.
    """
    strategies = strategies or DEFAULT_STRATEGIES
    profile = profile or THE5ERS
    backtest_fn = backtest_fn or _default_backtest

    rows: list[SweepRow] = []
    for sname, signal_cls in strategies.items():
        for instrument, data in data_by_inst.items():
            if data.is_empty():
                continue
            result = backtest_fn(data, signal_cls(), instrument)
            chal = ChallengeSimulator(profile, initial_balance).run(result.equity_curve)
            rows.append(
                SweepRow(
                    strategy=sname,
                    instrument=instrument,
                    sharpe=result.sharpe_ratio,
                    total_return=result.total_return,
                    max_drawdown=result.max_drawdown,
                    profit_factor=result.profit_factor,
                    total_trades=result.total_trades,
                    challenge_status=chal.status.value,
                    challenge_days=chal.days_elapsed,
                    failure_reason=chal.failure_reason,
                    passed=chal.passed,
                )
            )

    # Pass first, then by total return descending.
    rows.sort(key=lambda r: (not r.passed, -r.total_return))
    return SweepReport(rows=rows)
