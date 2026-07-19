"""Volatility-scaled backtest — the F6b lever to cut daily-loss breaches.

The Monte Carlo evaluation (Fase 7) showed the dominant failure mode for
prop-firm challenges is ``fail_d`` — a single day dropping more than the
3% daily limit.  With a fixed notional that happens whenever volatility
spikes.  **Volatility-scaled sizing** deploys a fraction of equity
inversely proportional to recent ATR, so the per-trade (and per-day)
risk stays bounded regardless of how volatile the instrument is:

    size_pct = risk_pct / (stop_atr_mult * ATR%)

On a high-ATR day the position shrinks; the same adverse move costs a
smaller fraction of equity.  This mirrors stratevo's ``market_regime``
sensitivity + Kelly-style sizing (see [[strategy-research]]).

This module builds its own vectorbt portfolio (long-flat, percent sizing)
rather than modifying :class:`VectorizedEngine`, keeping sizing a
strategy-layer concern.  The equity curve feeds the Monte Carlo harness
exactly like an engine-produced :class:`BacktestResult`.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import numpy as np
import polars as pl

from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import (
    _ensure_datetime_index,
    _infer_freq,
    _normalise_vbt_price,
)
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult
from analytics.technical.polars_indicators import atr


def atr_percent_sizes(
    data: pl.DataFrame,
    atr_period: int = 14,
    risk_pct: float = 0.01,
    stop_atr_mult: float = 2.0,
    max_pct: float = 1.0,
) -> pl.Series:
    """Per-bar fraction-of-equity to deploy, scaled inversely to ATR%.

    Args:
        data: OHLCV polars frame.
        atr_period: ATR lookback.
        risk_pct: Target risk per trade as a fraction of equity (1% rule).
        stop_atr_mult: Stop distance in ATR multiples (sets notional).
        max_pct: Cap on the deployed fraction (e.g. 1.0 = full equity).
    """
    high = data["high"] if "high" in data.columns else data["High"]
    low = data["low"] if "low" in data.columns else data["Low"]
    close = data["close"] if "close" in data.columns else data["Close"]
    a = atr(high, low, close, atr_period)
    atr_pct = a / close  # fraction of price
    stop_pct = stop_atr_mult * atr_pct
    size = (risk_pct / stop_pct).clip(upper_bound=max_pct)
    return size.fill_nan(0.0).fill_null(0.0).clip(lower_bound=0.0)


def sized_backtest(
    data: pl.DataFrame,
    signal: BacktestSignal,
    instrument_id: str = "",
    settings: BacktestConfig | None = None,
    atr_period: int = 14,
    risk_pct: float = 0.01,
    stop_atr_mult: float = 2.0,
    max_pct: float = 1.0,
) -> BacktestResult:
    """Run a long-flat backtest with volatility-scaled percent sizing."""
    import vectorbt as vbt
    from vectorbt.portfolio.enums import OppositeEntryMode

    cfg = settings or BacktestConfig()
    df = _ensure_datetime_index(_normalise_vbt_price(data.to_pandas()))
    if "Close" not in df.columns:
        raise ValueError("DataFrame must contain a 'close' column.")

    raw = np.asarray(signal.compute(data), dtype=np.int64)
    raw = np.roll(raw, 1)
    raw[0] = 0  # no execution on the first bar (no prior close)

    entries = raw == 1
    exits = raw == 0
    sizes = atr_percent_sizes(
        data, atr_period=atr_period, risk_pct=risk_pct, stop_atr_mult=stop_atr_mult, max_pct=max_pct
    ).to_numpy()

    portfolio = vbt.Portfolio.from_signals(
        df["Close"],
        entries=entries,
        exits=exits,
        upon_opposite_entry=OppositeEntryMode.Close,
        accumulate=False,
        size=sizes,
        size_type="percent",
        slippage=cfg.slippage_bps / 10_000.0,
        fees=cfg.commission_pct,
        init_cash=float(cfg.initial_capital),
        freq=_infer_freq(df.index),
    )

    metrics = portfolio.stats(silence_warnings=True)

    def _m(key: str, default: float = 0.0) -> float:
        val = metrics.get(key, default)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)

    equity = portfolio.value()
    equity_list = equity.to_numpy(dtype=np.float64).tolist()
    final = equity_list[-1] if equity_list else float(cfg.initial_capital)
    cash = float(cfg.initial_capital)

    return BacktestResult(
        run_id=str(uuid4()),
        strategy_name=type(signal).__name__,
        instrument=instrument_id,
        engine="sized",
        total_return=_m("Total Return [%]") / 100.0,
        sharpe_ratio=_m("Sharpe Ratio"),
        sortino_ratio=_m("Sortino Ratio"),
        calmar_ratio=_m("Calmar Ratio"),
        max_drawdown=_m("Max Drawdown [%]") / 100.0,
        volatility=_m("Volatility [%]") / 100.0,
        total_trades=int(_m("Total Trades")),
        win_rate=_m("Win Rate [%]") / 100.0,
        profit_factor=_m("Profit Factor"),
        initial_capital=Decimal(str(cash)),
        final_equity=final,
        equity_curve=equity_list,
    )
