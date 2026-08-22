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
    ALPHA_ONE_6,
    ALPHA_PRO_8,
    APEX_MANUAL,
    E8_ONE,
    FTMO_1_STEP,
    FTMO_2_STEP_P1,
    FTMO_2_STEP_P2,
    FUNDEDNEXT_FLEX,
    MFFU_NEWS_RESTRICTED,
    THE5ERS_BOOTCAMP_FUNDED,
    THE5ERS_BOOTCAMP_STEP,
    THE5ERS_HIGH_STAKES_P1,
    THE5ERS_HIGH_STAKES_P2,
    THE5ERS_HYPER_GROWTH,
    THE5ERS_PRO_GROWTH,
    TOPSTEP_TC_50K,
    TOPSTEP_XFA_CONSISTENCY,
    TOPSTEP_XFA_STANDARD,
    TPT_PRO,
    TPT_TEST,
    BreachType,
    ChallengeStatus,
    DailyLossAction,
    DrawdownMode,
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
        # BL-095 (2026-08-21): 2026 vintage — profit target $3,000 (6%)
        # verified against docs/firm_sources/topstep/ snapshots.
        assert TOPSTEP_TC_50K.profit_target_pct == 0.06
        assert TOPSTEP_TC_50K.rule_version == "2026-08-21"
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
        """Profit target 6% ($3,000 BL-095) + any days -> passed.

        +$5,000 exceeds the lowered 2026 target, so the outcome holds.
        """
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
        # BL-095 (2026-08-15, re-verified 2026-08-21): MFFU 2026 rules —
        # profit target 6% ($3K on $50K), daily loss limit removed, no
        # minimum profitable days. consistency_pct=0.0 is a DECLARED GAP:
        # the 2026 "50% eval-only" soft rule has target-based semantics
        # the governor does not model (fixtures.py comment).
        assert MFFU_NEWS_RESTRICTED.news_blackout is not None
        assert MFFU_NEWS_RESTRICTED.consistency_pct == 0.0
        assert MFFU_NEWS_RESTRICTED.min_profitable_days == 0
        assert MFFU_NEWS_RESTRICTED.profit_target_pct == 0.06

    def test_consistency_rule_not_modeled(self):
        """BL-095: the 2026 eval-only consistency rule is deliberately not
        modeled (declared gap) — a profit-concentrated day must NOT raise
        a governor consistency breach."""
        gov = _make_gov(MFFU_NEWS_RESTRICTED, balance=50_000)
        gov.record_trade(4_000)
        gov.record_trade(1_000)  # max = 4k/5k = 80%; not modeled -> no breach
        breaches = gov.evaluate()
        assert not any(b.type == BreachType.CONSISTENCY for b in breaches)


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


# =========================================================================
# BL-721 — fixtures verified against 2026-08-22 official snapshots
# (docs/firm_sources/SNAPSHOTS.tsv sha256)
# =========================================================================


class TestFTMO_1_STEP:  # noqa: N801
    def test_profile_basics(self):
        assert FTMO_1_STEP.firm == "FTMO"
        assert FTMO_1_STEP.account_size == 100_000
        assert FTMO_1_STEP.profit_target_pct == 0.10
        assert FTMO_1_STEP.max_daily_loss_pct == 0.03
        assert FTMO_1_STEP.max_overall_loss_pct == 0.10
        assert FTMO_1_STEP.dd_mode is DrawdownMode.TRAILING_EOD
        assert FTMO_1_STEP.daily_loss_reset_timezone == "Europe/Prague"
        assert FTMO_1_STEP.rule_version == "2026-08-22"
        # default: termina (FTMO non sospende)
        assert FTMO_1_STEP.daily_loss_action is DailyLossAction.TERMINATE

    def test_daily_breach_at_three_thousand(self):
        """Daily loss limit 3% = $3,000 su initial balance day 1."""
        gov = _make_gov(FTMO_1_STEP)
        gov.update(balance=100_000, equity=97_000.0)
        breaches = {b.type for b in gov.evaluate()}
        assert BreachType.DAILY_LOSS in breaches

    def test_pass_on_target(self):
        gov = _make_gov(FTMO_1_STEP, balance=100_000.0)
        gov.record_trade(10_100.0)
        gov.update(balance=110_100.0, equity=110_100.0)
        assert gov.challenge_outcome() is ChallengeStatus.PASSED


class TestFTMO_2_STEP:  # noqa: N801
    def test_p1_basics(self):
        assert FTMO_2_STEP_P1.profit_target_pct == 0.10
        assert FTMO_2_STEP_P1.max_daily_loss_pct == 0.05
        assert FTMO_2_STEP_P1.dd_mode is DrawdownMode.STATIC
        assert FTMO_2_STEP_P1.min_trading_days == 4

    def test_p2_basics(self):
        assert FTMO_2_STEP_P2.stage == "verification"
        assert FTMO_2_STEP_P2.profit_target_pct == 0.05
        assert FTMO_2_STEP_P2.max_daily_loss_pct == 0.05
        assert FTMO_2_STEP_P2.min_trading_days == 4

    def test_p1_daily_breach_at_five_thousand(self):
        gov = _make_gov(FTMO_2_STEP_P1)
        gov.update(balance=100_000, equity=95_000.0)
        breaches = {b.type for b in gov.evaluate()}
        assert BreachType.DAILY_LOSS in breaches


class TestTHE5ERS_BOOTCAMP:  # noqa: N801
    def test_step_basics(self):
        assert THE5ERS_BOOTCAMP_STEP.profit_target_pct == 0.06
        assert THE5ERS_BOOTCAMP_STEP.max_overall_loss_pct == 0.05
        # nessuna daily rule in evaluation (3% pause è solo funded)
        assert THE5ERS_BOOTCAMP_STEP.max_daily_loss_pct == 0.0

    def test_funded_basics(self):
        assert THE5ERS_BOOTCAMP_FUNDED.stage == "funded"
        assert THE5ERS_BOOTCAMP_FUNDED.max_overall_loss_pct == 0.04
        assert THE5ERS_BOOTCAMP_FUNDED.max_daily_loss_pct == 0.03
        assert THE5ERS_BOOTCAMP_FUNDED.daily_loss_action is DailyLossAction.PAUSE


class TestTHE5ERS_HIGH_STAKES:  # noqa: N801
    def test_p1_basics(self):
        assert THE5ERS_HIGH_STAKES_P1.profit_target_pct == 0.08
        assert THE5ERS_HIGH_STAKES_P1.max_daily_loss_pct == 0.05
        assert THE5ERS_HIGH_STAKES_P1.max_overall_loss_pct == 0.10
        assert THE5ERS_HIGH_STAKES_P1.daily_loss_action is DailyLossAction.TERMINATE
        assert THE5ERS_HIGH_STAKES_P1.min_profitable_days == 3
        assert THE5ERS_HIGH_STAKES_P1.news_blackout is not None
        assert THE5ERS_HIGH_STAKES_P1.news_blackout.before_minutes == 2

    def test_p2_basics(self):
        assert THE5ERS_HIGH_STAKES_P2.stage == "verification"
        assert THE5ERS_HIGH_STAKES_P2.profit_target_pct == 0.05

    def test_daily_breach_terminates(self):
        gov = _make_gov(THE5ERS_HIGH_STAKES_P1)
        gov.update(balance=100_000, equity=94_999.0)
        breaches = {b.type for b in gov.evaluate()}
        assert BreachType.DAILY_LOSS in breaches


class TestTHE5ERS_GROWTH_PROGRAMS:  # noqa: N801
    def test_hyper_growth_pauses(self):
        assert THE5ERS_HYPER_GROWTH.profit_target_pct == 0.10
        assert THE5ERS_HYPER_GROWTH.max_overall_loss_pct == 0.06
        assert THE5ERS_HYPER_GROWTH.max_daily_loss_pct == 0.03
        assert THE5ERS_HYPER_GROWTH.daily_loss_action is DailyLossAction.PAUSE

    def test_pro_growth_terminates(self):
        assert THE5ERS_PRO_GROWTH.profit_target_pct == 0.10
        assert THE5ERS_PRO_GROWTH.max_overall_loss_pct == 0.06
        assert THE5ERS_PRO_GROWTH.daily_loss_action is DailyLossAction.TERMINATE
        assert THE5ERS_PRO_GROWTH.min_profitable_days == 3


class TestALPHA_CAPITAL:  # noqa: N801
    def test_pro8_basics(self):
        assert ALPHA_PRO_8.program == "Alpha Pro 8%"
        assert ALPHA_PRO_8.profit_target_pct == 0.08
        assert ALPHA_PRO_8.max_daily_loss_pct == 0.04
        assert ALPHA_PRO_8.max_overall_loss_pct == 0.08
        assert ALPHA_PRO_8.dd_mode is DrawdownMode.STATIC
        assert ALPHA_PRO_8.daily_loss_basis == "balance"
        assert ALPHA_PRO_8.min_trading_days == 3
        # anti-HFT: durata media > 2 min (enforcement BL-722)
        assert ALPHA_PRO_8.min_trade_duration_minutes == 2.0

    def test_news_blackout_five_minutes(self):
        assert ALPHA_PRO_8.news_blackout is not None
        assert ALPHA_PRO_8.news_blackout.before_minutes == 5
        assert ALPHA_PRO_8.news_blackout.after_minutes == 5
        assert ALPHA_ONE_6.news_blackout is not None
        assert ALPHA_ONE_6.news_blackout.before_minutes == 5

    def test_one6_basics(self):
        assert ALPHA_ONE_6.profit_target_pct == 0.06
        assert ALPHA_ONE_6.max_overall_loss_pct == 0.04
        assert ALPHA_ONE_6.dd_mode is DrawdownMode.TRAILING_EOD
        assert ALPHA_ONE_6.max_daily_loss_pct == 0.03
        assert ALPHA_ONE_6.min_trading_days == 1


class TestE8_ONE:  # noqa: N801
    def test_dynamic_drawdown_mechanics_only(self):
        """E8 One: TRAILING_CLOSED codificato; numeri default = gap
        dichiarato (customizzabili al checkout) — 0 finché seconda passata
        BL-720 non li snapshot-ta."""
        assert E8_ONE.dd_mode is DrawdownMode.TRAILING_CLOSED
        assert E8_ONE.profit_target_pct == 0.0
        assert E8_ONE.max_daily_loss_pct == 0.0
        assert E8_ONE.max_overall_loss_pct == 0.0

    def test_e8_not_usable_for_simulation_yet(self):
        """Con target 0 il governor PASSA con qualsiasi profitto positivo:
        pericolo di falso-verde. Fail-safe qui = il test documentale
        (target 0) + gate BL-722; il profilo non va usato in simulazione
        finché i default non entrano (seconda passata BL-720)."""
        gov = _make_gov(E8_ONE, balance=100_000.0)
        gov.record_trade(20_000.0)
        gov.update(balance=120_000.0, equity=120_000.0)
        assert E8_ONE.profit_target_pct == 0.0  # gap dichiarato, non numero reale
        assert gov.challenge_outcome() is ChallengeStatus.PASSED  # documenta il pericolo
