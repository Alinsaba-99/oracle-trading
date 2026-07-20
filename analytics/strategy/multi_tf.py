"""Multi-timeframe composition via polars ``join_asof`` (R2.2).

The core operation for multi-TF strategies: given a primary-TF OHLCV frame
(e.g. 1h bars) and a filter-TF OHLCV frame (e.g. 1d bars), attach to every
primary row the most recent *closed* filter bar. This is what lets a
signal on 1h bars gate itself on the state of the daily trend without
look-ahead.

Key safety property — **no look-ahead**: a primary bar at time ``t`` must
only see filter bars whose *close* time is strictly ≤ ``t``. With a
``backward`` ``join_asof`` on the filter bar's *open* timestamp this is
almost right, but a primary bar at ``t == filter.open`` would attach the
filter bar that has just opened (not yet closed) — a look-ahead. We avoid
it by joining on the filter bar's **close timestamp** (``open + duration -
1µs``), so a filter bar becomes visible only once it has fully closed.

The compose step also renames filter columns with a ``_{filter_tf}`` suffix
(e.g. ``close_1d``), so signals can address them unambiguously.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import polars as pl

from analytics.strategy.timeframe import tf_duration, validate_pair

if TYPE_CHECKING:
    from analytics.backtest.providers import DataRegistry

#: Column used as the time key in OHLCV frames throughout the repo.
TIMESTAMP_COL: str = "timestamp"

#: OHLCV columns that get suffixed when broadcasting from filter to primary.
BROADCAST_COLS: tuple[str, ...] = ("open", "high", "low", "close", "volume")


def _close_timestamp_expr(tf: str) -> pl.Expr:
    """Filter bar close time = open time + bar duration - 1µs.

    The ``-1µs`` ensures that a 1d bar opening at 2026-07-20 00:00 is
    visible to a 1h primary bar at 2026-07-20 23:00 (the primary bar's
    timestamp is *inside* the filter bar), but not to one at 2026-07-21
    00:00 *if* we wanted strict less-than — actually we do want it visible
    there too. Using close = open + duration - 1µs gives the last
    microsecond of the bar, which is exactly when it becomes "closed".
    """
    delta = tf_duration(tf)
    delta_us = int(delta.total_seconds() * 1_000_000) - 1
    return pl.col(TIMESTAMP_COL) + pl.duration(microseconds=delta_us)


class MultiTFComposer:
    """Compose a primary-TF frame with a filter-TF frame via ``join_asof``.

    The composer is stateless; one instance can be reused across many pairs
    and timeframes.
    """

    def __init__(self, primary_tf: str, filter_tf: str) -> None:
        validate_pair(primary_tf, filter_tf)
        self.primary_tf = primary_tf
        self.filter_tf = filter_tf

    # ------------------------------------------------------------------
    def _prepare_filter(self, filter_df: pl.DataFrame) -> pl.DataFrame:
        """Add the filter bar's close timestamp and rename OHLCV cols with
        the filter TF suffix. Sorted by close-ts (join_asof requirement).
        """
        suffix = f"_{self.filter_tf}"
        renames = {c: f"{c}{suffix}" for c in BROADCAST_COLS if c in filter_df.columns}
        return (
            filter_df.with_columns(_close_timestamp_expr(self.filter_tf).alias("_filter_close_ts"))
            .rename(renames)
            .sort("_filter_close_ts")
        )

    def compose(
        self, primary_df: pl.DataFrame, filter_df: pl.DataFrame, *, keep_filter_ts: bool = False
    ) -> pl.DataFrame:
        """Attach filter columns to each primary row (backward, no look-ahead).

        Args:
            primary_df: primary-TF OHLCV frame (must have ``timestamp`` col).
            filter_df: filter-TF OHLCV frame (same schema).
            keep_filter_ts: when True keep the ``_filter_close_ts`` column
                (useful for tests/debug). Default drops it.

        Returns:
            A new Polars frame with one row per primary row, in original
            primary order, with extra ``{open,high,low,close,volume}_{filter_tf}``
            columns. Rows whose timestamp precedes the first available
            filter close get null in those columns.
        """
        if primary_df.is_empty():
            return primary_df
        if filter_df.is_empty():
            # Attach null columns so downstream signals see a stable schema.
            suffix = f"_{self.filter_tf}"
            out = primary_df
            for c in BROADCAST_COLS:
                if c in primary_df.columns:
                    out = out.with_columns(pl.lit(None).alias(f"{c}{suffix}"))
            return out

        prepared_filter = self._prepare_filter(filter_df)
        # Keep only close-ts + suffixed OHLCV for the join.
        keep_cols = ["_filter_close_ts"] + [
            f"{c}_{self.filter_tf}" for c in BROADCAST_COLS if c in filter_df.columns
        ]
        prepared_filter = prepared_filter.select(keep_cols)

        # Sort primary by timestamp (required by join_asof), remember original order.
        sorted_primary = primary_df.with_row_index("_orig_idx").sort(TIMESTAMP_COL)

        joined = sorted_primary.join_asof(
            prepared_filter, left_on=TIMESTAMP_COL, right_on="_filter_close_ts", strategy="backward"
        )

        # Restore original order.
        joined = joined.sort("_orig_idx").drop("_orig_idx")
        if not keep_filter_ts:
            joined = joined.drop("_filter_close_ts")
        return joined

    # ------------------------------------------------------------------
    def attach_filter_signal(
        self,
        primary_df: pl.DataFrame,
        filter_df: pl.DataFrame,
        filter_signal: pl.Series,
        *,
        signal_col: str | None = None,
    ) -> pl.DataFrame:
        """Broadcast a per-bar filter signal onto primary rows.

        Args:
            primary_df: primary-TF OHLCV frame.
            filter_df: filter-TF OHLCV frame (must be same length as
                ``filter_signal``).
            filter_signal: signal Series aligned with ``filter_df`` rows,
                values in ``{-1, 0, 1}`` (or any numeric gate).
            signal_col: name of the broadcast column (default
                ``signal_{filter_tf}``).

        Returns:
            ``primary_df`` with one extra column of the filter signal value
            that was in force at each primary row's timestamp.
        """
        if filter_df.height != filter_signal.len():
            raise ValueError(
                f"filter_df and filter_signal length mismatch: "
                f"{filter_df.height} vs {filter_signal.len()}"
            )
        col_name = signal_col or f"signal_{self.filter_tf}"
        filter_with_sig = filter_df.with_columns(filter_signal.alias(col_name))

        if primary_df.is_empty():
            return primary_df
        if filter_with_sig.is_empty():
            return primary_df.with_columns(pl.lit(None).alias(col_name))

        prepared = (
            filter_with_sig.with_columns(
                _close_timestamp_expr(self.filter_tf).alias("_filter_close_ts")
            )
            .select(["_filter_close_ts", col_name])
            .sort("_filter_close_ts")
        )

        sorted_primary = primary_df.with_row_index("_orig_idx").sort(TIMESTAMP_COL)
        joined = sorted_primary.join_asof(
            prepared, left_on=TIMESTAMP_COL, right_on="_filter_close_ts", strategy="backward"
        )
        joined = joined.sort("_orig_idx").drop(["_orig_idx", "_filter_close_ts"])
        return joined


# ----------------------------------------------------------------------
# R2.5: DataRegistry fetch_pair helper
# ----------------------------------------------------------------------
def fetch_pair(
    registry: DataRegistry,
    instrument_id: str,
    primary_tf: str,
    filter_tf: str,
    *,
    period: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    force: bool = False,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Fetch ``(primary_df, filter_df)`` for one instrument via a DataRegistry.

    Thin wrapper around ``DataRegistry.get_ohlcv`` that enforces the
    multi-TF invariant (``filter_tf > primary_tf``) and returns both
    frames ready for ``MultiTFComposer``.
    """
    validate_pair(primary_tf, filter_tf)
    primary_df = registry.get_ohlcv(
        instrument_id, primary_tf, period=period, start=start, end=end, force=force
    )
    filter_df = registry.get_ohlcv(
        instrument_id, filter_tf, period=period, start=start, end=end, force=force
    )
    return primary_df, filter_df
