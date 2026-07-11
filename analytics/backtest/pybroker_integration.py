"""PyBroker integration — high-performance walkforward backtesting.

Wraps Oracle's genetic engine signals into PyBroker's backtesting
pipeline for time-based walkforward validation with proper temporal
ordering (no CPCV interleaving).
"""
from __future__ import annotations

from typing import Any, Callable

import polars as pl
import numpy as np


class PyBrokerBacktest:
    """High-performance walkforward backtesting via PyBroker."""

    def __init__(self) -> None:
        self._last_result: Any = None

    def run(
        self,
        data: pl.DataFrame,
        signal_fn: Callable[[pl.DataFrame], pl.Series],
        n_windows: int = 5,
        train_size: float = 0.6,
    ) -> dict[str, float]:
        """Run walkforward backtest using PyBroker.

        Pre-computes the trading signal on the full dataset, then feeds
        it to PyBroker via the indicator API for time-based validation.

        Args:
            data: Polars OHLCV DataFrame.
            signal_fn: Function that computes trading signals from OHLCV.
            n_windows: Number of walkforward windows.
            train_size: Fraction for training each window.

        Returns:
            Dict of metrics.
        """
        import pandas as pd

        from pybroker import Strategy, indicator
        from pybroker.ext.data import DataSource

        # Pre-compute signal ONCE on full data
        signal_arr = signal_fn(data).to_numpy()

        # Convert to pandas for PyBroker
        df = data.to_pandas()
        if "date" not in df.columns and "timestamp" in df.columns:
            df = df.rename(columns={"timestamp": "date"})
        df["symbol"] = "SYMBOL"
        df["date"] = pd.to_datetime(df["date"])
        if df["date"].dt.tz is not None:
            df["date"] = df["date"].dt.tz_localize(None)

        # Attach signal as an extra column
        df["_signal"] = signal_arr

        class SignalDataSource(DataSource):
            def _fetch_data(
                self, symbols, start_date, end_date, timeframe=None, adjust=None
            ):
                mask = (df["date"] >= start_date) & (df["date"] <= end_date)
                result = df[mask].copy()
                return result

        # Compute signal from the BarData's close prices using pre-computed array
        # We use a closure to capture signal_arr and align by date
        def _signal_indicator(bar_data):
            """Return the pre-computed signal aligned by date."""
            dates = pd.DatetimeIndex(bar_data.date)
            df_dates = pd.DatetimeIndex(df["date"])
            idx = df_dates.get_indexer(dates)
            valid = idx >= 0
            result = np.zeros(len(dates), dtype=np.int8)
            result[valid] = signal_arr[idx[valid]]
            return result.astype(np.float64)

        sig_ind = indicator("knn_signal", _signal_indicator)

        def exec_fn(ctx):
            sig = ctx.indicator("knn_signal")
            if sig is None or len(sig) == 0:
                return
            latest = int(sig[-1])
            if latest == 1 and not ctx.long_pos():
                ctx.buy_shares = 100
            elif latest == -1 and not ctx.short_pos():
                ctx.sell_shares = 100
            elif latest == 0:
                if ctx.long_pos():
                    ctx.sell_all_shares()
                elif ctx.short_pos():
                    ctx.buy_shares = 100
        source = SignalDataSource()
        strategy = Strategy(
            source,
            start_date=str(df["date"].iloc[0].date()),
            end_date=str(df["date"].iloc[-1].date()),
        )
        strategy.add_execution(exec_fn, ["SYMBOL"], indicators=sig_ind)
        result = strategy.walkforward(
            timeframe="1d", windows=n_windows, train_size=train_size
        )

        self._last_result = result
        m = result.metrics
        return {
            "sharpe": float(m.sharpe),
            "sortino": float(m.sortino),
            "profit_factor": float(m.profit_factor),
            "total_return_pct": float(m.total_return_pct),
            "max_drawdown_pct": float(m.max_drawdown_pct),
            "win_rate": float(m.win_rate),
            "trade_count": int(m.trade_count),
            "calmar": float(m.calmar) if m.calmar is not None else 0.0,
            "n_windows": n_windows,
        }
