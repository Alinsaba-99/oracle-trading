"""Tests for the prop-firm risk governor — rule semantics and gating.

Scenarios are built around the The5ers profile (target 10%, daily 3%,
overall 6%, static DD) on a 100,000 starting balance.  All percentages
and thresholds are derived analytically so the assertions are exact.
"""

from __future__ import annotations

import pytest

from policy.prop_firm import (
    LUCID,
    THE5ERS,
    BreachType,
    ChallengeStatus,
    DrawdownMode,
    FirmProgramProfile,
    PropFirmRiskGovernor,
    SupportMode,
)

INITIAL = 100_000.0


def _make_profile(
    *,
    profit_target_pct: float = 0.10,
    max_daily_loss_pct: float = 0.03,
    max_overall_loss_pct: float = 0.06,
    dd_mode: str = "static",
    consistency_pct: float = 0.0,
    min_trading_days: int = 0,
    min_profitable_days: int = 0,
    support_mode: str = "research_only",
) -> FirmProgramProfile:
    """Minimal profile factory for governor tests."""
    return FirmProgramProfile(
        firm="Test",
        program="Test",
        stage="evaluation",
        platform="test",
        account_size=INITIAL,
        rule_version="1.0",
        effective_from="2026-01-01",
        source_url="https://test.example.com",
        source_checked_at="2026-07-17",
        support_mode=SupportMode(support_mode),
        profit_target_pct=profit_target_pct,
        max_daily_loss_pct=max_daily_loss_pct,
        max_overall_loss_pct=max_overall_loss_pct,
        dd_mode=DrawdownMode(dd_mode),
        consistency_pct=consistency_pct,
        min_trading_days=min_trading_days,
        min_profitable_days=min_profitable_days,
    )


Prof = _make_profile  # shorthand


def _gov(profile: FirmProgramProfile = THE5ERS, balance: float = INITIAL) -> PropFirmRiskGovernor:
    return PropFirmRiskGovernor(profile, initial_balance=balance)


def _auto_gov(balance: float = INITIAL) -> PropFirmRiskGovernor:
    """Governor with AUTO_SUPPORTED profile for gate tests."""
    p = _make_profile(
        support_mode="auto_supported", max_daily_loss_pct=0.03, max_overall_loss_pct=0.06
    )
    return PropFirmRiskGovernor(p, initial_balance=balance)


class TestProfile:
    def test_the5ers_presets(self) -> None:
        assert THE5ERS.profit_target_pct == 0.10
        assert THE5ERS.max_daily_loss_pct == 0.03
        assert THE5ERS.max_overall_loss_pct == 0.06

    def test_lucid_marked_unverified(self) -> None:
        assert "unverified" in LUCID.version_key.lower()


class TestDailyLoss:
    def test_no_loss_at_start(self) -> None:
        gov = _gov()
        assert gov.daily_loss() == 0.0
        assert gov.daily_loss_used_pct() == 0.0

    def test_equity_based_daily_loss(self) -> None:
        gov = _gov()
        gov.update(balance=INITIAL, equity=INITIAL - 2_000)  # 2% down
        assert gov.daily_loss() == pytest.approx(2_000)
        assert gov.daily_loss_used_pct() == pytest.approx(0.02)

    def test_daily_breach_detected(self) -> None:
        gov = _gov()
        gov.update(balance=INITIAL, equity=INITIAL - 3_000)  # exactly 3% down
        breaches = gov.evaluate()
        assert any(b.type == BreachType.DAILY_LOSS and b.severity == "hard" for b in breaches)
        assert gov.status == ChallengeStatus.FAILED_DAILY

    def test_just_under_limit_no_breach(self) -> None:
        gov = _gov()
        gov.update(balance=INITIAL, equity=INITIAL - 2_990)  # 2.99% down
        assert all(b.type != BreachType.DAILY_LOSS for b in gov.evaluate())


class TestOverallLoss:
    def test_static_floor(self) -> None:
        gov = _gov()  # static, 6%
        assert gov.overall_floor() == pytest.approx(94_000)

    def test_trailing_floor_rises_with_peak(self) -> None:
        profile = _make_profile(
            profit_target_pct=0.10,
            max_daily_loss_pct=0.05,
            max_overall_loss_pct=0.06,
            dd_mode="trailing_eod",
        )
        gov = PropFirmRiskGovernor(profile, initial_balance=INITIAL)
        gov.update(balance=110_000, equity=110_000)  # peak rises
        assert gov.overall_floor() == pytest.approx(110_000 * 0.94)

    def test_overall_breach_below_floor(self) -> None:
        gov = _gov()
        # Day starts already in deficit (5% off initial) then a further small
        # drop breaches the static 94k overall floor WITHOUT tripping the 3%
        # daily limit (2.5% intraday < 3%).
        gov.update(balance=95_000, equity=95_000)
        gov.rollover()  # day_start resets to 95,000
        gov.update(balance=93_500, equity=93_500)
        breaches = gov.evaluate()
        assert any(b.type == BreachType.OVERALL_LOSS for b in breaches)
        assert all(b.type != BreachType.DAILY_LOSS for b in breaches)
        assert gov.status == ChallengeStatus.FAILED_OVERALL


class TestRollover:
    def test_rollover_resets_daily_counter(self) -> None:
        gov = _gov()
        gov.update(balance=INITIAL, equity=INITIAL - 2_000)  # 2% intraday
        gov.record_trade(500.0)
        assert gov.daily_loss() == pytest.approx(2_000)
        gov.rollover()
        assert gov.daily_loss() == 0.0
        assert gov.state.realized_pnl_today == 0.0
        assert gov.state.trading_days == 1

    def test_rollover_without_trade_no_count(self) -> None:
        gov = _gov()
        gov.rollover()
        assert gov.state.trading_days == 0


class TestPositionSizing:
    def test_max_size_within_daily_budget(self) -> None:
        gov = _gov()
        # 1 lot, entry 1.1000 stop 1.0950 -> risk_per_lot = 100000 * 0.0050 = 500
        # daily budget = 3% * 100k = 3000; per-trade cap = 1% * 100k = 1000
        # max_lots = min(3000, 1000) / 500 = 2.0
        max_lots = gov.max_position_size(entry=1.10, stop=1.095, contract_size=100_000)
        assert max_lots == pytest.approx(2.0)

    def test_max_size_shrinks_after_loss(self) -> None:
        gov = _gov()
        gov.update(balance=INITIAL, equity=INITIAL - 2_000)  # 2000 daily loss used
        # remaining daily = 3000 - 2000 = 1000; per-trade cap = 1000 -> budget 1000
        max_lots = gov.max_position_size(entry=1.10, stop=1.095, contract_size=100_000)
        assert max_lots == pytest.approx(2.0)

    def test_zero_risk_when_no_stop_distance(self) -> None:
        gov = _gov()
        assert gov.max_position_size(entry=1.10, stop=1.10, contract_size=100_000) == 0.0


class TestPreTradeGate:
    def test_support_mode_blocks_non_auto(self) -> None:
        """ASSISTED_ONLY profili sono bloccati dal gate."""
        gov = _gov()  # THE5ERS is ASSISTED_ONLY
        check = gov.check_new_order(entry=1.10, stop=1.095, lots=1.0, contract_size=100_000)
        assert check.allowed is False
        assert "automation denied" in check.reason.lower()

    def test_allow_safe_order(self) -> None:
        gov = _auto_gov()
        # risk = 1.0 lot * 500 = 500, well within daily 3000
        check = gov.check_new_order(entry=1.10, stop=1.095, lots=1.0, contract_size=100_000)
        assert check.allowed is True
        assert check.max_lots == pytest.approx(2.0)

    def test_deny_order_breaching_daily(self) -> None:
        gov = _auto_gov()
        # 7 lots -> risk 3500 > daily 3000
        check = gov.check_new_order(entry=1.10, stop=1.095, lots=7.0, contract_size=100_000)
        assert check.allowed is False
        assert "daily" in check.reason.lower()

    def test_deny_when_challenge_already_failed(self) -> None:
        gov = _auto_gov()
        gov.update(balance=INITIAL, equity=INITIAL - 3_000)
        gov.evaluate()  # triggers FAILED_DAILY
        assert gov.status == ChallengeStatus.FAILED_DAILY
        check = gov.check_new_order(entry=1.10, stop=1.095, lots=0.1, contract_size=100_000)
        assert check.allowed is False


class TestChallengeOutcome:
    def test_in_progress_at_start(self) -> None:
        assert _gov().challenge_outcome() == ChallengeStatus.IN_PROGRESS

    def test_passed_on_target(self) -> None:
        gov = _gov(
            profile=_make_profile(
                profit_target_pct=0.10,
                max_daily_loss_pct=0.03,
                max_overall_loss_pct=0.06,
                min_trading_days=0,
            )
        )
        gov.update(balance=INITIAL * 1.10, equity=INITIAL * 1.10)
        assert gov.challenge_outcome() == ChallengeStatus.PASSED

    def test_not_passed_without_min_days(self) -> None:
        gov = _gov(
            profile=_make_profile(
                profit_target_pct=0.10,
                max_daily_loss_pct=0.03,
                max_overall_loss_pct=0.06,
                min_trading_days=3,
            )
        )
        gov.update(balance=INITIAL * 1.10, equity=INITIAL * 1.10)
        assert gov.challenge_outcome() == ChallengeStatus.IN_PROGRESS

    def test_failed_status_sticky(self) -> None:
        gov = _gov()
        gov.update(balance=INITIAL, equity=INITIAL - 3_000)
        gov.evaluate()
        assert gov.status == ChallengeStatus.FAILED_DAILY
        # Recovering equity does not un-fail
        gov.update(balance=INITIAL, equity=INITIAL)
        assert gov.challenge_outcome() == ChallengeStatus.FAILED_DAILY


class TestConsistency:
    def test_soft_breach_when_one_day_dominates(self) -> None:
        profile = _make_profile(
            profit_target_pct=0.10,
            max_daily_loss_pct=0.05,
            max_overall_loss_pct=0.10,
            consistency_pct=0.45,
        )
        gov = PropFirmRiskGovernor(profile, initial_balance=INITIAL)
        gov.record_trade(5_000)  # one big winning day
        breaches = gov.evaluate()
        assert any(b.type == BreachType.CONSISTENCY and b.severity == "soft" for b in breaches)
        # consistency is soft — does not fail the challenge
        assert gov.status == ChallengeStatus.IN_PROGRESS
