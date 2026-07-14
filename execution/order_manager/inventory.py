"""Position and P&L tracking for the order manager."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from execution.order_manager.types import FillReport


class InventoryTracker:
    """Track open positions and P&L."""

    def __init__(self, daily_loss_limit: float = -10000.0) -> None:
        self._positions: dict[str, dict[str, Any]] = {}
        self._daily_pnl: float = 0.0
        #: Account is "breached" when daily P&L falls below this (negative)
        #: threshold.  In prop-firm mode this is wired to the
        #: :class:`~policy.prop_firm.PropFirmRiskGovernor`'s daily-loss budget;
        #: the default keeps legacy behaviour.
        self._daily_loss_limit: float = daily_loss_limit

    def update(self, order: Any, fill: FillReport) -> None:
        """Update position from a fill event."""
        pos = self._positions.setdefault(
            order.instrument_id, {"qty": Decimal("0"), "avg_price": Decimal("0"), "pnl": 0.0}
        )
        if order.side == "buy":
            pos["qty"] += fill.quantity
        else:
            pos["qty"] -= fill.quantity
        pos["avg_price"] = fill.price

    def position(self, instrument_id: str) -> Decimal:
        """Return current net position quantity for an instrument."""
        return cast(Decimal, self._positions.get(instrument_id, {}).get("qty", Decimal("0")))

    def daily_pnl(self) -> float:
        """Return running daily P&L."""
        return self._daily_pnl

    def breached_daily_limit(self) -> bool:
        """Return True if daily P&L is below the loss limit."""
        return self._daily_pnl < self._daily_loss_limit
