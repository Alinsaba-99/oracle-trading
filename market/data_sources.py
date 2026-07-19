"""Unified data source interface — fetch market data from multiple providers.

Supports:
- yfinance: futures, equities, crypto daily/intraday (free, no key)
- ccxt: crypto spot/futures (free, no key for public endpoints)
- OpenBB: equities, ETFs, futures, macro, FX (free, no key for basic)

Usage::

    from market.data_sources import DataFetcher
    
    fetcher = DataFetcher()
    
    # ES futures daily via yfinance
    df = fetcher.yfinance_futures("ES", period="6mo")
    
    # BTC/USDT 1h via ccxt
    df = fetcher.ccxt_ohlcv("binance", "BTC/USDT", "1h", limit=500)
    
    # SPY daily via OpenBB
    df = fetcher.openbb_equity("SPY")
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger("oracle.data.sources")


class DataFetcher:
    """Unified market data fetcher with multiple backends."""

    DATA_DIR = Path("data/ohlcv")

    def __init__(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── yfinance ────────────────────────────────────────────────────────

    def yfinance_futures(
        self, symbol: str, period: str = "6mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetch futures data via yfinance.

        Args:
            symbol: Root symbol (e.g. ES, NQ, GC, CL).
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max).
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo).

        Returns:
            DataFrame with OHLCV data.
        """
        import yfinance as yf

        ticker = f"{symbol}=F"
        logger.info("Fetching yfinance futures", ticker=ticker, period=period)
        df = yf.download(ticker, period=period, interval=interval)

        # Flatten MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        # Cache
        path = self.DATA_DIR / f"{symbol}_{interval}.parquet"
        df.to_parquet(path)
        logger.info("Cached to", path=str(path))

        return df

    def yfinance_equity(
        self, symbol: str, period: str = "6mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetch equity data via yfinance."""
        import yfinance as yf

        logger.info("Fetching yfinance equity", ticker=symbol)
        df = yf.download(symbol, period=period, interval=interval)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]

        path = self.DATA_DIR / f"{symbol}_{interval}.parquet"
        df.to_parquet(path)
        return df

    # ── CCXT (crypto) ───────────────────────────────────────────────────

    def ccxt_ohlcv(
        self,
        exchange_id: str = "binance",
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        limit: int = 500,
    ) -> pd.DataFrame:
        """Fetch OHLCV data via CCXT.

        Args:
            exchange_id: Exchange identifier (binance, bybit, okx, kraken).
            symbol: Trading pair (BTC/USDT, ETH/USDT).
            timeframe: 1m, 5m, 15m, 1h, 4h, 1d.
            limit: Number of candles.

        Returns:
            DataFrame with timestamp, open, high, low, close, volume.
        """
        import ccxt

        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class()
        logger.info("Fetching CCXT", exchange=exchange_id, symbol=symbol)

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        path = self.DATA_DIR / f"{symbol.replace('/', '_')}_{timeframe}.parquet"
        df.to_parquet(path)
        return df

    # ── OpenBB ──────────────────────────────────────────────────────────

    def openbb_equity(
        self, symbol: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """Fetch equity data via OpenBB."""
        try:
            from openbb import obb
        except ImportError:
            logger.warning("OpenBB not installed — run ``uv pip install openbb``")
            return pd.DataFrame()

        logger.info("Fetching OpenBB equity", symbol=symbol)
        df = obb.equity.price.historical(symbol, start_date=start_date, end_date=end_date).to_df()

        path = self.DATA_DIR / f"obb_{symbol}_daily.parquet"
        df.to_parquet(path)
        return df

    # ── Unified fetch ───────────────────────────────────────────────────

    def fetch(
        self,
        symbol: str,
        source: str = "auto",
        period: str = "6mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Unified fetch — auto-selects the best source for the symbol.

        Args:
            symbol: Ticker symbol (ES, NQ, BTC/USDT, AAPL).
            source: Force a specific source (yfinance, ccxt, openbb, auto).
            period: Data period.
            interval: Data interval.

        Returns:
            DataFrame with OHLCV data.
        """
        # Auto-detect source
        if source == "auto":
            if "/" in symbol:
                return self.ccxt_ohlcv("binance", symbol)
            elif symbol.upper() in ("ES", "NQ", "GC", "CL", "6E", "ZS", "ZM", "ZW"):
                return self.yfinance_futures(symbol, period, interval)
            else:
                return self.yfinance_equity(symbol, period, interval)

        sources = {
            "yfinance": lambda: self.yfinance_futures(symbol, period, interval)
            if symbol.upper()
            in ("ES", "NQ", "GC", "CL", "6E", "ZS", "ZM", "ZW")
            else self.yfinance_equity(symbol, period, interval),
            "ccxt": lambda: self.ccxt_ohlcv("binance", symbol),
            "openbb": lambda: self.openbb_equity(symbol),
        }

        fetcher = sources.get(source)
        if fetcher is None:
            raise ValueError(f"Unknown source: {source}. Use: {', '.join(sources)}")

        return fetcher()
