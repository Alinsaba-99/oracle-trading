"""Intraday-honest challenge replay (R0.6).

:meth:`ChallengeSimulator.run` measures daily loss close-to-close on a *daily*
equity curve. Real prop firms mark intraday drawdown: a dip below the
daily-loss limit **during** a session fails the challenge even if the session
closes flat. That gap is the realism problem the multi-TF pivot targets.

``run_intraday`` feeds every intraday equity point to
:class:`PropFirmRiskGovernor` (whose daily loss is measured from the
session-open equity, reset by ``rollover()``), so intraday dips are caught
honestly. Session boundaries are configurable via ``rollover_hour_utc``
(0 = UTC midnight; 21 ≈ CME settlement / 17:00-ET FX roll). Testable today on
crypto H1 (ccxt), which needs no MetaApi credentials.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from analytics.backtest.challenge import ChallengeResult
from policy.prop_firm.governor import Breach, ChallengeStatus, PropFirmRiskGovernor
from policy.prop_firm.profile import PropFirmProfile


def run_intraday(
    profile: PropFirmProfile,
    initial_balance: float,
    equity: list[float],
    timestamps: list[datetime],
    *,
    rollover_hour_utc: int = 0,
) -> ChallengeResult:
    """Replay an intraday equity curve through ``profile`` (intraday-honest).

    Args:
        profile: Prop-firm rule set.
        initial_balance: Starting account balance (== ``equity[0]``).
        equity: Intraday equity points, finest granularity available.
        timestamps: tz-aware UTC datetime per point, same length as ``equity``.
        rollover_hour_utc: UTC hour at which a trading day starts (session roll).
    """
    if not equity:
        return ChallengeResult(
            status=ChallengeStatus.IN_PROGRESS,
            initial_balance=initial_balance,
            final_balance=initial_balance,
            total_return=0.0,
            max_drawdown_pct=0.0,
            days_elapsed=0,
            target_hit=False,
        )
    if len(equity) != len(timestamps):
        raise ValueError("equity and timestamps must be the same length")

    gov = PropFirmRiskGovernor(profile, initial_balance)

    def session_key(ts: datetime) -> date:
        return (ts - timedelta(hours=rollover_hour_utc)).date()

    peak = initial_balance
    max_dd = 0.0
    breaches: list[Breach] = []
    days_elapsed = 0
    profitable_days = 0
    session_start_equity = initial_balance
    prev_equity = initial_balance
    prev_session = session_key(timestamps[0])

    for eq, ts in zip(equity, timestamps, strict=True):
        key = session_key(ts)
        if key != prev_session:
            if prev_equity > session_start_equity:
                profitable_days += 1
            gov.rollover()
            days_elapsed += 1
            session_start_equity = prev_equity
            prev_session = key

        gov.update(balance=eq, equity=eq)

        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd

        prev_equity = eq

        for b in gov.evaluate():
            if b not in breaches:
                breaches.append(b)
        if gov.status != ChallengeStatus.IN_PROGRESS:
            return _finish(gov.status, initial_balance, eq, max_dd, days_elapsed, breaches)

        target = initial_balance * (1.0 + profile.profit_target_pct)
        days_ok = days_elapsed >= profile.min_trading_days
        prof_ok = profitable_days >= profile.min_profitable_days
        if eq >= target and days_ok and prof_ok:
            return _finish(
                ChallengeStatus.PASSED, initial_balance, eq, max_dd, days_elapsed, breaches
            )

    return _finish(gov.status, initial_balance, equity[-1], max_dd, days_elapsed, breaches)


def _finish(
    status: ChallengeStatus,
    initial_balance: float,
    final: float,
    max_dd: float,
    days_elapsed: int,
    breaches: list[Breach],
) -> ChallengeResult:
    total_return = (final - initial_balance) / initial_balance
    return ChallengeResult(
        status=status,
        initial_balance=initial_balance,
        final_balance=final,
        total_return=total_return,
        max_drawdown_pct=max_dd,
        days_elapsed=days_elapsed,
        target_hit=status == ChallengeStatus.PASSED,
        breaches=breaches,
    )
