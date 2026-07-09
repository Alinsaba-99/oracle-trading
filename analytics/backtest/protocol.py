"""Backtest signal protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import polars as pl


@runtime_checkable
class BacktestSignal(Protocol):
    """A signal function that computes trading signals from market data.

    The ``compute`` method accepts a Polars DataFrame with market data
    and returns a Polars Series with values -1 (short), 0 (neutral), or
    1 (long). The returned Series must be aligned with the input rows.
    """

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute trading signals from the given market data.

        Args:
            data: Market data as a Polars DataFrame.

        Returns:
            A Polars Series with values -1, 0, or 1, aligned with input rows.
        """
        ...
