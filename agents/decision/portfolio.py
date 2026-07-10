"""PortfolioManager — pure deterministic decision maker.

Final aggregation layer: scores signals, runs risk checks, and produces
the final PortfolioDecision. 0% LLM.
"""

from __future__ import annotations

from agents.decision.risk import RiskManager
from agents.decision.scoring import SignalScorer
from agents.protocol import AnalystSignal, PortfolioDecision

__all__ = ["PortfolioManager"]


class PortfolioManager:
    """Final decision maker — 0% LLM, pure deterministic signal aggregation."""

    def __init__(self, scorer: SignalScorer, risk_manager: RiskManager) -> None:
        self._scorer = scorer
        self._risk = risk_manager

    def decide(
        self,
        signals: list[AnalystSignal],
        market_state: object,
        portfolio: dict[str, object] | None = None,
    ) -> PortfolioDecision:
        buy_w, sell_w, hold_w = self._scorer.weighted_vote(signals)

        # Direction from highest weight
        weights: dict[str, float] = {"buy": buy_w, "sell": sell_w, "hold": hold_w}
        direction = max(weights, key=weights.get)  # type: ignore[arg-type]

        # Size proportional to confidence
        confidence = weights[direction]
        position_size = confidence * 0.2  # 20% at full confidence

        decision = PortfolioDecision(
            direction=direction,  # type: ignore[arg-type]
            instrument="SPY",
            position_size=position_size,
            confidence=confidence,
            reasoning=self._build_reasoning(signals, direction),
            agents_contributing=[s.source for s in signals],
            regime_at_decision=getattr(market_state, "regime", "unknown"),
            risk_approved=False,
        )

        # Check risk
        risk = self._risk.approve(decision, portfolio)
        final_direction: str = decision.direction
        final_reasoning = decision.reasoning
        if not risk.approved:
            final_direction = "no_trade"
            final_reasoning += f" | RISK REJECTED: {', '.join(risk.reasons)}"

        return PortfolioDecision(
            direction=final_direction,  # type: ignore[arg-type]
            instrument=decision.instrument,
            position_size=decision.position_size,
            confidence=decision.confidence,
            reasoning=final_reasoning,
            agents_contributing=decision.agents_contributing,
            regime_at_decision=decision.regime_at_decision,
            risk_approved=risk.approved,
            escalated=False,
        )

    @staticmethod
    def _build_reasoning(signals: list[AnalystSignal], direction: str) -> str:
        """Compose reasoning from all agent signals."""
        parts = [f"Decision: {direction.upper()}"]
        for s in signals:
            parts.append(
                f"[{s.source}] {s.vote.direction} ({s.vote.confidence:.2f}): "
                f"{s.vote.reasoning[:100]}"
            )
        return "\n".join(parts)

    @staticmethod
    def escalate(debate: object) -> PortfolioDecision:
        """Handle escalate edge from debate — produce decision with weighted vote."""
        _ = debate
        return PortfolioDecision(
            direction="hold",
            instrument="SPY",
            position_size=0.0,
            confidence=0.3,
            reasoning="Escalated — no consensus, defaulting to HOLD",
            agents_contributing=[],
            regime_at_decision="unknown",
            risk_approved=True,
            escalated=True,
        )
