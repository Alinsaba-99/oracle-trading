"""CuratedAlphaLibrary — registry of all 50 alpha factors organized by category.

Provides batch computation, factor lookup, and metadata for every
factor in the curated library.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import polars as pl

from genetics.alpha import factors

FactorFunc = Callable[[pl.DataFrame], pl.Series]


CATEGORIES: dict[str, list[str]] = {
    "momentum": [
        "roc_1m",
        "roc_3m",
        "roc_6m",
        "roc_12m",
        "mom_1m_exc_last",
        "mom_reversal",
        "weighted_mom",
        "exponential_mom",
        "momentum_trend",
        "momentum_stability",
    ],
    "mean_reversion": [
        "rsi_14",
        "bb_position",
        "distance_from_sma_20",
        "distance_from_sma_50",
        "zscore_20",
        "mean_reversion_speed",
        "serial_correlation",
        "idiosyncratic_reversion",
    ],
    "volatility": [
        "atr_14",
        "bb_width",
        "historical_vol_20",
        "historical_vol_60",
        "parkinson_vol",
        "yang_zhang_vol",
    ],
    "correlation": [
        "corr_to_spy",
        "corr_to_sector",
        "corr_stability",
        "beta_60",
        "beta_120",
        "idiosyncratic_vol",
    ],
    "volume": ["volume_zscore_20", "volume_trend", "dollar_volume", "turnover", "volume_vs_avg"],
    "seasonality": [
        "month_effect",
        "day_of_week",
        "quarter_effect",
        "turning_month",
        "january_effect",
    ],
    "fundamental_proxies": [
        "div_yield",
        "earnings_yield",
        "book_to_price",
        "cash_flow_yield",
        "payout_ratio",
    ],
    "microstructure": [
        "bid_ask_spread_est",
        "amihud_illiquidity",
        "roll_impact",
        "lot_size_adj",
        "price_reversal_1d",
    ],
}


# Build factor registry: name -> (func, metadata)
_FACTOR_META: dict[str, dict[str, Any]] = {
    k: {"category": c, "description": d}
    for k, c, d in [
        ("roc_1m", "momentum", "ROC 1m (21d)"),
        ("roc_3m", "momentum", "ROC 3m (63d)"),
        ("roc_6m", "momentum", "ROC 6m (126d)"),
        ("roc_12m", "momentum", "ROC 12m (252d)"),
        ("mom_1m_exc_last", "momentum", "1m mom excl last day"),
        ("mom_reversal", "momentum", "Short-term reversal (neg 1d ret)"),
        ("weighted_mom", "momentum", "Weighted avg 1m/3m/6m/12m ROC"),
        ("exponential_mom", "momentum", "EWMA of returns"),
        ("momentum_trend", "momentum", "Momentum acceleration (delta 21d ROC)"),
        ("momentum_stability", "momentum", "Ratio of positive return days"),
        ("rsi_14", "mean_reversion", "RSI (Wilder, p=14)"),
        ("bb_position", "mean_reversion", "BB position (close-sma)/2*std"),
        ("distance_from_sma_20", "mean_reversion", "% distance from 20d SMA"),
        ("distance_from_sma_50", "mean_reversion", "% distance from 50d SMA"),
        ("zscore_20", "mean_reversion", "20d z-score of close"),
        ("mean_reversion_speed", "mean_reversion", "Mean rev speed (inv half-life autocorr)"),
        ("serial_correlation", "mean_reversion", "Lag-1 autocorr of returns/20d"),
        ("idiosyncratic_reversion", "mean_reversion", "Idio rev (neg resid from mkt model)"),
        ("atr_14", "volatility", "ATR (Wilder, p=14) norm by close"),
        ("bb_width", "volatility", "BB width (upper-lower)/sma_20"),
        ("historical_vol_20", "volatility", "20d hist vol (annualized)"),
        ("historical_vol_60", "volatility", "60d hist vol (annualized)"),
        ("parkinson_vol", "volatility", "Parkinson vol estimator (20d)"),
        ("yang_zhang_vol", "volatility", "Yang-Zhang vol estimator (20d)"),
        ("corr_to_spy", "correlation", "60d rolling corr to mkt proxy"),
        ("corr_to_sector", "correlation", "60d rolling corr to sector proxy"),
        ("corr_stability", "correlation", "Stability of mkt corr"),
        ("beta_60", "correlation", "60d mkt beta"),
        ("beta_120", "correlation", "120d mkt beta"),
        ("idiosyncratic_vol", "correlation", "Idio vol (resid vol after mkt adj)"),
        ("volume_zscore_20", "volume", "20d volume z-score"),
        ("volume_trend", "volume", "Vol trend (slope log-vol/20d)"),
        ("dollar_volume", "volume", "Dollar vol norm by SMA(20)"),
        ("turnover", "volume", "Turnover (vol/sma_60(vol))"),
        ("volume_vs_avg", "volume", "Volume vs 20d avg"),
        ("month_effect", "seasonality", "Month-of-year effect"),
        ("day_of_week", "seasonality", "Day-of-week effect"),
        ("quarter_effect", "seasonality", "Quarter-of-year effect"),
        ("turning_month", "seasonality", "Turning-month indicator"),
        ("january_effect", "seasonality", "January effect indicator"),
        ("div_yield", "fundamental_proxies", "Div yield proxy"),
        ("earnings_yield", "fundamental_proxies", "Earnings yield proxy"),
        ("book_to_price", "fundamental_proxies", "Book-to-price proxy"),
        ("cash_flow_yield", "fundamental_proxies", "CF yield proxy"),
        ("payout_ratio", "fundamental_proxies", "Payout ratio proxy"),
        ("bid_ask_spread_est", "microstructure", "Bid-ask spread (Roll 1984)"),
        ("amihud_illiquidity", "microstructure", "Amihud illiquidity (2002)"),
        ("roll_impact", "microstructure", "Roll impact (|ret|/dollar vol)"),
        ("lot_size_adj", "microstructure", "Lot size adj (1/close)"),
        ("price_reversal_1d", "microstructure", "1d price reversal"),
    ]
}


class CuratedAlphaLibrary:
    """Registry of all 50 curated alpha factors.

    Organizes factors by category and provides batch computation and
    metadata lookup for the factor library.

    Categories:
        momentum (10), mean_reversion (8), volatility (6),
        correlation (6), volume (5), seasonality (5),
        fundamental_proxies (5), microstructure (5)
    """

    def __init__(self) -> None:
        self._registry: dict[str, FactorFunc] = self._build_registry()

    # ------------------------------------------------------------------
    # Category constants
    # ------------------------------------------------------------------
    CATEGORIES: dict[str, list[str]] = CATEGORIES
    FACTOR_META: dict[str, dict[str, Any]] = _FACTOR_META

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    @staticmethod
    def _build_registry() -> dict[str, FactorFunc]:
        """Build the factor name -> function mapping."""
        return {
            "roc_1m": factors.roc_1m,
            "roc_3m": factors.roc_3m,
            "roc_6m": factors.roc_6m,
            "roc_12m": factors.roc_12m,
            "mom_1m_exc_last": factors.mom_1m_exc_last,
            "mom_reversal": factors.mom_reversal,
            "weighted_mom": factors.weighted_mom,
            "exponential_mom": factors.exponential_mom,
            "momentum_trend": factors.momentum_trend,
            "momentum_stability": factors.momentum_stability,
            "rsi_14": factors.rsi_14,
            "bb_position": factors.bb_position,
            "distance_from_sma_20": factors.distance_from_sma_20,
            "distance_from_sma_50": factors.distance_from_sma_50,
            "zscore_20": factors.zscore_20,
            "mean_reversion_speed": factors.mean_reversion_speed,
            "serial_correlation": factors.serial_correlation,
            "idiosyncratic_reversion": factors.idiosyncratic_reversion,
            "atr_14": factors.atr_14,
            "bb_width": factors.bb_width,
            "historical_vol_20": factors.historical_vol_20,
            "historical_vol_60": factors.historical_vol_60,
            "parkinson_vol": factors.parkinson_vol,
            "yang_zhang_vol": factors.yang_zhang_vol,
            "corr_to_spy": factors.corr_to_spy,
            "corr_to_sector": factors.corr_to_sector,
            "corr_stability": factors.corr_stability,
            "beta_60": factors.beta_60,
            "beta_120": factors.beta_120,
            "idiosyncratic_vol": factors.idiosyncratic_vol,
            "volume_zscore_20": factors.volume_zscore_20,
            "volume_trend": factors.volume_trend,
            "dollar_volume": factors.dollar_volume,
            "turnover": factors.turnover,
            "volume_vs_avg": factors.volume_vs_avg,
            "month_effect": factors.month_effect,
            "day_of_week": factors.day_of_week,
            "quarter_effect": factors.quarter_effect,
            "turning_month": factors.turning_month,
            "january_effect": factors.january_effect,
            "div_yield": factors.div_yield,
            "earnings_yield": factors.earnings_yield,
            "book_to_price": factors.book_to_price,
            "cash_flow_yield": factors.cash_flow_yield,
            "payout_ratio": factors.payout_ratio,
            "bid_ask_spread_est": factors.bid_ask_spread_est,
            "amihud_illiquidity": factors.amihud_illiquidity,
            "roll_impact": factors.roll_impact,
            "lot_size_adj": factors.lot_size_adj,
            "price_reversal_1d": factors.price_reversal_1d,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def factor_names(self) -> list[str]:
        """Return list of all 50 factor names."""
        return list(self._registry.keys())

    def get(self, name: str) -> FactorFunc:
        """Get a factor function by name.

        Args:
            name: Factor name.

        Returns:
            The factor function.

        Raises:
            KeyError: If factor name is not found.
        """
        if name not in self._registry:
            msg = f"Unknown factor: {name}. Available: {sorted(self._registry)}"
            raise KeyError(msg)
        return self._registry[name]

    def compute(self, data: pl.DataFrame, names: list[str] | None = None) -> dict[str, pl.Series]:
        """Compute specified factors (or all 50) on the given data.

        Args:
            data: OHLCV DataFrame with columns [timestamp, open, high, low, close, volume].
            names: List of factor names to compute. If None, computes all.

        Returns:
            Dict mapping factor names to computed Series.
        """
        factor_names = names if names is not None else self.factor_names
        results: dict[str, pl.Series] = {}
        for name in factor_names:
            func = self.get(name)
            results[name] = func(data)
        return results

    @property
    def metadata(self) -> dict[str, dict[str, Any]]:
        """Return metadata dict for all factors.

        Each entry: {name: {category: str, description: str}}
        """
        return {name: dict(_FACTOR_META.get(name, {})) for name in self.factor_names}
