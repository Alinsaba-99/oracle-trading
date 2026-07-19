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

        ``corr_matrix`` maps ``"INSTRUMENT_A:INSTRUMENT_B"`` (or just
        ``"INSTRUMENT_A"`` when the key represents the correlation of
        *instrument* against an existing position) to a correlation
        coefficient in ``[-1, 1]``.

        Returns ``False`` if any correlation with *instrument* exceeds
        *threshold* in absolute value.
        """
        for key, coeff in corr_matrix.items():
            if instrument not in key and key != instrument:
                continue
            if abs(coeff) > threshold:
                return False
        return True

    def approve(
        self, decision: PortfolioDecision, portfolio: dict[str, object] | None = None
    ) -> RiskAssessment:
        """Apply hard risk limits. Returns approved or rejected with reasons.

        When *portfolio* contains historical data the metrics are computed
        from it; otherwise sensible defaults are used.
        """
        pf: dict[str, object] = portfolio or {}
        reasons: list[str] = []

        raw_pct = pf.get("max_position_pct", 0.25)
        max_pct: float = float(raw_pct) if isinstance(raw_pct, (int, float)) else 0.25

        # Position size limit
        if decision.position_size > max_pct:
            reasons.append(f"Position size exceeds {max_pct:.0%} max")

        # Confidence floor
        raw_conf = pf.get("min_confidence", 0.0)
        min_confidence: float = float(raw_conf) if isinstance(raw_conf, (int, float)) else 0.0
        if decision.confidence < min_confidence:
            reasons.append(
                f"Confidence {decision.confidence:.2f} below minimum {min_confidence:.2f}"
            )

        # VaR from portfolio returns (if provided)
        returns = pf.get("returns", [])
        var_95: float
        kelly: float
        if isinstance(returns, list) and returns:
            var_95 = self.var(returns, alpha=0.05)
            # Kelly from portfolio trade history (if provided)
            trades = pf.get("trades", [])
            if isinstance(trades, list) and trades:
                wins = [t for t in trades if t > 0]
                losses = [t for t in trades if t < 0]
                if wins and losses:
                    win_rate = len(wins) / len(trades)
                    avg_win = sum(wins) / len(wins)
                    avg_loss = abs(sum(losses) / len(losses))
                    kelly = self.kelly_fraction(win_rate, avg_win, avg_loss)
                else:
                    kelly = 0.0
            else:
                kelly = 0.0
        else:
            var_95 = 0.0
            kelly = 0.0

        # Correlation check (if matrix provided)
        corr_matrix = pf.get("correlations", {})
        if (
            isinstance(corr_matrix, dict)
            and corr_matrix
            and not self.correlation_check(corr_matrix, decision.instrument, threshold=0.7)
        ):
            reasons.append("Correlation with existing positions exceeds 0.7")

        approved = len(reasons) == 0
        return RiskAssessment(
            approved=approved,
            max_position_size=max_pct,
            kelly_fraction=kelly,
            var_95=var_95,
            reasons=reasons,
        )
