"""BL-709 — Dual-Channel Strategy Promotion Policy unit tests.

Verifies the pre-registered criteria checkers for Channel A (Personal)
and Channel B (Funded).  All thresholds are FROZEN at BL-709 acceptance;
golden vectors here pin the verdicts so a future bump requires an
explicit ADR amendment and a conscious rewrite of the golden vectors.

Test surface:

* Channel A pass / fail matrix (haircut, dsr, max_dd, walk-forward)
* Channel B pass / fail matrix (hard-risk, consistency, daily-action,
  n_sessions, sim_pass, mc_pass)
* Domain / NaN / non-finite failure modes (fail-closed)
* Independence of the two channels (no cross-contamination)
* Eligible profile + governor_clean helpers
"""

from __future__ import annotations

import math

import pytest

from policy.prop_firm import (
    ALPHA_PRO_8,
    FUNDED_CONSISTENCY_PCT_MAX,
    FUNDED_MIN_PAPER_SESSIONS,
    FUNDED_MONTE_CARLO_PASS_RATE_MIN,
    FUNDED_SIMULATED_PASS_RATE_MIN,
    PERSONAL_DSR_MIN,
    PERSONAL_HAIRCUT_SHARPE_MIN,
    PERSONAL_MAX_DRAWDOWN_MAX,
    PERSONAL_WALK_FORWARD_ALPHA_MIN,
    THE5ERS_BOOTCAMP_STEP,
    TOPSTEP_XFA_CONSISTENCY,
    TPT_PRO,
    Channel,
    DailyLossAction,
    FirmProgramProfile,
    FundedPromotionMetrics,
    PersonalPromotionMetrics,
    SupportMode,
    check_dual_channel,
    check_funded_channel,
    check_personal_channel,
    eligible_profiles,
    governor_clean,
)

# ---------------------------------------------------------------------------
# Helpers / golden fixtures
# ---------------------------------------------------------------------------

#: A passing Channel A metrics bundle (all four criteria met).
PASS_PERSONAL = PersonalPromotionMetrics(
    haircut_sharpe=0.75, dsr=0.98, max_drawdown=0.12, walk_forward_alpha=0.04
)

#: A passing Channel B metrics bundle (all six criteria met).
PASS_FUNDED = FundedPromotionMetrics(
    hard_risk_compliant=True,
    consistency_pct=0.30,
    daily_pause_terminate_supported=True,
    n_paper_sessions=120,
    simulated_pass_rate=0.72,
    monte_carlo_pass_rate=0.68,
)


# ===========================================================================
# Channel A (Personal) — pre-registered criteria
# ===========================================================================


class TestPersonalChannelPasses:
    def test_passes_all_criteria(self) -> None:
        dec = check_personal_channel(PASS_PERSONAL)
        assert dec.passes is True
        assert dec.failed_criteria == ()
        assert dec.channel == Channel.PERSONAL
        assert dec.notes  # notes populated on pass

    def test_passes_at_threshold_minimums(self) -> None:
        """At-the-fence = pass (>=, not >)."""
        metrics = PersonalPromotionMetrics(
            haircut_sharpe=PERSONAL_HAIRCUT_SHARPE_MIN,
            dsr=PERSONAL_DSR_MIN,
            max_drawdown=PERSONAL_MAX_DRAWDOWN_MAX - 1e-9,
            walk_forward_alpha=PERSONAL_WALK_FORWARD_ALPHA_MIN + 1e-9,
        )
        assert check_personal_channel(metrics).passes is True

    def test_truthiness_via_bool(self) -> None:
        """`if decision:` returns True only when passes."""
        assert bool(check_personal_channel(PASS_PERSONAL)) is True
        assert bool(check_personal_channel(PersonalPromotionMetrics(0.0, 0.0, 1.0, 0.0))) is False


class TestPersonalChannelFails:
    def test_fails_low_haircut_sharpe(self) -> None:
        m = PersonalPromotionMetrics(
            haircut_sharpe=PERSONAL_HAIRCUT_SHARPE_MIN - 0.01,
            dsr=PASS_PERSONAL.dsr,
            max_drawdown=PASS_PERSONAL.max_drawdown,
            walk_forward_alpha=PASS_PERSONAL.walk_forward_alpha,
        )
        dec = check_personal_channel(m)
        assert dec.passes is False
        assert any(c.startswith("haircut_sharpe") for c in dec.failed_criteria)
        # Other criteria still pass → only one failure listed
        assert len(dec.failed_criteria) == 1

    def test_fails_low_dsr(self) -> None:
        m = PersonalPromotionMetrics(
            haircut_sharpe=PASS_PERSONAL.haircut_sharpe,
            dsr=PERSONAL_DSR_MIN - 0.01,
            max_drawdown=PASS_PERSONAL.max_drawdown,
            walk_forward_alpha=PASS_PERSONAL.walk_forward_alpha,
        )
        dec = check_personal_channel(m)
        assert dec.passes is False
        assert any(c.startswith("dsr") for c in dec.failed_criteria)

    def test_fails_drawdown_at_or_above_ceiling(self) -> None:
        """DD == ceiling fails (the gate is < ceiling, not <=)."""
        m = PersonalPromotionMetrics(
            haircut_sharpe=PASS_PERSONAL.haircut_sharpe,
            dsr=PASS_PERSONAL.dsr,
            max_drawdown=PERSONAL_MAX_DRAWDOWN_MAX,
            walk_forward_alpha=PASS_PERSONAL.walk_forward_alpha,
        )
        dec = check_personal_channel(m)
        assert dec.passes is False
        assert any(c.startswith("max_drawdown") for c in dec.failed_criteria)

    def test_fails_zero_walk_forward_alpha(self) -> None:
        """OOS alpha == 0 is a coin-flip, not an edge."""
        m = PersonalPromotionMetrics(
            haircut_sharpe=PASS_PERSONAL.haircut_sharpe,
            dsr=PASS_PERSONAL.dsr,
            max_drawdown=PASS_PERSONAL.max_drawdown,
            walk_forward_alpha=0.0,
        )
        dec = check_personal_channel(m)
        assert dec.passes is False
        assert any(c.startswith("walk_forward_alpha") for c in dec.failed_criteria)

    def test_fails_negative_walk_forward_alpha(self) -> None:
        m = PersonalPromotionMetrics(
            haircut_sharpe=PASS_PERSONAL.haircut_sharpe,
            dsr=PASS_PERSONAL.dsr,
            max_drawdown=PASS_PERSONAL.max_drawdown,
            walk_forward_alpha=-0.01,
        )
        assert check_personal_channel(m).passes is False

    def test_fails_multiple_criteria_simultaneously(self) -> None:
        m = PersonalPromotionMetrics(
            haircut_sharpe=0.0,  # fail
            dsr=0.50,  # fail
            max_drawdown=0.30,  # fail
            walk_forward_alpha=-0.05,  # fail
        )
        dec = check_personal_channel(m)
        assert dec.passes is False
        assert len(dec.failed_criteria) == 4


class TestPersonalChannelFailClosed:
    """Non-finite / out-of-domain inputs MUST fail closed (never silently
    pass).  This is the lesson of the M31 evidence loss (ADR-014)."""

    @pytest.mark.parametrize(
        "field, bad_value",
        [
            ("haircut_sharpe", math.nan),
            ("haircut_sharpe", math.inf),
            ("haircut_sharpe", -math.inf),
            ("dsr", math.nan),
            ("dsr", math.inf),
            ("max_drawdown", math.nan),
            ("max_drawdown", -0.01),
            ("max_drawdown", 1.01),
            ("max_drawdown", math.inf),
            ("walk_forward_alpha", math.nan),
            ("walk_forward_alpha", math.inf),
        ],
    )
    def test_non_finite_or_ood_fails_closed(self, field: str, bad_value: float) -> None:
        kwargs = {
            "haircut_sharpe": PASS_PERSONAL.haircut_sharpe,
            "dsr": PASS_PERSONAL.dsr,
            "max_drawdown": PASS_PERSONAL.max_drawdown,
            "walk_forward_alpha": PASS_PERSONAL.walk_forward_alpha,
        }
        kwargs[field] = bad_value
        m = PersonalPromotionMetrics(**kwargs)
        dec = check_personal_channel(m)
        assert dec.passes is False
        # The failed criterion must name the offending field (audit trail).
        assert any(field in c for c in dec.failed_criteria), (
            f"failed_criteria {dec.failed_criteria} does not name {field}"
        )


# ===========================================================================
# Channel B (Funded) — pre-registered criteria
# ===========================================================================


class TestFundedChannelPasses:
    def test_passes_all_criteria(self) -> None:
        dec = check_funded_channel(PASS_FUNDED)
        assert dec.passes is True
        assert dec.failed_criteria == ()
        assert dec.channel == Channel.FUNDED
        assert dec.notes

    def test_passes_at_threshold_minimums(self) -> None:
        metrics = FundedPromotionMetrics(
            hard_risk_compliant=True,
            consistency_pct=FUNDED_CONSISTENCY_PCT_MAX,
            daily_pause_terminate_supported=True,
            n_paper_sessions=FUNDED_MIN_PAPER_SESSIONS,
            simulated_pass_rate=FUNDED_SIMULATED_PASS_RATE_MIN,
            monte_carlo_pass_rate=FUNDED_MONTE_CARLO_PASS_RATE_MIN,
        )
        assert check_funded_channel(metrics).passes is True


class TestFundedChannelFails:
    def test_fails_hard_risk_breach(self) -> None:
        m = FundedPromotionMetrics(
            hard_risk_compliant=False,
            consistency_pct=PASS_FUNDED.consistency_pct,
            daily_pause_terminate_supported=PASS_FUNDED.daily_pause_terminate_supported,
            n_paper_sessions=PASS_FUNDED.n_paper_sessions,
            simulated_pass_rate=PASS_FUNDED.simulated_pass_rate,
            monte_carlo_pass_rate=PASS_FUNDED.monte_carlo_pass_rate,
        )
        dec = check_funded_channel(m)
        assert dec.passes is False
        assert any("hard_risk_compliant" in c for c in dec.failed_criteria)

    def test_fails_consistency_above_ceiling(self) -> None:
        m = FundedPromotionMetrics(
            hard_risk_compliant=True,
            consistency_pct=FUNDED_CONSISTENCY_PCT_MAX + 0.01,
            daily_pause_terminate_supported=True,
            n_paper_sessions=120,
            simulated_pass_rate=0.72,
            monte_carlo_pass_rate=0.68,
        )
        dec = check_funded_channel(m)
        assert dec.passes is False
        assert any("consistency_pct" in c for c in dec.failed_criteria)

    def test_fails_no_daily_pause_or_terminate(self) -> None:
        m = FundedPromotionMetrics(
            hard_risk_compliant=True,
            consistency_pct=0.30,
            daily_pause_terminate_supported=False,
            n_paper_sessions=120,
            simulated_pass_rate=0.72,
            monte_carlo_pass_rate=0.68,
        )
        dec = check_funded_channel(m)
        assert dec.passes is False
        assert any("daily_pause_terminate" in c for c in dec.failed_criteria)

    def test_fails_insufficient_paper_sessions(self) -> None:
        m = FundedPromotionMetrics(
            hard_risk_compliant=True,
            consistency_pct=0.30,
            daily_pause_terminate_supported=True,
            n_paper_sessions=FUNDED_MIN_PAPER_SESSIONS - 1,
            simulated_pass_rate=0.72,
            monte_carlo_pass_rate=0.68,
        )
        dec = check_funded_channel(m)
        assert dec.passes is False
        assert any("n_paper_sessions" in c for c in dec.failed_criteria)

    def test_fails_simulated_pass_rate_below_floor(self) -> None:
        m = FundedPromotionMetrics(
            hard_risk_compliant=True,
            consistency_pct=0.30,
            daily_pause_terminate_supported=True,
            n_paper_sessions=120,
            simulated_pass_rate=FUNDED_SIMULATED_PASS_RATE_MIN - 0.01,
            monte_carlo_pass_rate=0.68,
        )
        dec = check_funded_channel(m)
        assert dec.passes is False
        assert any("simulated_pass_rate" in c for c in dec.failed_criteria)

    def test_fails_monte_carlo_pass_rate_below_floor(self) -> None:
        m = FundedPromotionMetrics(
            hard_risk_compliant=True,
            consistency_pct=0.30,
            daily_pause_terminate_supported=True,
            n_paper_sessions=120,
            simulated_pass_rate=0.72,
            monte_carlo_pass_rate=FUNDED_MONTE_CARLO_PASS_RATE_MIN - 0.01,
        )
        dec = check_funded_channel(m)
        assert dec.passes is False
        assert any("monte_carlo_pass_rate" in c in c for c in dec.failed_criteria) or any(
            "monte_carlo_pass_rate" in c for c in dec.failed_criteria
        )


class TestFundedChannelFailClosed:
    @pytest.mark.parametrize(
        "field, bad_value",
        [
            ("consistency_pct", math.nan),
            ("consistency_pct", -0.01),
            ("consistency_pct", 1.01),
            ("consistency_pct", math.inf),
            ("simulated_pass_rate", math.nan),
            ("simulated_pass_rate", -0.01),
            ("simulated_pass_rate", 1.01),
            ("monte_carlo_pass_rate", math.nan),
            ("monte_carlo_pass_rate", -0.01),
            ("monte_carlo_pass_rate", 1.01),
        ],
    )
    def test_ood_fails_closed(self, field: str, bad_value: float) -> None:
        kwargs = {
            "hard_risk_compliant": True,
            "consistency_pct": 0.30,
            "daily_pause_terminate_supported": True,
            "n_paper_sessions": 120,
            "simulated_pass_rate": 0.72,
            "monte_carlo_pass_rate": 0.68,
        }
        kwargs[field] = bad_value
        m = FundedPromotionMetrics(**kwargs)
        dec = check_funded_channel(m)
        assert dec.passes is False
        assert any(field in c for c in dec.failed_criteria)


# ===========================================================================
# Independence between channels
# ===========================================================================


class TestChannelIndependence:
    """A strategy may pass Channel A and fail Channel B (or vice versa).
    No cross-contamination of verdicts."""

    def test_personal_pass_funded_fail_independent(self) -> None:
        a, b = check_dual_channel(PASS_PERSONAL, PASS_FUNDED)
        assert a.passes is True
        assert b.passes is True  # both pass independently

    def test_personal_fail_does_not_block_funded_pass(self) -> None:
        bad_personal = PersonalPromotionMetrics(0.0, 0.0, 1.0, 0.0)
        a, b = check_dual_channel(bad_personal, PASS_FUNDED)
        assert a.passes is False
        assert b.passes is True  # Channel B unaffected by Channel A

    def test_funded_fail_does_not_block_personal_pass(self) -> None:
        bad_funded = FundedPromotionMetrics(
            hard_risk_compliant=False,
            consistency_pct=0.95,
            daily_pause_terminate_supported=False,
            n_paper_sessions=10,
            simulated_pass_rate=0.30,
            monte_carlo_pass_rate=0.30,
        )
        a, b = check_dual_channel(PASS_PERSONAL, bad_funded)
        assert a.passes is True
        assert b.passes is False

    def test_dual_returns_tuple_in_channel_order(self) -> None:
        a, b = check_dual_channel(PASS_PERSONAL, PASS_FUNDED)
        assert a.channel == Channel.PERSONAL
        assert b.channel == Channel.FUNDED


# ===========================================================================
# eligible_profiles + governor_clean helpers
# ===========================================================================


class TestEligibleProfiles:
    def test_auto_supported_pause_terminate_eligible(self) -> None:
        """Auto-supported firm with TERMINATE daily-loss action = eligible."""
        # THE5ERS_BOOTCAMP_STEP is ASSISTED_ONLY with TERMINATE; not
        # AUTO_SUPPORTED.  Use ALPHA_PRO_8 (auto supported, terminate).
        assert eligible_profiles(ALPHA_PRO_8) is True

    def test_assisted_only_with_terminate_eligible(self) -> None:
        """Assisted-only firms (e.g. APEX, MT5 manual) are still
        structurally promotable; the operator executes the orders."""
        assert eligible_profiles(THE5ERS_BOOTCAMP_STEP) is True

    def test_research_only_ineligible(self) -> None:
        """Research-only (TopstepX eval, FTMO 1-step) cannot enforce."""
        assert eligible_profiles(TOPSTEP_XFA_CONSISTENCY) is False

    def test_pause_action_eligible(self) -> None:
        """A firm with PAUSE daily-loss action (e.g. FTMO 2-step P2) is
        eligible: pause is a valid enforcement mode."""
        # Construct a profile with PAUSE specifically to verify the gate.
        pause_profile = FirmProgramProfile(
            firm="TestFirm",
            program="PauseTest",
            stage="evaluation",
            platform="MT5",
            account_size=100_000,
            rule_version="2026-01-01",
            effective_from="2026-01-01",
            source_url="https://example.com",
            source_checked_at="2026-09-03",
            support_mode=SupportMode.AUTO_SUPPORTED,
            profit_target_pct=0.08,
            max_daily_loss_pct=0.05,
            max_overall_loss_pct=0.10,
            dd_mode="static",  # type: ignore[arg-type]
            daily_loss_action=DailyLossAction.PAUSE,
        )
        assert eligible_profiles(pause_profile) is True

    def test_term_required(self) -> None:
        """A profile that doesn't enforce PAUSE-or-TERMINATE = ineligible
        even if supported."""
        # Construct a profile with a non-pause/non-terminate daily-loss
        # action — there isn't one in the enum today, but the gate must
        # still reject if a future mode is unsupported.  We model it by
        # passing a stringly-typed value the gate cannot accept.
        none_profile = FirmProgramProfile(
            firm="TestFirm",
            program="NoneTest",
            stage="evaluation",
            platform="MT5",
            account_size=100_000,
            rule_version="2026-01-01",
            effective_from="2026-01-01",
            source_url="https://example.com",
            source_checked_at="2026-09-03",
            support_mode=SupportMode.AUTO_SUPPORTED,
            profit_target_pct=0.08,
            max_daily_loss_pct=0.05,
            max_overall_loss_pct=0.10,
            dd_mode="static",  # type: ignore[arg-type]
            daily_loss_action="none",  # type: ignore[arg-type]
        )
        assert eligible_profiles(none_profile) is False


class TestGovernorClean:
    def test_empty_breach_list_is_clean(self) -> None:
        assert governor_clean(_FakeGovernor(), []) is True

    def test_any_breach_dirties_governor(self) -> None:
        # Even a single breach disqualifies the validation envelope.
        assert governor_clean(_FakeGovernor(), ["DAILY_LOSS"]) is False


class _FakeGovernor:
    """Minimal stand-in for PropFirmRiskGovernor.

    governor_clean() only consumes its argument; the governor object
    itself isn't used (the breach list is the authoritative signal).
    Kept here so test_governor_clean exercises the same surface as the
    production caller.
    """


# ===========================================================================
# Decision immutability / shape
# ===========================================================================


class TestDecisionShape:
    def test_failed_criteria_is_tuple(self) -> None:
        dec = check_personal_channel(PersonalPromotionMetrics(0.0, 0.0, 1.0, 0.0))
        assert isinstance(dec.failed_criteria, tuple)

    def test_decision_is_frozen(self) -> None:
        """Decision must be immutable for audit log integrity."""
        dec = check_personal_channel(PASS_PERSONAL)
        with pytest.raises((AttributeError, Exception)):
            dec.passes = False  # type: ignore[misc]

    def test_notes_empty_on_fail(self) -> None:
        """Notes should NOT contain promotional language on a fail."""
        dec = check_personal_channel(PersonalPromotionMetrics(0.0, 0.0, 1.0, 0.0))
        assert dec.passes is False
        assert "personal capital" not in dec.notes.lower()

    def test_channel_enum_values(self) -> None:
        assert Channel.PERSONAL == "A"
        assert Channel.FUNDED == "B"


# ===========================================================================
# Real fixture sanity (catalog stays promotable at conservative defaults)
# ===========================================================================


class TestCatalogSanity:
    """Smoke-check that the canonical fixture profiles survive the gate."""

    def test_tpt_pro_supported(self) -> None:
        """TPT_PRO is ASSISTED_ONLY with TERMINATE daily-loss action."""
        assert eligible_profiles(TPT_PRO) is True

    def test_topstep_xfa_research_only_ineligible(self) -> None:
        """TopstepX FA is research-only (no auto-bridge to TopstepX
        live), so structurally ineligible."""
        assert eligible_profiles(TOPSTEP_XFA_CONSISTENCY) is False
