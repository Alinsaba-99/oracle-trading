"""Golden tests for prop-firm profiles — deterministic fixture replay.

Each test uses a pre-computed sequence of balance/equity updates and
verifies that the governor produces the *exact* breaches, status, and
decision codes specified by the prop firm's rule set.

All scenarios are deterministic: no randomness, no external data.
"""
# mypy: allow-untyped-defs

from __future__ import annotations

import pytest

from policy.prop_firm import (
    APEX_MANUAL,
    FUNDEDNEXT_FLEX,
    MFFU_NEWS_RESTRICTED,
    TOPSTEP_TC_50K,
    TOPSTEP_XFA_CONSISTENCY,
    TOPSTEP_XFA_STANDARD,
    TPT_PRO,
    TPT_TEST,
    BreachType,
    ChallengeStatus,
    FirmProgramProfile,
    PropFirmRiskGovernor,
)


def _make_gov(profile: FirmProgramProfile, balance: float | None = None) -> PropFirmRiskGovernor:
    """Helper to create a governor for a profile."""
    balance = balance or profile.account_size
    return PropFirmRiskGovernor(profile, initial_balance=float(balance))


# =========================================================================
# TOPSTEP Trading Combine 50K
# =========================================================================


class TestTOPSTEP_TC_50K:  # noqa: N801
    """Contract cap, MLL unrealized, minimum days e session flatten."""

    def test_profile_basics(self):
        assert TOPSTEP_TC_50K.firm == "TOPSTEP"
        assert TOPSTEP_TC_50K.account_size == 50_000
        assert TOPSTEP_TC_50K.profit_target_pct == 0.10
        assert TOPSTEP_TC_50K.max_daily_loss_pct == 0.02
        assert TOPSTEP_TC_50K.max_overall_loss_pct == 0.04
        assert TOPSTEP_TC_50K.max_daily_loss_amount == 1_000
        assert TOPSTEP_TC_50K.max_overall_loss_amount == 2_000

    def test_daily_breach_at_one_thousand_dollars(self):
        """Optional 50K Daily Loss Limit is fixed at $1,000."""
        gov = _make_gov(TOPSTEP_TC_50K)
        gov.update(balance=49_001, equity=49_001)
        assert all(b.type != BreachType.DAILY_LOSS for b in gov.evaluate())
        gov.update(balance=49_000, equity=49_000)
        breaches = gov.evaluate()
        assert any(b.type == BreachType.DAILY_LOSS for b in breaches)
        assert gov.status == ChallengeStatus.FAILED_DAILY

    def test_overall_breach_at_two_thousand_dollars(self):
        """50K MLL starts at $48,000 and trails at EOD."""
        gov = _make_gov(TOPSTEP_TC_50K)
        assert gov.overall_floor() == pytest.approx(48_000)
        gov.update(balance=50_500, equity=50_500)
        gov.rollover()
        assert gov.overall_floor() == pytest.approx(48_500)
        gov.update(balance=48_499, equity=48_499)
        breaches = gov.evaluate()
        overall = [b for b in breaches if b.type == BreachType.OVERALL_LOSS]
        assert len(overall) >= 1, f"Expected OVERALL loss breach, got: {[b.type for b in breaches]}"

    def test_contract_cap(self):
        """Official 50K cap is 5 minis or 50 micros."""
        assert TOPSTEP_TC_50K.contract_cap is not None
        assert TOPSTEP_TC_50K.contract_cap.max_mini_eq == 5
        assert TOPSTEP_TC_50K.contract_cap.per_product["MES"] == 50

    def test_pass_on_target(self):
        """Profit target 10% + any days -> passed."""
        gov = _make_gov(TOPSTEP_TC_50K, balance=50_000)
        gov.update(balance=55_000, equity=55_000)
        # Need at least one trade to count as trading day
        gov.record_trade(5_000.0)
        assert gov.challenge_outcome() == ChallengeStatus.PASSED


# =========================================================================
# TOPSTEP XFA Standard
# =========================================================================


class TestTOPSTEP_XFA_STANDARD:  # noqa: N801
    """Five winning days, no consistency rule on standard path."""

    def test_profile_basics(self):
        assert TOPSTEP_XFA_STANDARD.program == "XFA"
        assert TOPSTEP_XFA_STANDARD.min_profitable_days == 5
        assert TOPSTEP_XFA_STANDARD.consistency_pct == 0.0  # no consistency

    def test_not_passed_without_days(self):
        """Profit alone is not enough — need 5 winning days."""
        gov = _make_gov(TOPSTEP_XFA_STANDARD, balance=50_000)
        gov.update(balance=55_000, equity=55_000)
        assert gov.challenge_outcome() == ChallengeStatus.IN_PROGRESS

    def test_passed_with_5_days(self):
        """5 winning days + profit target met (XFA has no profit target)."""
        gov = _make_gov(TOPSTEP_XFA_STANDARD, balance=50_000)
        # 5 winning days
        for _ in range(5):
            gov.record_trade(500.0)
            gov.rollover()
        # XFA has no profit target, so just positive balance is enough
        assert gov.challenge_outcome() == ChallengeStatus.PASSED


# =========================================================================
# TOPSTEP XFA Consistency
# =========================================================================


class TestTOPSTEP_XFA_CONSISTENCY:  # noqa: N801
    """40% consistency rule enforced."""

    def test_consistency_breach(self):
        """Single day >40% of total profit triggers consistency breach."""
        gov = _make_gov(TOPSTEP_XFA_CONSISTENCY, balance=50_000)
        gov.record_trade(5_000)  # one big day
        gov.record_trade(1_000)  # total profit = 6k, single day = 5k = 83%
        breaches = gov.evaluate()
        consistency = [b for b in breaches if b.type == BreachType.CONSISTENCY]
        assert len(consistency) == 1
        assert consistency[0].severity == "soft"  # soft breach, not terminal

    def test_consistency_not_triggered_when_under(self):
        """Multiple smaller days stay under the 40% threshold."""
        gov = _make_gov(TOPSTEP_XFA_CONSISTENCY, balance=50_000)
        gov.record_trade(500.0)
        gov.record_trade(600.0)
        gov.record_trade(400.0)  # max single = 600/1500 = 40% -> exactly at limit
        gov.rollover()
        gov.record_trade(200.0)  # now max = 600/1700 = 35%
        breaches = gov.evaluate()
        assert all(b.type != BreachType.CONSISTENCY for b in breaches)


# =========================================================================
# APEX Manual
# =========================================================================


class TestAPEX_MANUAL:  # noqa: N801
    """Automation denied, news constraints, session close."""

    def test_profile_basics(self):
        assert APEX_MANUAL.support_mode.value == "assisted_only"
        assert APEX_MANUAL.news_blackout is not None
        assert APEX_MANUAL.news_blackout.before_minutes == 5
        assert APEX_MANUAL.consistency_pct == 0.30

    def test_consistency_breach(self):
        """30% consistency: single day >30% triggers soft breach."""
        gov = _make_gov(APEX_MANUAL, balance=50_000)
        gov.record_trade(3_000)
        gov.record_trade(2_000)  # max day = 3k / 5k = 60% > 30%
        breaches = gov.evaluate()
        assert any(b.type == BreachType.CONSISTENCY for b in breaches)

    def test_min_trading_days(self):
        """Need 10 trading days and 7 profitable days to pass."""
        gov = _make_gov(APEX_MANUAL, balance=50_000)
        gov.update(balance=54_000, equity=54_000)
        for _ in range(9):
            gov.record_trade(100.0)
            gov.rollover()
        assert gov.challenge_outcome() == ChallengeStatus.IN_PROGRESS
        gov.record_trade(100.0)
        gov.rollover()
        assert gov.challenge_outcome() == ChallengeStatus.PASSED


# =========================================================================
# TPT Test
# =========================================================================


class TestTPT_TEST:  # noqa: N801
    """Five days, best day under 50%, EOD trailing drawdown."""

    def test_profile_basics(self):
        assert TPT_TEST.dd_mode.value == "trailing_eod"
        assert TPT_TEST.consistency_pct == 0.50
        assert TPT_TEST.min_trading_days == 5

    def test_trailing_eod_floor_rises(self):
        """EOD trailing: floor locks at end-of-day peak."""
        gov = _make_gov(TPT_TEST, balance=50_000)
        gov.update(balance=55_000, equity=55_000)  # intraday peak
        gov.rollover()  # locks peak at 55k
        # New day: rise to 60k
        gov.update(balance=60_000, equity=60_000)
        gov.rollover()  # locks peak at 60k
        floor = gov.overall_floor()  # 60k * 0.92 = 55,200
        assert floor == pytest.approx(55_200)

    def test_consistency_breach(self):
        """Single day >50% of total profit triggers soft breach."""
        gov = _make_gov(TPT_TEST, balance=50_000)
        gov.record_trade(5_000)
        gov.record_trade(2_000)  # max = 5k/7k = 71% > 50%
        breaches = gov.evaluate()
        assert any(b.type == BreachType.CONSISTENCY for b in breaches)


# =========================================================================
# TPT PRO
# =========================================================================


class TestTPT_PRO:  # noqa: N801
    """Automation denied, intraday drawdown, news blackout."""

    def test_profile_basics(self):
        assert TPT_PRO.support_mode.value == "assisted_only"
        assert TPT_PRO.dd_mode.value == "trailing_intraday"
        assert TPT_PRO.news_blackout is not None

    def test_trailing_intraday_floor_rises(self):
        """Intraday trailing: floor updates on every peak during the day."""
        gov = _make_gov(TPT_PRO, balance=50_000)
        floor_before = gov.overall_floor()
        gov.update(balance=52_000, equity=52_000)  # intraday peak
        floor_after = gov.overall_floor()
        assert floor_after > floor_before  # floor rose immediately


# =========================================================================
# MFFU News Restricted
# =========================================================================


class TestMFFU_NEWS_RESTRICTED:  # noqa: N801
    """Automation non-HFT, blackout Tier-1 news."""

    def test_profile_basics(self):
        assert MFFU_NEWS_RESTRICTED.news_blackout is not None
        assert MFFU_NEWS_RESTRICTED.consistency_pct == 0.30
        assert MFFU_NEWS_RESTRICTED.min_profitable_days == 5

    def test_consistency_breach(self):
        """30% consistency enforced."""
        gov = _make_gov(MFFU_NEWS_RESTRICTED, balance=50_000)
        gov.record_trade(4_000)
        gov.record_trade(1_000)  # max = 4k/5k = 80% > 30%
        breaches = gov.evaluate()
        assert any(b.type == BreachType.CONSISTENCY for b in breaches)


# =========================================================================
# FundedNext Flex
# =========================================================================


class TestFUNDEDNEXT_FLEX:  # noqa: N801
    """EOD trailing, equity breach, lock point."""

    def test_profile_basics(self):
        assert FUNDEDNEXT_FLEX.dd_mode.value == "trailing_eod"
        assert FUNDEDNEXT_FLEX.profit_target_pct == 0.10
        assert FUNDEDNEXT_FLEX.max_daily_loss_pct == 0.04

    def test_daily_breach_at_4_percent(self):
        """Daily loss limit is 4%."""
        gov = _make_gov(FUNDEDNEXT_FLEX, balance=50_000)
        gov.update(balance=49_000, equity=48_001)  # 3.998% down
        assert all(b.type != BreachType.DAILY_LOSS for b in gov.evaluate())
        gov.update(balance=49_000, equity=47_999)  # 4.002% down
        breaches = gov.evaluate()
        assert any(b.type == BreachType.DAILY_LOSS for b in breaches)
        assert gov.status == ChallengeStatus.FAILED_DAILY

    def test_trailing_eod(self):
        """EOD trailing floor locks after rollover."""
        gov = _make_gov(FUNDEDNEXT_FLEX, balance=50_000)
        gov.update(balance=55_000, equity=55_000)
        floor_intraday = gov.overall_floor()  # peak = 55k -> floor = 55k * 0.90 = 49,500
        gov.rollover()  # EOD lock — floor stays at 49,500 until next peak
        # Introduce a new peak next day
        gov.update(balance=60_000, equity=60_000)
        gov.rollover()
        floor_after = gov.overall_floor()  # 60k * 0.90 = 54,000
        assert floor_after > floor_intraday

    def test_profit_target(self):
        """10% profit target to pass."""
        gov = _make_gov(FUNDEDNEXT_FLEX, balance=50_000)
        gov.update(balance=55_000, equity=55_000)
        gov.record_trade(5_000.0)
        assert gov.challenge_outcome() == ChallengeStatus.PASSED
