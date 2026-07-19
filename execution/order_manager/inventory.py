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
        """Update position from a fill event — track avg entry and realized P&L."""
        pos = self._positions.setdefault(
            order.instrument_id, {"qty": Decimal("0"), "avg_price": Decimal("0"), "pnl": 0.0}
        )
        old_qty: Decimal = pos["qty"]
        old_avg: Decimal = pos["avg_price"]
        fill_qty: Decimal = fill.quantity
        fill_price: Decimal = fill.price
        side: str = order.side

        if side == "buy":
            new_qty = old_qty + fill_qty
            if old_qty < 0:
                # Covering a short — realised P&L
                closed_qty = min(abs(old_qty), fill_qty)
                realized_pnl = float(old_avg - fill_price) * float(closed_qty)
                self._daily_pnl += realized_pnl
                pos["pnl"] = float(pos["pnl"]) + realized_pnl
                remaining = fill_qty - closed_qty
                if remaining > 0:
                    pos["avg_price"] = fill_price  # flipped to long
                elif abs(new_qty) > 0:
                    pos["avg_price"] = old_avg  # partial cover
                else:
                    pos["avg_price"] = Decimal("0")  # fully closed
            else:
                # Adding to long / opening
                if old_qty == 0:
                    pos["avg_price"] = fill_price
                else:
                    pos["avg_price"] = (old_avg * old_qty + fill_price * fill_qty) / new_qty
        else:  # sell
            new_qty = old_qty - fill_qty
            if old_qty > 0:
                # Closing a long — realised P&L
                closed_qty = min(old_qty, fill_qty)
                realized_pnl = float(fill_price - old_avg) * float(closed_qty)
                self._daily_pnl += realized_pnl
                pos["pnl"] = float(pos["pnl"]) + realized_pnl
                remaining = fill_qty - closed_qty
                if remaining > 0:
                    pos["avg_price"] = fill_price  # flipped to short
                elif abs(new_qty) > 0:
                    pos["avg_price"] = old_avg  # partial close
                else:
                    pos["avg_price"] = Decimal("0")  # fully closed
            else:
                # Adding to short / opening
                if old_qty == 0:
                    pos["avg_price"] = fill_price
                else:
                    pos["avg_price"] = (old_avg * abs(old_qty) + fill_price * fill_qty) / abs(
                        new_qty
                    )

        pos["qty"] = new_qty

    def position(self, instrument_id: str) -> Decimal:
        """Return current net position quantity for an instrument."""
        return cast(Decimal, self._positions.get(instrument_id, {}).get("qty", Decimal("0")))

    def daily_pnl(self) -> float:
        """Return running daily P&L."""
        return self._daily_pnl

    def breached_daily_limit(self) -> bool:
        """Return True if daily P&L is below the loss limit."""
        return self._daily_pnl < self._daily_loss_limit
