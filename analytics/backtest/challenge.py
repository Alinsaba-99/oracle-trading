"""Challenge simulator — replay an equity curve through prop-firm rules.

Takes a backtest equity curve (daily granularity) and a
:class:`PropFirmProfile`, replays it bar-by-bar through the
:class:`PropFirmRiskGovernor`, and reports whether the challenge PASSED
or FAILED plus the failure mode and key statistics.

This is the testbed for Fase 6 (strategy iteration): a strategy is
"good enough" only when the simulator shows it passing The5ers/Lucid
rules with acceptable frequency (see the Fase 7 evaluation harness).

Limitation (v1): the equity curve is treated as daily closing equity,
so daily loss is measured close-to-close.  Real prop firms measure
intraday drawdown; once the MetaTrader5 intraday feed (Fase 5a) lands,
the simulator can consume intraday points and the same logic will
capture true intraday breaches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from policy.prop_firm.governor import Breach, BreachType, ChallengeStatus, PropFirmRiskGovernor
from policy.prop_firm.profile import PropFirmProfile


@dataclass
class ChallengeResult:
    """Outcome of a single simulated challenge."""

    status: ChallengeStatus
    initial_balance: float
    final_balance: float
    total_return: float
    max_drawdown_pct: float
    days_elapsed: int
    target_hit: bool
    breaches: list[Breach] = field(default_factory=list)
    failure_reason: str = ""

    @property
    def passed(self) -> bool:
        return self.status == ChallengeStatus.PASSED


class ChallengeSimulator:
    """Replay a daily equity curve through a :class:`PropFirmProfile`."""

    def __init__(self, profile: PropFirmProfile, initial_balance: float) -> None:
        self.profile = profile
        self.initial_balance = initial_balance

    def run(self, equity: list[float], dates: list[date] | None = None) -> ChallengeResult:
        """Simulate one challenge over the given daily equity curve.

        Args:
            equity: Daily closing equity values (first = initial balance).
            dates: Optional calendar day per bar.  When omitted, bars are
                assumed to be consecutive trading days starting today.
        """
        if not equity:
            return ChallengeResult(
                status=ChallengeStatus.IN_PROGRESS,
                initial_balance=self.initial_balance,
                final_balance=self.initial_balance,
                total_return=0.0,
                max_drawdown_pct=0.0,
                days_elapsed=0,
                target_hit=False,
            )

        gov = PropFirmRiskGovernor(self.profile, self.initial_balance)
        if dates is None:
            today = date.today()
            dates = [today - timedelta(days=len(equity) - 1 - i) for i in range(len(equity))]

        peak = self.initial_balance
        max_dd = 0.0
        breaches: list[Breach] = []
        days_elapsed = 0
        profitable_days = 0
        prev_equity = self.initial_balance
        prev_day = dates[0]

        for eq, d in zip(equity, dates, strict=True):
            # Day rollover (skip the very first bar — day 1 starts at initial).
            if d != prev_day:
                gov.rollover()
                days_elapsed += 1
                prev_day = d

            gov.update(balance=eq, equity=eq)

            # Drawdown bookkeeping
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd

            # Profitable day = closed higher than the previous bar.
            if eq > prev_equity:
                profitable_days += 1
            prev_equity = eq

            # Breach scan (hard breaches end the challenge).
            for b in gov.evaluate():
                if b not in breaches:
                    breaches.append(b)
            if gov.status != ChallengeStatus.IN_PROGRESS:
                return self._finish(gov.status, eq, max_dd, days_elapsed, breaches)

            # Pass condition: profit target + min days met.
            target = self.initial_balance * (1.0 + self.profile.profit_target_pct)
            days_ok = days_elapsed >= self.profile.min_trading_days
            prof_ok = profitable_days >= self.profile.min_profitable_days
            if eq >= target and days_ok and prof_ok:
                return self._finish(ChallengeStatus.PASSED, eq, max_dd, days_elapsed, breaches)

        # Equity exhausted without a terminal outcome.
        return self._finish(gov.status, equity[-1], max_dd, days_elapsed, breaches)

    # ------------------------------------------------------------------
    def _finish(
        self,
        status: ChallengeStatus,
        final: float,
        max_dd: float,
        days_elapsed: int,
        breaches: list[Breach],
    ) -> ChallengeResult:
        total_return = (final - self.initial_balance) / self.initial_balance
        return ChallengeResult(
            status=status,
            initial_balance=self.initial_balance,
            final_balance=final,
            total_return=total_return,
            max_drawdown_pct=max_dd,
            days_elapsed=days_elapsed,
            target_hit=status == ChallengeStatus.PASSED,
            breaches=breaches,
            failure_reason=_failure_reason(status, breaches),
        )


def _failure_reason(status: ChallengeStatus, breaches: list[Breach]) -> str:
    if status == ChallengeStatus.PASSED:
        return ""
    if status == ChallengeStatus.FAILED_DAILY:
        return next(
            (b.message for b in breaches if b.type == BreachType.DAILY_LOSS),
            "Daily loss limit breached",
        )
    if status == ChallengeStatus.FAILED_OVERALL:
        return next(
            (b.message for b in breaches if b.type == BreachType.OVERALL_LOSS),
            "Overall loss limit breached",
        )
    if status == ChallengeStatus.IN_PROGRESS:
        return "Equity exhausted before target hit (did not pass)"
    return status.value
