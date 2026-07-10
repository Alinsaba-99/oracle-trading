"""PortfolioBridge — converts PortfolioDecision (Phase 4) to OrderRequest (Phase 5).

Responsibilities:
- Map MAS decision to executable order
- float -> Decimal with quantize(0.0001)
- Map confidence -> execution algo (high=market, low=VWAP)
- Call RiskManager gate #1 (pre-decision check) or integration point
- Handle hold/no_trade decisions gracefully (return None)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger("oracle.execution.bridge")


class PortfolioBridge:
    """Converts PortfolioDecision (Phase 4) to OrderRequest (Phase 5)."""

    def __init__(self, risk_manager: Any | None = None) -> None:
        self._risk = risk_manager

    def to_order_request(self, decision: Any) -> Any | None:
        """Convert PortfolioDecision to OrderRequest.

        Args:
            decision: PortfolioDecision (from agents.protocol)

        Returns:
            OrderRequest if direction is buy/sell
            None if direction is hold/no_trade

        Raises:
            ValueError if direction is invalid
        """
        from execution.order_manager.types import OrderRequest

        if decision.direction in ("hold", "no_trade"):
            return None

        if decision.direction not in ("buy", "sell"):
            raise ValueError(f"Invalid direction: {decision.direction}")

        algo = self._confidence_to_algo(decision.confidence)

        return OrderRequest(
            instrument_id=decision.instrument,
            side=decision.direction,
            quantity=Decimal(str(decision.position_size)).quantize(Decimal("0.0001")),
            execution_algo=algo,
            algo_config={"confidence": decision.confidence},
            source="mas",
        )

    @staticmethod
    def _confidence_to_algo(confidence: float) -> str:
        """Map confidence to execution algo."""
        if confidence >= 0.7:
            return "market"
        if confidence >= 0.4:
            return "vwap"
        return "twap"

    def to_order_request_with_risk_check(
        self,
        decision: Any,
        portfolio: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> Any | None:
        """Convert + pre-check via RiskManager gate #1."""
        req = self.to_order_request(decision)
        if req is None:
            return None
        if self._risk is not None and not self._risk.check_order(req):
            logger.info("risk_gate_rejected", instrument=decision.instrument)
            return None
        return req
