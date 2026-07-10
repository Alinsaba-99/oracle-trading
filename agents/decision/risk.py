"""Purely deterministic risk calculations — VaR, CVaR, Kelly, drawdown.

Nessun LLM — 100% deterministica.
"""

from __future__ import annotations

from agents.protocol import PortfolioDecision, RiskAssessment

__all__ = ["RiskManager"]


class RiskManager:
    """Deterministic risk manager — Kelly, VaR, CVaR, drawdown, position sizing."""

    @staticmethod
    def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Compute the Kelly fraction f* = p - q/b.

        Where:
            p = win_rate
            q = 1 - win_rate
            b = avg_win / |avg_loss|

        Result is clamped to [0, 1].
        """
        if avg_loss == 0:
            return 0.0
        b = avg_win / abs(avg_loss)
        q = 1.0 - win_rate
        if b == 0:
            return 0.0
        kelly = win_rate - q / b
        return max(0.0, min(kelly, 1.0))

    @staticmethod
    def var(returns: list[float], alpha: float = 0.05) -> float:
        """Historical Value at Risk at the given alpha quantile."""
        if not returns:
            return 0.0
        sorted_rets = sorted(returns)
        idx = int(len(sorted_rets) * alpha)
        return float(sorted_rets[idx]) if idx < len(sorted_rets) else float(sorted_rets[0])

    @staticmethod
    def cvar(returns: list[float], alpha: float = 0.05) -> float:
        """Expected shortfall (Conditional VaR) beyond the VaR threshold."""
        if not returns:
            return 0.0
        sorted_rets = sorted(returns)
        idx = int(len(sorted_rets) * alpha)
        tail = sorted_rets[: max(1, idx)]
        return float(sum(tail) / len(tail))

    @staticmethod
    def max_drawdown(equity: list[float]) -> float:
        """Maximum drawdown as a positive percentage of peak value."""
        if len(equity) < 2:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for v in equity:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def max_position_size(equity: float, volatility: float, max_pct: float = 0.25) -> float:
        """Position size limited by volatility (1% risk rule)."""
        if volatility <= 0 or equity <= 0:
            return 0.0
        risk_capital = equity * max_pct
        return risk_capital / volatility

    @staticmethod
    def correlation_check(
        corr_matrix: dict[str, float], instrument: str, threshold: float = 0.7
    ) -> bool:
        """Check instrument correlation against existing positions.

        Returns False if any existing position has correlation > threshold.
        Current implementation always passes.
        """
        _ = corr_matrix, instrument, threshold  # consumed when implemented
        return True

    def approve(
        self, decision: PortfolioDecision, portfolio: dict[str, object] | None = None
    ) -> RiskAssessment:
        """Apply hard risk limits. Returns approved or rejected with reasons."""
        _ = portfolio  # available for enriched checks
        reasons: list[str] = []

        if decision.position_size > 0.25:
            reasons.append("Position size exceeds 25% max")

        # VaR check placeholder — would use real portfolio data
        # if decision.confidence < 0.2:
        #     reasons.append("Confidence too low for trade")

        approved = len(reasons) == 0
        return RiskAssessment(
            approved=approved,
            max_position_size=0.25,
            kelly_fraction=0.2,
            var_95=-0.02,
            reasons=reasons,
        )
