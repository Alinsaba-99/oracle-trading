"""Backtest configuration model."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class BacktestConfig(BaseModel):
    """Configuration for a single backtest run."""

    engine: str = "vectorized"
    slippage_bps: float = Field(default=5.0, ge=0)
    commission_pct: float = Field(default=0.001, ge=0, le=1)
    initial_capital: Decimal = Decimal("100000")

    def to_settings(self) -> dict[str, float | str | int]:
        """Return a dict suitable for passing to vectorbt / nautilus."""
        return {
            "initial_capital": float(self.initial_capital),
            "slippage_bps": self.slippage_bps,
            "commission_pct": self.commission_pct,
            "engine": self.engine,
        }
