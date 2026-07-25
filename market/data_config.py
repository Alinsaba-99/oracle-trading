"""Data source configuration — centralized API keys and provider settings.

Set via environment variables (prefixed with ``ORACLE_DATA_``) or
directly in this module during development.

Usage::

    from market.data_config import DataConfig
    config = DataConfig()
    config.polygon_key  # → from env ORACLE_DATA_POLYGON_KEY or ""
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class DataProvider(StrEnum):
    YFINANCE = "yfinance"
    CCXT = "ccxt"
    OPENBB = "openbb"
    POLYGON = "polygon"
    FRED = "fred"
    IBKR = "ibkr"
    ALPHAI = "alphai"
    ALPHAVANTAGE = "alphavantage"


# Provider capabilities matrix
PROVIDER_CAPABILITIES: dict[DataProvider, dict[str, bool]] = {
    DataProvider.YFINANCE: {
        "futures_daily": True,
        "futures_intraday": False,  # No 1m/5m for futures
        "equity_daily": True,
        "equity_intraday": True,  # 1h for some tickers
        "crypto_daily": True,
        "fx_daily": True,
        "options": False,
        "macro": False,
        "news": False,
    },
    DataProvider.CCXT: {
        "futures_daily": False,
        "futures_intraday": False,
        "crypto_spot": True,
        "crypto_futures": True,  # Perpetual + delivery futures
        "crypto_funding_rate": True,
        "orderbook_l2": True,
        "ticker_live": True,
    },
    DataProvider.OPENBB: {
        "equity_daily": True,
        "equity_fundamentals": True,
        "options_chain": True,
        "macro_fred": True,
        "fx": True,
        "bonds": True,
        "etf": True,
    },
    DataProvider.POLYGON: {
        "stocks_daily": True,
        "stocks_minute": True,  # 1m bars for stocks
        "options": True,
        "futures_daily": True,
        "futures_minute": True,  # 1m/5m/15m for futures! KEY FEATURE
        "fx": True,
        "indices": True,
    },
    DataProvider.FRED: {
        "macro_gdp": True,
        "macro_cpi": True,
        "macro_nfp": True,
        "macro_interest_rates": True,
        "macro_unemployment": True,
    },
    DataProvider.IBKR: {
        "futures_tick": True,  # Real-time tick for futures
        "futures_1m": True,  # Real-time 1m bars
        "equity_tick": True,
        "fx_tick": True,
        "account_data": True,
        "order_execution": True,
    },
    DataProvider.ALPHAI: {"news": True, "sentiment": True},
}


@dataclass
class DataConfig:
    """Centralized data source configuration.

    Priority: environment variable > field default > "".
    """

    # ── API Keys ────────────────────────────────────────────────────────
    polygon_key: str = ""
    """Polygon.io API key (free tier: 5 calls/min). Get at https://polygon.io"""

    fred_key: str = ""
    """FRED API key (free). Get at https://fred.stlouisfed.org/docs/api/api_key.html"""

    alphai_key: str = ""
    """AlphaAI API key (free tier: 20 req/min). Get at https://alphai.io"""

    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    """IBKR TWS/Gateway connection (paper: 7497, live: 7496)."""

    # ── Derived ─────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        """Load from environment variables."""
        self.polygon_key = os.getenv("ORACLE_DATA_POLYGON_KEY", self.polygon_key)
        self.fred_key = os.getenv("ORACLE_DATA_FRED_KEY", self.fred_key)
        self.alphai_key = os.getenv("ORACLE_DATA_ALPHAI_KEY", self.alphai_key)
        self.ibkr_host = os.getenv("ORACLE_IBKR_HOST", self.ibkr_host)
        ibkr_port = os.getenv("ORACLE_IBKR_PORT")
        if ibkr_port:
            self.ibkr_port = int(ibkr_port)

    @property
    def has_polygon(self) -> bool:
        return bool(self.polygon_key)

    @property
    def has_fred(self) -> bool:
        return bool(self.fred_key)

    @property
    def has_alphai(self) -> bool:
        return bool(self.alphai_key)
