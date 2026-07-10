"""BacktestSignal protocol — structural interface for all trading signal classes.

Every signal used in the GA fitness evaluator must satisfy this protocol:
a callable that takes market data and returns a -1 / 0 / 1 signal Series.
"""

from __future__ import annotations

from typing import Protocol

import polars as pl


class BacktestSignal(Protocol):
    """Protocol that all trading signal classes must implement.

    A signal takes market data and returns -1, 0, or 1 for each bar.
    """

    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Compute trading signals from market data.

        Args:
            data: OHLCV DataFrame with at minimum a ``close`` column.

        Returns:
            :class:`pl.Series` of dtype Int8 with values -1, 0, or 1.
        """
        ...
