"""Property-based tests for the prop-firm risk governor.

These tests verify *invariants* — properties that must hold for
ALL valid inputs — rather than checking specific example values.
"""

from __future__ import annotations

import pytest

from policy.prop_firm import THE5ERS, TOPSTEP_TC_50K
from policy.prop_firm.governor import PropFirmRiskGovernor

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def gov() -> PropFirmRiskGovernor:
    """Default governor with The5ers profile, 100k initial balance."""
    return PropFirmRiskGovernor(THE5ERS, initial_balance=100_000)


@pytest.fixture
def topstep_gov() -> PropFirmRiskGovernor:
    """Topstep 50k Trading Combine governor."""
    return PropFirmRiskGovernor(TOPSTEP_TC_50K, initial_balance=50_000)


# =========================================================================
# Property: Initial state invariants
# =========================================================================


class TestInitialState:
    """Properties that hold immediately after construction."""

    def test_initial_balance_is_positive(self, gov: PropFirmRiskGovernor) -> None:
        assert gov.state.initial_balance > 0

    def test_balance_equals_initial(self, gov: PropFirmRiskGovernor) -> None:
        assert gov.state.current_balance == gov.state.initial_balance

    def test_equity_equals_balance(self, gov: PropFirmRiskGovernor) -> None:
        assert gov.state.current_equity == gov.state.current_balance

    def test_no_daily_loss_at_start(self, gov: PropFirmRiskGovernor) -> None:
        assert gov.state.realized_pnl_today == 0.0
        assert gov.daily_loss_used_pct() == 0.0

    def test_challenge_in_progress(self, gov: PropFirmRiskGovernor) -> None:
        assert gov.status.value == "in_progress"


# =========================================================================
# Property: Loss limits are never exceeded
# =========================================================================


class TestLossLimits:
    """Hard limits must never be exceeded."""

    @pytest.mark.parametrize("loss_pct", [0.01, 0.05, 0.10, 0.25, 0.50])
    def test_daily_loss_pct_bounds(self, gov: PropFirmRiskGovernor, loss_pct: float) -> None:
        """Daily loss used must be between 0% and 100%."""
        loss = gov.state.initial_balance * loss_pct
        gov.state.realized_pnl_today = -loss
        used = gov.daily_loss_used_pct()
        assert 0.0 <= used <= 1.0, f"daily_loss_used_pct={used} out of [0, 1]"

    @pytest.mark.parametrize("loss_pct", [0.01, 0.05, 0.10, 0.25, 0.50])
    def test_overall_loss_pct_bounds(self, gov: PropFirmRiskGovernor, loss_pct: float) -> None:
        """Overall loss used must be between 0% and 100%."""
        ref = gov._overall_reference()
        max_allowed = ref * gov.profile.max_overall_loss_pct
        loss = max_allowed * loss_pct
        gov.update(balance=ref - loss, equity=ref - loss)
        used = gov.overall_loss_used_pct()
        assert 0.0 <= used <= 1.0, f"overall_loss_used_pct={used} out of [0, 1]"

    def test_daily_loss_ceiling(self, gov: PropFirmRiskGovernor) -> None:
        """Daily loss cannot exceed the profile's max_daily_loss_pct."""
        ref = gov._daily_reference()
        max_loss = ref * gov.profile.max_daily_loss_pct
        # Exactly at the limit — equity = ref - max_loss
        gov.update(balance=ref - max_loss, equity=ref - max_loss)
        assert gov.daily_loss_used_pct() <= 1.0
        # Slightly exceeding triggers breach
        gov.update(balance=ref - max_loss * 1.01, equity=ref - max_loss * 1.01)
        breaches = gov.evaluate()
        assert any(hasattr(b, "type") and b.type.value == "daily_loss" for b in breaches)


# =========================================================================
# Property: Max position sizing
# =========================================================================


class TestMaxPositionSize:
    """Position sizing must respect risk budget."""

    def test_max_position_size_positive(self, gov: PropFirmRiskGovernor) -> None:
        """Max position size must always be non-negative."""
        size = gov.max_position_size(entry=100.0, stop=99.0, contract_size=100)
        assert size >= 0

    def test_larger_stop_reduces_size(self, gov: PropFirmRiskGovernor) -> None:
        """Wider stop distance means smaller position."""
        tight_stop = gov.max_position_size(entry=100.0, stop=99.0, contract_size=100)
        wide_stop = gov.max_position_size(entry=100.0, stop=95.0, contract_size=100)
        assert wide_stop <= tight_stop, "Wider stop should not increase position"

    def test_larger_contract_reduces_size(self, gov: PropFirmRiskGovernor) -> None:
        """Larger contract multiplier means smaller position."""
        small_contract = gov.max_position_size(entry=100.0, stop=99.0, contract_size=100)
        large_contract = gov.max_position_size(entry=100.0, stop=99.0, contract_size=1000)
        assert large_contract <= small_contract

    def test_zero_stop_distance_returns_zero(self, gov: PropFirmRiskGovernor) -> None:
        """No stop distance means no position."""
        size = gov.max_position_size(entry=100.0, stop=100.0, contract_size=100)
        assert size == 0.0


# =========================================================================
# Property: Check order invariants
# =========================================================================


class TestCheckNewOrder:
    """Pre-trade gate invariants."""

    def test_denied_when_daily_loss_exceeded(self, gov: PropFirmRiskGovernor) -> None:
        """Orders must be denied if daily loss limit is already hit."""
        max_loss = gov.state.initial_balance * gov.profile.max_daily_loss_pct
        gov.state.realized_pnl_today = -max_loss * 1.01
        check = gov.check_new_order(entry=100.0, stop=99.0, lots=1.0, contract_size=100_000)
        assert not check.allowed

    def test_denied_when_overall_loss_exceeded(self, gov: PropFirmRiskGovernor) -> None:
        """Orders must be denied if overall loss limit is breached."""
        max_loss = gov.state.initial_balance * gov.profile.max_overall_loss_pct
        gov.state.current_balance = gov.state.initial_balance - max_loss * 1.01
        gov.state.current_equity = gov.state.current_balance
        check = gov.check_new_order(entry=100.0, stop=99.0, lots=1.0, contract_size=100_000)
        assert not check.allowed

    def test_check_returns_reason_on_deny(self, gov: PropFirmRiskGovernor) -> None:
        """Denied checks should provide a reason."""
        check = gov.check_new_order(entry=100.0, stop=99.0, lots=1000.0, contract_size=100_000)
        if not check.allowed:
            assert check.reason, "Denied check must provide a reason"
            assert len(check.reason) > 0

    def test_risk_decreases_with_daily_loss(self, gov: PropFirmRiskGovernor) -> None:
        """As daily loss accumulates, risk budget shrinks."""
        max_loss = gov.state.initial_balance * gov.profile.max_daily_loss_pct
        # No loss yet
        check1 = gov.check_new_order(entry=100.0, stop=99.0, lots=1.0, contract_size=100_000)
        # Halfway through daily loss
        gov.state.realized_pnl_today = -max_loss * 0.5
        check2 = gov.check_new_order(entry=100.0, stop=99.0, lots=1.0, contract_size=100_000)
        # Either both allowed, or check2 has smaller max_lots
        if (
            check1.allowed
            and check2.allowed
            and check1.max_lots is not None
            and check2.max_lots is not None
        ):
            assert check2.max_lots <= check1.max_lots


# =========================================================================
# Property: Daily rollover
# =========================================================================


class TestRollover:
    """Daily state reset invariants."""

    def test_daily_pnl_resets_on_rollover(self, gov: PropFirmRiskGovernor) -> None:
        """Rollover must reset daily P&L to zero."""
        gov.state.realized_pnl_today = -1000.0
        gov.rollover()
        assert gov.state.realized_pnl_today == 0.0

    def test_balance_preserved_on_rollover(self, gov: PropFirmRiskGovernor) -> None:
        """Rollover must preserve cumulative balance."""
        initial = gov.state.current_balance
        # Simulate a trade loss via update, then rollover
        gov.update(balance=initial - 1000, equity=initial - 1000)
        gov.rollover()
        assert gov.state.current_balance == initial - 1000.0
        assert gov.state.realized_pnl_today == 0.0

    def test_multiple_rollovers(self, gov: PropFirmRiskGovernor) -> None:
        """Multiple rollovers must compound correctly."""
        for _i in range(5):
            bal = gov.state.current_balance - 100.0
            gov.update(balance=bal, equity=bal)
            gov.rollover()
        expected = gov.state.initial_balance - 500.0
        assert gov.state.current_balance == expected


# =========================================================================
# Property: Challenge outcome
# =========================================================================


class TestChallengeOutcome:
    """Challenge status transitions."""

    def test_initial_is_in_progress(self, gov: PropFirmRiskGovernor) -> None:
        assert gov.challenge_outcome().value == "in_progress"

    def test_profit_target_ends_challenge(self, gov: PropFirmRiskGovernor) -> None:
        """Hitting profit target should pass the challenge."""
        target = gov.state.initial_balance * gov.profile.profit_target_pct
        gov.state.current_balance = gov.state.initial_balance + target
        gov.state.current_equity = gov.state.current_balance
        assert gov.challenge_outcome().value == "passed"

    def test_overall_loss_fails_challenge(self, gov: PropFirmRiskGovernor) -> None:
        """Hitting max overall loss should fail the challenge."""
        max_loss = gov.state.initial_balance * gov.profile.max_overall_loss_pct
        gov.update(
            balance=gov.state.initial_balance - max_loss * 1.01,
            equity=gov.state.initial_balance - max_loss * 1.01,
        )
        # evaluate() must be called to update status
        gov.evaluate()
        assert gov.challenge_outcome().value in ("failed_overall", "failed_daily")


# =========================================================================
# Property: Multiple profiles
# =========================================================================


class TestCrossProfile:
    """Properties that hold across different profiles."""

    @pytest.mark.parametrize("profile_fixture", ["gov", "topstep_gov"])
    def test_all_profiles_start_in_progress(
        self, profile_fixture: str, request: pytest.FixtureRequest
    ) -> None:
        g = request.getfixturevalue(profile_fixture)
        assert g.challenge_outcome().value == "in_progress"

    @pytest.mark.parametrize("profile_fixture", ["gov", "topstep_gov"])
    def test_all_profiles_have_positive_balance(
        self, profile_fixture: str, request: pytest.FixtureRequest
    ) -> None:
        g = request.getfixturevalue(profile_fixture)
        assert g.state.initial_balance > 0
        assert g.state.current_balance > 0

    def test_different_profiles_have_different_limits(
        self, gov: PropFirmRiskGovernor, topstep_gov: PropFirmRiskGovernor
    ) -> None:
        """Different profiles have different loss limits."""
        assert (
            gov.profile.max_daily_loss_pct != topstep_gov.profile.max_daily_loss_pct
            or gov.profile.max_overall_loss_pct != topstep_gov.profile.max_overall_loss_pct
        )
