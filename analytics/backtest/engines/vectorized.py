"""VectorizedEngine — wraps vectorbt for fast OHLCV backtesting.

Usage
-----
    from analytics.backtest.engines.vectorized import VectorizedEngine
    from analytics.backtest.config import BacktestConfig
    from analytics.backtest.protocol import BacktestSignal

    engine = VectorizedEngine()
    result = engine.run(data, my_signal, BacktestConfig())
    print(result.sharpe_ratio)
    equity = engine.equity_curve()
    trades = engine.trades()
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import numpy as np
import pandas as pd
import polars as pl
import vectorbt as vbt
from vectorbt.portfolio.enums import OppositeEntryMode

from analytics.backtest.config import BacktestConfig
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult
from core.domain.enums import TradeDirection, TradeStatus
from core.domain.trade import Trade


def _normalise_vbt_price(df: pd.DataFrame) -> pd.DataFrame:
    """Rename lower-case OHLCV columns to vectorbt capitalised convention.

    Column name detection is case-insensitive; matches ``open``,
    ``high``, ``low``, ``close``, ``volume``.  Unmatched columns
    are kept verbatim.
    """
    rename: dict[str, str] = {}
    for col in df.columns:
        lower = str(col).strip().lower()
        mapped = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }.get(lower)
        if mapped is not None:
            rename[col] = mapped
    return df.rename(columns=rename)


def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    """Promote a datetime-like column to the index if the index is not already datetime."""
    if isinstance(df.index, pd.DatetimeIndex):
        return df
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return df.set_index(col)
    # No datetime column — use a sequential integer index.
    return df


def _infer_freq(index: pd.Index) -> str | None:
    """Try to infer a pandas frequency string from the index."""
    if isinstance(index, pd.DatetimeIndex):
        inferred: str | None = pd.infer_freq(index)
        if inferred:
            return inferred
    if hasattr(index, "freq") and index.freq is not None:
        return str(index.freq)
    return None


class _SmaCrossoverSignal:
    """SMA crossover reference strategy (50 / 200) on daily data.

    Designed for cross-engine validation — the expected Sharpe ratio
    on SPY 2015-2020 daily data is approximately 0.3-0.5.
    """

    def __init__(self, fast: int = 50, slow: int = 200) -> None:
        self.fast = fast
        self.slow = slow

    def compute(self, data: pl.DataFrame) -> pl.Series:
        close_col = "close" if "close" in data.columns else "Close"
        close_raw = data[close_col]
        close_np = close_raw.to_numpy().astype(np.float64)

        # rolling mean via pandas (handles window edge behaviour)
        as_pd = close_raw.to_pandas()
        fast_series = as_pd.rolling(self.fast).mean()
        slow_series = as_pd.rolling(self.slow).mean()

        fast_arr = fast_series.to_numpy()
        slow_arr = slow_series.to_numpy()

        # crossover: fast > slow and was <= slow on previous bar
        prev_fast = np.roll(fast_arr, 1)
        prev_slow = np.roll(slow_arr, 1)
        prev_fast[0] = np.nan
        prev_slow[0] = np.nan

        long_cond = (fast_arr > slow_arr) & (prev_fast <= prev_slow)
        short_cond = (fast_arr < slow_arr) & (prev_fast >= prev_slow)

        # Build position: 1 after crossover, 0 after crossunder
        pos = 0
        sig_vals = np.zeros(len(close_np), dtype=np.int64)
        for i in range(len(close_np)):
            if long_cond[i] and not np.isnan(fast_arr[i]):
                pos = 1
            elif short_cond[i] and not np.isnan(fast_arr[i]):
                pos = 0
            sig_vals[i] = pos

        return pl.Series("signal", sig_vals)


class VectorizedEngine:
    """Vectorized backtesting engine powered by vectorbt.

    Accepts a :class:`BacktestSignal` protocol implementation, runs a
    single-instrument backtest via vectorbt's ``Portfolio.from_signals``,
    and returns structured metrics inside a :class:`BacktestResult`.
    """

    def __init__(self) -> None:
        self._equity: pl.Series | None = None
        self._trades_list: list[Trade] = []
        self._result: BacktestResult | None = None
        self._portfolio: vbt.Portfolio | None = None

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def run(
        self, data: pl.DataFrame, signal: BacktestSignal, settings: BacktestConfig | None = None
    ) -> BacktestResult:
        """Execute a vectorized backtest.

        Parameters
        ----------
        data:
            OHLCV data as a Polars DataFrame.  Expected columns (case
            insensitive): ``open``, ``high``, ``low``, ``close``, and
            optionally ``volume``.  A datetime column is auto-detected
            and used as the index.
        signal:
            A :class:`BacktestSignal` implementation whose ``compute``
            method returns -1 (short), 0 (neutral), or 1 (long).
        settings:
            Backtest configuration.  Defaults to ``BacktestConfig()``
            when ``None``.

        Returns
        -------
        BacktestResult
            Populated result containing all standard performance
            metrics plus the equity curve and trade log.
        """
        cfg = settings or BacktestConfig()

        # ── convert to pandas for vectorbt ──────────────────────────
        df = _normalise_vbt_price(data.to_pandas())
        df = _ensure_datetime_index(df)

        if "Close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column.")

        # ── compute signal ──────────────────────────────────────────
        signal_series = signal.compute(data)
        raw = np.asarray(signal_series, dtype=np.int64)

        # ── execution delay: shift signal by 1 bar ────────────────
        # Signal at bar i uses close[i]; execution can only happen at
        # bar i+1 at the earliest.  Shifting prevents look-ahead.
        raw = np.roll(raw, 1)
        raw[0] = 0  # first bar: no signal (no prior close)

        # ── build entry / exit arrays ───────────────────────────────
        # signal:  1 = long, -1 = short, 0 = flat
        entries = raw == 1
        exits = raw == 0
        short_entries = raw == -1
        short_exits = raw == 0

        # ── detect frequency for annualised metrics ─────────────────
        freq = _infer_freq(df.index)

        # ── vectorbt portfolio ──────────────────────────────────────
        slippage_decimal = cfg.slippage_bps / 10_000.0

        self._portfolio = vbt.Portfolio.from_signals(
            df["Close"],
            entries=entries,
            exits=exits,
            short_entries=short_entries,
            short_exits=short_exits,
            upon_opposite_entry=OppositeEntryMode.Close,
            accumulate=False,
            slippage=slippage_decimal,
            fees=cfg.commission_pct,
            init_cash=float(cfg.initial_capital),
            freq=freq,
        )

        # ── extract metrics ─────────────────────────────────────────
        metrics = self._portfolio.stats(silence_warnings=True)

        def _metric(key: str, default: float = 0.0) -> float:
            val = metrics.get(key, default)
            if val is None:
                return default
            if isinstance(val, float) and np.isnan(val):
                return default
            return float(val)

        total_return = _metric("Total Return [%]")
        sharpe = _metric("Sharpe Ratio")
        sortino = _metric("Sortino Ratio")
        calmar = _metric("Calmar Ratio")
        max_dd = _metric("Max Drawdown [%]")
        volatility = _metric("Volatility [%]")

        total_trades = int(_metric("Total Trades"))
        win_rate = _metric("Win Rate [%]")
        profit_factor = _metric("Profit Factor")
        avg_win = _metric("Avg Winning Trade [%]")
        avg_loss = _metric("Avg Losing Trade [%]")

        # ── equity curve ────────────────────────────────────────────
        equity_pd = self._portfolio.value()
        self._equity = pl.Series("equity", equity_pd.to_numpy(dtype=np.float64))

        # ── trades ──────────────────────────────────────────────────
        self._trades_list = self._extract_trades(close=df["Close"])

        # ── time bounds ─────────────────────────────────────────────
        start_time: datetime | None = None
        end_time: datetime | None = None
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
            start_time = df.index[0].to_pydatetime()
            end_time = df.index[-1].to_pydatetime()

        # ── CAGR ────────────────────────────────────────────────────
        cash = float(cfg.initial_capital)
        final_equity = float(equity_pd.iloc[-1]) if len(equity_pd) > 0 else cash
        years = (
            (end_time - start_time).total_seconds() / (365.25 * 86400)
            if start_time and end_time
            else 1.0
        )
        cagr = ((final_equity / cash) ** (1.0 / max(years, 1e-10)) - 1.0) if cash > 0 else 0.0

        self._result = BacktestResult.from_metrics(
            run_id=str(uuid4()),
            strategy_name="",
            instrument="",
            start_time=start_time,
            end_time=end_time,
            total_return=total_return / 100.0,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd / 100.0 if max_dd else 0.0,
            volatility=volatility / 100.0 if volatility else 0.0,
            cagr=cagr,
            total_trades=total_trades,
            win_rate=win_rate / 100.0 if win_rate else 0.0,
            profit_factor=profit_factor,
            avg_win=avg_win / 100.0 if avg_win else 0.0,
            avg_loss=abs(avg_loss / 100.0) if avg_loss else 0.0,
            initial_capital=cfg.initial_capital,
            final_equity=final_equity,
            equity_curve=self._equity.to_list(),
            trades=self._trades_list,
        )
        return self._result

    def equity_curve(self) -> pl.Series:
        """Return the equity curve from the most recent backtest."""
        if self._equity is None:
            return pl.Series("equity", [])
        return self._equity

    def trades(self) -> list[Trade]:
        """Return the trade log from the most recent backtest."""
        return list(self._trades_list)

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _extract_trades(self, close: pd.Series) -> list[Trade]:
        """Convert vectorbt trade records to core domain Trade models."""
        result: list[Trade] = []

        if self._portfolio is None:
            return result

        records = self._portfolio.trades.records
        if records is None or len(records) == 0:
            return result

        index = close.index
        for _, row in records.iterrows():
            entry_idx = int(row["entry_idx"])
            exit_idx = int(row["exit_idx"])
            direction_val = int(row.get("direction", 0))

            entry_price_val = float(row["entry_price"])
            exit_price_val = float(row["exit_price"])
            qty = abs(float(row.get("size", 0.0)))
            pnl_val = float(row.get("pnl", 0.0))
            ret_pct = float(row.get("return", 0.0))

            entry_time: datetime | None = None
            exit_time: datetime | None = None
            if isinstance(index, pd.DatetimeIndex):
                if 0 <= entry_idx < len(index):
                    entry_time = index[entry_idx].to_pydatetime()
                if 0 <= exit_idx < len(index):
                    exit_time = index[exit_idx].to_pydatetime()

            trade = Trade(
                trade_id=str(uuid4()),
                instrument_id="",
                direction=TradeDirection.long if direction_val in (0, 1) else TradeDirection.short,
                status=TradeStatus.closed if exit_time is not None else TradeStatus.open,
                entry_price=Decimal(str(entry_price_val)),
                exit_price=(
                    Decimal(str(exit_price_val))
                    if entry_price_val != exit_price_val or exit_time
                    else None
                ),
                quantity=Decimal(str(qty)),
                pnl=Decimal(str(pnl_val)),
                pnl_pct=ret_pct,
                entry_time=entry_time or datetime.min,
                exit_time=exit_time,
                exit_reason="signal" if exit_time else None,
            )
            result.append(trade)
        return result


def sma_crossover_signal(fast: int = 50, slow: int = 200) -> BacktestSignal:
    """Factory for the SMA crossover reference signal.

    Returns a :class:`BacktestSignal` instance that computes a
    -1 / 0 / 1 signal from fast/slow simple moving averages.
    """
    return _SmaCrossoverSignal(fast=fast, slow=slow)
