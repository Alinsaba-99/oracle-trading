"""BacktestPortfolio — aggregate and rebalance across multiple results."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import polars as pl

from analytics.backtest.result import BacktestResult
from core.domain.enums import TradeDirection, TradeStatus
from core.domain.trade import Trade


class BacktestPortfolio:
    """Aggregates multiple :class:`BacktestResult` objects.

    Holds results from different strategies, instruments, or folds and
    provides methods to compute combined equity, allocate capital based
    on optimisation weights, and generate rebalance trades.
    """

    def __init__(self, results: list[BacktestResult] | None = None) -> None:
        self._results: list[BacktestResult] = list(results) if results else []

    # ── result management ───────────────────────────────────────────

    def add_result(self, result: BacktestResult) -> None:
        """Add a single backtest result."""
        self._results.append(result)

    @property
    def results(self) -> list[BacktestResult]:
        """Read-only view of held results."""
        return list(self._results)

    # ── capital allocation ─────────────────────────────────────────

    def allocation(
        self, optimizer_result: dict[str, float], capital: Decimal
    ) -> dict[str, Decimal]:
        """Compute capital allocation per asset from target weights.

        Args:
            optimizer_result: Dict mapping asset name to target weight.
            capital: Total capital to distribute.

        Returns:
            Dict mapping asset name to allocated capital (as Decimal).
        """
        if not optimizer_result:
            return {}

        total_weight = sum(optimizer_result.values())
        if total_weight == 0:
            return {asset: Decimal("0") for asset in optimizer_result}

        return {
            asset: (Decimal(str(weight)) / Decimal(str(total_weight))) * capital
            for asset, weight in optimizer_result.items()
        }

    # ── combined equity ─────────────────────────────────────────────

    def combined_equity(self) -> pl.Series:
        """Sum the equity curves of all held results.

        Returns:
            A Polars Series with the combined equity curve.  Shorter
            curves are forward-filled from their last value.
        """
        if not self._results:
            return pl.Series("equity", [])

        curves = [r.equity_curve for r in self._results]
        max_len = max(len(c) for c in curves)

        padded: list[list[float]] = []
        for c in curves:
            if len(c) < max_len:
                fill = [c[-1]] * (max_len - len(c)) if c else [0.0] * max_len
                padded.append(c + fill)
            else:
                padded.append(c[:max_len])

        combined = [sum(x) for x in zip(*padded, strict=True)]
        return pl.Series("equity", combined)

    # ── rebalance trades ────────────────────────────────────────────

    def rebalance(
        self, dates: list[datetime], weights: dict[str, float], capital: Decimal | None = None
    ) -> list[Trade]:
        """Generate rebalance trades for target weights at given dates.

        Each (date, asset) pair produces a single ``Trade`` with
        quantity proportional to the target weight weighted across all
        provided dates.

        Args:
            dates: Rebalance dates.
            weights: Target allocation ``{asset_name: weight}``.
            capital: Notional capital for quantity scaling.  Falls back
                     to the sum of ``initial_capital`` across results if
                     ``None``.

        Returns:
            List of ``Trade`` objects, one per asset per date.
        """
        if not dates or not weights:
            return []

        total_weight = sum(abs(w) for w in weights.values())
        if total_weight == 0:
            return []

        if capital is None:
            capital = sum((r.initial_capital for r in self._results), Decimal("0"))
        if capital == Decimal("0"):
            capital = Decimal("100000")

        trades: list[Trade] = []
        for date in dates:
            for asset, weight in weights.items():
                direction = TradeDirection.long if weight >= 0 else TradeDirection.short
                # Scale quantity proportionally across dates and weights.
                quantity = Decimal(str(abs(weight))) * capital / Decimal(str(len(dates)))

                trades.append(
                    Trade(
                        instrument_id=asset,
                        direction=direction,
                        status=TradeStatus.open,
                        entry_price=Decimal("0"),
                        quantity=quantity,
                        entry_time=date,
                    )
                )

        return trades
