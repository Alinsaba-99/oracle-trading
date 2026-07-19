"""PortfolioBridge — converts PortfolioDecision (Phase 4) to OrderRequest (Phase 5).

Responsibilities:
- Map MAS decision to executable order
- Convert fraction-of-portfolio to share/contract quantity using portfolio value and price
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
    """Converts PortfolioDecision (Phase 4) to OrderRequest (Phase 5).

    The ``risk_manager`` parameter is required.  Passing ``None`` raises
    ``ValueError`` — a missing risk gate is a safety violation.
    """

    def __init__(self, risk_manager: Any, portfolio_value: Decimal | None = None) -> None:
        if risk_manager is None:
            raise ValueError("risk_manager is required — a missing risk gate is a safety violation")
        self._risk = risk_manager
        self._portfolio_value = portfolio_value or Decimal("100000")  # default $100k

    def set_portfolio_value(self, value: Decimal) -> None:
        """Update the portfolio value for position sizing."""
        self._portfolio_value = value

    def to_order_request(self, decision: Any, current_price: Decimal | None = None) -> Any | None:
        """Convert PortfolioDecision to OrderRequest.

        The decision's ``position_size`` is treated as a **fraction of
        the portfolio** (0.0 to 1.0).  The bridge multiplies it by the
        current portfolio value and divides by the current price to
        compute the correct number of shares/contracts.

        Args:
            decision: PortfolioDecision (from agents.protocol)
            current_price: Current market price for sizing conversion.
                          Uses fallback ``$100`` when unavailable.

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

        # Convert fraction-of-portfolio -> quantity in units
        fraction = Decimal(str(decision.position_size)).quantize(Decimal("0.0001"))
        price = current_price or Decimal("100")
        target_value = (self._portfolio_value * fraction).quantize(Decimal("0.01"))
        quantity = (target_value / price).quantize(Decimal("0.0001"))

        algo = self._confidence_to_algo(decision.confidence)

        return OrderRequest(
            instrument_id=decision.instrument,
            side=decision.direction,
            quantity=quantity,
            execution_algo=algo,
            algo_config={"confidence": decision.confidence, "target_value": str(target_value)},
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
        if not self._risk.check_order(req):
            logger.info("risk_gate_rejected", instrument=decision.instrument)
            return None
        return req
