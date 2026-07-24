"""Tests for R0.6 intraday-honest challenge replay."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from analytics.backtest.challenge import ChallengeSimulator
from analytics.backtest.challenge_intraday import run_intraday
from policy.prop_firm.governor import ChallengeStatus
from policy.prop_firm.profile import DrawdownMode, FirmProgramProfile, SupportMode

# 10% target, 3% daily, 6% overall — The5ers-shaped, no min-day gates.
PROFILE = FirmProgramProfile(
    firm="test",
    program="challenge",
    stage="evaluation",
    platform="paper",
    account_size=100_000,
    rule_version="1",
    effective_from="2026-01-01",
    source_url="https://example.com",
    source_checked_at="2026-07-19",
    support_mode=SupportMode.RESEARCH_ONLY,
    profit_target_pct=0.10,
    max_daily_loss_pct=0.03,
    max_overall_loss_pct=0.06,
    dd_mode=DrawdownMode.STATIC,
)


def test_intraday_catches_dip_that_daily_misses() -> None:
    sim = ChallengeSimulator(PROFILE, 100_000)
    # Daily close-to-close view: opens and closes at 100k -> no visible loss.
    daily = sim.run([100_000, 100_000], [date(2026, 1, 4), date(2026, 1, 5)])
    assert daily.status != ChallengeStatus.FAILED_DAILY

    # Intraday view: dips to 96,500 (-3.5%) mid-session, then recovers to flat.
    ts = [
        datetime(2026, 1, 5, 9, tzinfo=UTC),
        datetime(2026, 1, 5, 13, tzinfo=UTC),
        datetime(2026, 1, 5, 20, tzinfo=UTC),
    ]
    res = run_intraday(PROFILE, 100_000, [100_000, 96_500, 100_000], ts)
    assert res.status == ChallengeStatus.FAILED_DAILY
    assert res.max_drawdown_pct > 0.03


def test_rollover_resets_daily_budget() -> None:
    # Two sessions, each down ~1% from its own open -> no daily breach.
    ts = [
        datetime(2026, 1, 5, 9, tzinfo=UTC),
        datetime(2026, 1, 5, 18, tzinfo=UTC),
        datetime(2026, 1, 6, 9, tzinfo=UTC),
        datetime(2026, 1, 6, 18, tzinfo=UTC),
    ]
    equity = [100_000, 99_000, 99_000, 98_010]  # s1 -1%, s2 -1% (from 99k open)
    res = run_intraday(PROFILE, 100_000, equity, ts)
    assert res.status != ChallengeStatus.FAILED_DAILY
    assert res.days_elapsed == 1  # one rollover between the two sessions


def test_intraday_can_pass_on_target() -> None:
    # Slow grind up to +10% with no breach -> PASSED (min_profitable_days=0).
    ts = [datetime(2026, 1, d, 12, tzinfo=UTC) for d in range(1, 6)]
    equity = [100_000, 102_000, 104_000, 107_000, 111_000]  # clears the +10% target
    res = run_intraday(PROFILE, 100_000, equity, ts)
    assert res.status == ChallengeStatus.PASSED
    assert res.target_hit


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        run_intraday(PROFILE, 100_000, [100_000, 99_000], [datetime(2026, 1, 5, tzinfo=UTC)])


def test_empty_equity_is_in_progress() -> None:
    res = run_intraday(PROFILE, 100_000, [], [])
    assert res.status == ChallengeStatus.IN_PROGRESS
