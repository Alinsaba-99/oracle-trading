"""Tests for the challenge simulator — pass / fail semantics vs prop-firm rules.

Scenarios use the The5ers profile (target 10%, daily 3%, overall 6%,
static DD, min_profitable_days 3) on a 100,000 starting balance.  Equity
curves are constructed analytically.
"""

from __future__ import annotations

from datetime import date, timedelta

from analytics.backtest.challenge import ChallengeSimulator
from policy.prop_firm import (
    THE5ERS,
    ChallengeStatus,
    DrawdownMode,
    PropFirmProfile,
    SupportMode,
)

INITIAL = 100_000.0


def _dates(n: int) -> list[date]:
    today = date.today()
    return [today + timedelta(days=i) for i in range(n)]


class TestPass:
    def test_steady_growth_passes(self) -> None:
        # +0.5%/day compounded -> hits +10% target after ~20 days.
        equity = [INITIAL * (1.005**i) for i in range(25)]
        result = ChallengeSimulator(THE5ERS, INITIAL).run(equity, dates=_dates(25))
        assert result.status == ChallengeStatus.PASSED
        assert result.target_hit is True
        assert result.total_return >= 0.10
        assert result.days_elapsed >= THE5ERS.min_profitable_days

    def test_never_breaches_daily_or_overall(self) -> None:
        equity = [INITIAL * (1.005**i) for i in range(25)]
        result = ChallengeSimulator(THE5ERS, INITIAL).run(equity, dates=_dates(25))
        # No hard breaches on a passing run.
        assert all(b.severity != "hard" for b in result.breaches)


class TestDailyBreach:
    def test_single_big_down_day_fails_daily(self) -> None:
        # Day 2 drops 4% (> 3% daily limit) in one bar.
        equity = [INITIAL, INITIAL * 0.96]
        result = ChallengeSimulator(THE5ERS, INITIAL).run(equity, dates=_dates(2))
        assert result.status == ChallengeStatus.FAILED_DAILY
        assert result.passed is False
        assert "daily" in result.failure_reason.lower()


class TestOverallBreach:
    def test_grind_down_fails_overall_without_daily(self) -> None:
        # -2.5%/day for 4 bars: each day < 3% daily, but cumulative > 6%.
        equity = [INITIAL * (0.975**i) for i in range(4)]
        result = ChallengeSimulator(THE5ERS, INITIAL).run(equity, dates=_dates(4))
        assert result.status == ChallengeStatus.FAILED_OVERALL
        assert result.max_drawdown_pct > 0.06


class TestEdgeCases:
    def test_empty_equity(self) -> None:
        result = ChallengeSimulator(THE5ERS, INITIAL).run([])
        assert result.status == ChallengeStatus.IN_PROGRESS
        assert result.days_elapsed == 0

    def test_min_trading_days_blocks_premature_pass(self) -> None:
        # Hit target on day 1 but min_trading_days=5 -> must not pass yet.
        profile = PropFirmProfile(
            firm="Test",
            program="Challenge",
            stage="evaluation",
            platform="paper",
            account_size=int(INITIAL),
            rule_version="1.0",
            effective_from="2026-01-01",
            source_url="https://example.com/test-profile",
            source_checked_at="2026-07-20",
            support_mode=SupportMode.RESEARCH_ONLY,
            profit_target_pct=0.10,
            max_daily_loss_pct=0.03,
            max_overall_loss_pct=0.06,
            dd_mode=DrawdownMode.STATIC,
            min_trading_days=5,
            min_profitable_days=0,
        )
        equity = [INITIAL, INITIAL * 1.12]  # +12% in one day, but only 1 elapsed
        result = ChallengeSimulator(profile, INITIAL).run(equity, dates=_dates(2))
        assert result.status != ChallengeStatus.PASSED
