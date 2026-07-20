"""Composite multi-TF signal — wraps a primary-TF signal with a filter-TF signal (R2.3).

The composite is itself a :class:`BacktestSignal`: it accepts a primary-TF
OHLCV frame, internally delegates to a primary signal and a filter signal,
and returns the combined per-bar signal.

Because the filter signal needs the filter-TF frame to compute, the
composite exposes two usage patterns:

1. **Pre-attached columns** (preferred for vectorbt/lean loops): the
   caller has already run ``MultiTFComposer.attach_filter_signal`` and the
   primary frame carries a ``signal_{filter_tf}`` column. The composite
   just reads it.
2. **Explicit filter_df**: the caller passes the filter-TF frame and the
   composite computes the filter signal itself, then broadcasts it via
   the composer.

Modes:

- ``gate``: primary fires only when the filter signal is non-zero in the
  allowed direction (long-only by default; flip with ``filter_sign``).
- ``confirm``: primary and filter must *agree* (same sign); otherwise 0.
- ``size``: primary's value is scaled by the filter's magnitude
  (e.g. trend strength); here the filter signal is treated as a
  multiplier, so ``1`` keeps size, ``0`` kills it, ``-1`` flips it.
"""

from __future__ import annotations

from enum import StrEnum

import polars as pl

from analytics.backtest.protocol import BacktestSignal
from analytics.strategy.multi_tf import MultiTFComposer


class CompositeMode(StrEnum):
    GATE = "gate"
    CONFIRM = "confirm"
    SIZE = "size"


class CompositeMTFSignal:
    """Multi-TF composition of a primary + filter signal.

    Args:
        primary_signal: signal computed on the primary-TF frame.
        filter_signal: signal computed on the filter-TF frame.
        primary_tf: e.g. ``"1h"``.
        filter_tf: e.g. ``"1d"`` (must be strictly higher than primary).
        mode: combination rule (gate / confirm / size).
        filter_sign: +1 to require filter long bias, -1 to require short.
            Only used in ``gate`` mode.
    """

    def __init__(
        self,
        primary_signal: BacktestSignal,
        filter_signal: BacktestSignal,
        *,
        primary_tf: str,
        filter_tf: str,
        mode: str = "gate",
        filter_sign: int = 1,
    ) -> None:
        self.primary_signal = primary_signal
        self.filter_signal = filter_signal
        self.primary_tf = primary_tf
        self.filter_tf = filter_tf
        self.mode = CompositeMode(mode)
        if filter_sign not in (1, -1):
            raise ValueError(f"filter_sign must be +1 or -1, got {filter_sign}")
        self.filter_sign = filter_sign
        self._composer = MultiTFComposer(primary_tf, filter_tf)

    @property
    def filter_signal_col(self) -> str:
        return f"signal_{self.filter_tf}"

    # ------------------------------------------------------------------
    def compute(self, data: pl.DataFrame) -> pl.Series:
        """Default entry-point for BacktestSignal protocol.

        Requires that ``data`` already carries the broadcast filter signal
        column (via ``MultiTFComposer.attach_filter_signal``). If you have
        a separate filter_df, use :meth:`compute_with_filter` instead.
        """
        if self.filter_signal_col not in data.columns:
            raise ValueError(
                f"{self.filter_signal_col!r} column missing — call "
                f"MultiTFComposer.attach_filter_signal first, or use "
                f"compute_with_filter(primary_df, filter_df)"
            )
        primary_sig = self.primary_signal.compute(data)
        filter_sig = data[self.filter_signal_col]
        return self._combine(primary_sig, filter_sig)

    def compute_with_filter(self, primary_df: pl.DataFrame, filter_df: pl.DataFrame) -> pl.Series:
        """Two-frame variant: compute the filter signal on ``filter_df``,
        broadcast to primary rows, then combine with the primary signal.
        """
        filter_sig_series = self.filter_signal.compute(filter_df)
        combined_df = self._composer.attach_filter_signal(
            primary_df, filter_df, filter_sig_series, signal_col=self.filter_signal_col
        )
        primary_sig = self.primary_signal.compute(primary_df)
        return self._combine(primary_sig, combined_df[self.filter_signal_col])

    # ------------------------------------------------------------------
    def _combine(self, primary: pl.Series, filter_sig: pl.Series) -> pl.Series:
        """Element-wise combine. Null filter values are treated as 0 (no
        confirmation — the safe default for gate/confirm, kills size)."""
        n = primary.len()
        if filter_sig.len() != n:
            raise ValueError(f"signal length mismatch: primary={n} filter={filter_sig.len()}")
        filter_filled = filter_sig.fill_null(0)

        if self.mode == CompositeMode.GATE:
            allowed = filter_filled * self.filter_sign > 0
            return pl.Series([int(p) if allowed[i] else 0 for i, p in enumerate(primary.to_list())])
        if self.mode == CompositeMode.CONFIRM:
            return pl.Series(
                [
                    int(p) if (p * f > 0) else 0
                    for p, f in zip(primary.to_list(), filter_filled.to_list(), strict=True)
                ]
            )
        # SIZE — filter scales primary (sign of filter can flip direction).
        return pl.Series(
            [
                int(p) * float(f)
                for p, f in zip(primary.to_list(), filter_filled.to_list(), strict=True)
            ]
        )
