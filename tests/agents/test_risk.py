"""Tests for RiskManager — Kelly, VaR, CVaR, drawdown, position sizing."""

from __future__ import annotations

import pytest

from agents.decision.risk import RiskManager
from agents.protocol import PortfolioDecision


class TestKellyFraction:
    """Kelly criterion calculations."""

    def test_fifty_win_two_to_one(self) -> None:
        """50% win rate, 2:1 reward:risk → f* = 0.25."""
        # f* = p - q/b = 0.5 - 0.5/2 = 0.5 - 0.25 = 0.25
        result = RiskManager.kelly_fraction(win_rate=0.5, avg_win=2.0, avg_loss=1.0)
        assert result == pytest.approx(0.25)

    def test_zero_win_rate(self) -> None:
        """Zero win rate → 0.0."""
        result = RiskManager.kelly_fraction(win_rate=0.0, avg_win=2.0, avg_loss=1.0)
        assert result == 0.0

    def test_never_loses_capped(self) -> None:
        """Win rate 1.0 → kelly capped at 1.0."""
        result = RiskManager.kelly_fraction(win_rate=1.0, avg_win=1.0, avg_loss=1.0)
        assert result == 1.0

    def test_zero_avg_loss(self) -> None:
        """Zero avg_loss returns 0.0 to avoid division by zero."""
        result = RiskManager.kelly_fraction(win_rate=0.5, avg_win=2.0, avg_loss=0.0)
        assert result == 0.0

    def test_zero_avg_win(self) -> None:
        """Zero avg_win → b=0 → kelly = 0."""
        result = RiskManager.kelly_fraction(win_rate=0.5, avg_win=0.0, avg_loss=1.0)
        assert result == 0.0

    def test_negative_avg_loss(self) -> None:
        """avg_loss is negative (the convention); b computed on absolute value."""
        # b = 3.0 / 1.5 = 2, q = 0.6, f* = 0.4 - 0.6/2 = 0.4 - 0.3 = 0.1
        result = RiskManager.kelly_fraction(win_rate=0.4, avg_win=3.0, avg_loss=-1.5)
        assert result == pytest.approx(0.1)

    def test_kelly_clamp_negative(self) -> None:
        """Negative raw kelly is clamped to 0.0."""
        # b = 1/2 = 0.5, q = 0.7, f* = 0.3 - 0.7/0.5 = 0.3 - 1.4 = -1.1
        result = RiskManager.kelly_fraction(win_rate=0.3, avg_win=1.0, avg_loss=2.0)
        assert result == 0.0


class TestValueAtRisk:
    """Historical VaR calculations."""

    def test_var_negative(self) -> None:
        """Normal-ish distribution returns a negative VaR value."""
        returns = [-0.05, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05]
        var = RiskManager.var(returns, alpha=0.1)
        # bottom 10% → index 1 → -0.03
        assert var == pytest.approx(-0.03)

    def test_var_empty(self) -> None:
        """Empty returns → 0.0."""
        assert RiskManager.var([]) == 0.0

    def test_var_alpha_at_edge(self) -> None:
        """Alpha that lands exactly on an index boundary."""
        returns = [0.1, 0.2, 0.3, 0.4]
        var = RiskManager.var(returns, alpha=0.25)
        assert var == pytest.approx(0.2)

    def test_var_single_element(self) -> None:
        """Single-element list returns that element."""
        assert RiskManager.var([0.42], alpha=0.05) == 0.42


class TestConditionalVaR:
    """Expected shortfall beyond VaR."""

    def test_cvar_less_than_var(self) -> None:
        """CVaR is strictly less (more negative) than VaR."""
        returns = [-0.10, -0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08]
        var = RiskManager.var(returns, alpha=0.2)
        cvar = RiskManager.cvar(returns, alpha=0.2)
        assert cvar < var

    def test_cvar_empty(self) -> None:
        """Empty returns → 0.0."""
        assert RiskManager.cvar([]) == 0.0

    def test_cvar_tail_average(self) -> None:
        """CVaR is the average of the tail."""
        returns = [-0.10, -0.06, -0.02, 0.02, 0.06, 0.10]
        cvar = RiskManager.cvar(returns, alpha=0.3)
        # bottom 30% ≈ 1 element → -0.10 (since len=6, idx=1, tail = [-0.10])
        assert cvar == pytest.approx(-0.10)

    def test_cvar_single_tail_element(self) -> None:
        """Alpha yields exactly one tail element."""
        returns = [-0.05, 0.01, 0.02]
        cvar = RiskManager.cvar(returns, alpha=0.3)
        # idx = 0, tail = [-0.05]
        assert cvar == pytest.approx(-0.05)


class TestMaxDrawdown:
    """Maximum drawdown calculations."""

    def test_monotonically_up(self) -> None:
        """Always rising → max drawdown = 0.0."""
        equity = [100.0, 101.0, 102.0, 105.0, 110.0]
        assert RiskManager.max_drawdown(equity) == 0.0

    def test_fifty_percent_crash(self) -> None:
        """50% crash from peak → max drawdown = 0.5."""
        equity = [100.0, 110.0, 105.0, 55.0, 60.0]
        # peak = 110, trough = 55, dd = (110-55)/110 = 0.5
        assert RiskManager.max_drawdown(equity) == pytest.approx(0.5)

    def test_single_element(self) -> None:
        """Single element → 0.0."""
        assert RiskManager.max_drawdown([100.0]) == 0.0

    def test_empty_list(self) -> None:
        """Empty list → 0.0."""
        assert RiskManager.max_drawdown([]) == 0.0

    def test_recovery_after_drawdown(self) -> None:
        """Drawdown measured from peak before crash, not from local trough."""
        equity = [100.0, 200.0, 150.0, 180.0]
        # peak = 200, trough = 150, dd = 50/200 = 0.25
        assert RiskManager.max_drawdown(equity) == pytest.approx(0.25)

    def test_double_dip_maximum(self) -> None:
        """Largest drawdown is reported even after partial recovery."""
        equity = [100.0, 90.0, 80.0, 85.0, 70.0]
        # peak = 100, trough = 70, dd = 30/100 = 0.3
        assert RiskManager.max_drawdown(equity) == pytest.approx(0.3)


class TestMaxPositionSize:
    """Position size limits based on volatility."""

    def test_high_vol_smaller_position(self) -> None:
        """Higher volatility reduces max position size."""
        low_vol = RiskManager.max_position_size(equity=100_000, volatility=0.01)
        high_vol = RiskManager.max_position_size(equity=100_000, volatility=0.05)
        assert high_vol < low_vol

    def test_zero_equity(self) -> None:
        """Zero equity → 0.0."""
        assert RiskManager.max_position_size(equity=0.0, volatility=0.02) == 0.0

    def test_zero_volatility(self) -> None:
        """Zero volatility → 0.0."""
        assert RiskManager.max_position_size(equity=100_000, volatility=0.0) == 0.0

    def test_custom_max_pct(self) -> None:
        """Custom max_pct changes the risk capital."""
        result = RiskManager.max_position_size(equity=100_000, volatility=0.02, max_pct=0.1)
        # risk_capital = 100k * 0.1 = 10k, / 0.02 = 500k
        assert result == pytest.approx(500_000.0)

    def test_negative_equity(self) -> None:
        """Negative equity → 0.0."""
        assert RiskManager.max_position_size(equity=-1000.0, volatility=0.02) == 0.0


class TestApprove:
    """RiskManager.approve hard limit checks."""

    def test_position_too_large_rejected(self) -> None:
        """Position size > 0.25 → rejected with reason."""
        rm = RiskManager()
        decision = PortfolioDecision(
            direction="buy",
            instrument="SPY",
            position_size=0.5,
            confidence=0.8,
            reasoning="test",
            agents_contributing=["macro"],
            regime_at_decision="bull",
            risk_approved=False,
        )
        assessment = rm.approve(decision)
        assert not assessment.approved
        assert "Position size exceeds 25% max" in assessment.reasons

    def test_small_position_approved(self) -> None:
        """Position size ≤ 0.25 → approved."""
        rm = RiskManager()
        decision = PortfolioDecision(
            direction="buy",
            instrument="SPY",
            position_size=0.1,
            confidence=0.8,
            reasoning="test",
            agents_contributing=["macro"],
            regime_at_decision="bull",
            risk_approved=False,
        )
        assessment = rm.approve(decision)
        assert assessment.approved


class TestCorrelationCheck:
    """Correlation threshold check."""

    def test_no_correlation_data_passes(self) -> None:
        """No entries for the instrument → passes (no correlation found)."""
        assert RiskManager.correlation_check({"SPY": 0.9}, "QQQ")

    def test_high_correlation_rejected(self) -> None:
        """Correlation above threshold → rejected."""
        assert not RiskManager.correlation_check({"SPY:QQQ": 0.85}, "QQQ")

    def test_low_correlation_passes(self) -> None:
        """Correlation below threshold → passes."""
        assert RiskManager.correlation_check({"SPY:QQQ": 0.3}, "QQQ")


class TestHelpers:
    """Miscellaneous edge-case coverage."""

    def test_kelly_and_var_no_crosstalk(self) -> None:
        """Static methods are independent — no shared state."""
        k = RiskManager.kelly_fraction(0.5, 2.0, 1.0)
        v = RiskManager.var([-0.1, -0.05, 0.0, 0.05, 0.1], alpha=0.2)
        assert k == pytest.approx(0.25)
        assert v == pytest.approx(-0.05)

    def test_cvar_empty_tail_zero_alpha(self) -> None:
        """Alpha=0.0 returns first element (tail length forced to 1)."""
        returns = [-0.05, 0.01, 0.02]
        cvar = RiskManager.cvar(returns, alpha=0.0)
        assert cvar == pytest.approx(-0.05)
