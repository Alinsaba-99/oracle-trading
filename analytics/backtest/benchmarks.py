"""Benchmark data providers and risk-free rate.

Provides synthetic / downloaded benchmark return series for performance
attribution and a default risk-free rate when no live rate is available.
"""

from __future__ import annotations

import math
from typing import Any

import polars as pl


class BenchmarkFactory:
    """Factory for benchmark return series and the risk-free rate.

    Usage
    -----
    >>> bench = BenchmarkFactory()
    >>> spy_returns = bench.spy()
    >>> rf = bench.risk_free_rate()
    """

    _spy_cache: pl.Series | None = None

    @classmethod
    def spy(cls) -> pl.Series:
        """Daily returns for SPY (SPDR S&P 500 ETF) from 2015-01-01 to 2020-12-31.

        The first call downloads via ``yfinance`` and caches the result
        in memory for subsequent calls.

        Returns
        -------
        pl.Series
            Daily returns (``(close_t - close_{t-1}) / close_{t-1}``)
            sorted chronologically (oldest first).  The name of the
            series is ``"spy_return"``.
        """
        if cls._spy_cache is not None:
            return cls._spy_cache

        try:
            import yfinance as yf
        except ImportError:
            # Fallback: synthetic SPY-like returns when yfinance is
            # unavailable (e.g. CI).
            cls._spy_cache = cls._synthetic_spy()
            return cls._spy_cache

        ticker = yf.Ticker("SPY")
        hist: Any = ticker.history(start="2015-01-01", end="2020-12-31")
        if hist.empty:
            cls._spy_cache = cls._synthetic_spy()
            return cls._spy_cache

        close = hist["Close"].to_numpy(dtype=float)
        rets = [(close[i] - close[i - 1]) / close[i - 1] for i in range(1, len(close))]
        cls._spy_cache = pl.Series("spy_return", rets)
        return cls._spy_cache

    @classmethod
    def risk_free_rate(cls) -> float:
        """Current-ish annualised risk-free rate.

        Tries to fetch the US 10-year Treasury yield from Yahoo Finance
        (``^TNX``).  On any failure returns 0.05 (5 %) as a sensible
        default for backtest attribution contexts.

        Returns
        -------
        float
            Annualised risk-free rate as a decimal (e.g. ``0.05`` for
            5 %).
        """
        try:
            import yfinance as yf

            tnx = yf.Ticker("^TNX")
            hist = tnx.history(period="5d")
            if not hist.empty:
                last_close = float(hist["Close"].iloc[-1])
                if 0.0 < last_close < 100.0:
                    return last_close / 100.0
        except Exception:
            pass
        return 0.05

    # ── internal ────────────────────────────────────────────────────

    @classmethod
    def _synthetic_spy(cls) -> pl.Series:
        """Generate a plausible SPY return series (annualised vol ~15 %)."""
        import numpy as np

        rng = np.random.default_rng(42)
        n = 252 * 5  # ~5 years of daily data
        daily_vol = 0.15 / math.sqrt(252)
        returns = rng.normal(loc=0.0006, scale=daily_vol, size=n)
        return pl.Series("spy_return", returns)
