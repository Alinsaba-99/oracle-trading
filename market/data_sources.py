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

from pathlib import Path

import pandas as pd
import structlog

from market.data_config import DataConfig

logger = structlog.get_logger("oracle.data.sources")


class DataFetcher:
    """Unified market data fetcher with multiple backends."""

    DATA_DIR = Path("data/ohlcv")

    def __init__(self, config: DataConfig | None = None) -> None:
        self.config = config or DataConfig()
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── yfinance ────────────────────────────────────────────────────────

    def yfinance_futures(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
        *,
        allow_overwrite: bool = False,
    ) -> pd.DataFrame:
        """Fetch futures data via yfinance.

        Args:
            symbol: Root symbol (e.g. ES, NQ, GC, CL).
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max).
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo).
            allow_overwrite: if False (default), refuse to overwrite an existing
                pinned dataset. Set to True only when intentionally refreshing.

        Returns:
            DataFrame with OHLCV data.
        """
        import yfinance as yf

        ticker = f"{symbol}=F"
        path = self.DATA_DIR / f"{symbol}_{interval}.parquet"
        if path.exists() and not allow_overwrite:
            import hashlib

            existing_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            pinned_paths = list(self.DATA_DIR.parent.glob(f"pinned/{symbol}_{interval}_*.parquet"))
            for pinned in pinned_paths:
                pinned_hash = hashlib.sha256(pinned.read_bytes()).hexdigest()
                if pinned_hash == existing_hash:
                    logger.info(
                        "STALE_DATASET_PINNED",
                        path=str(path),
                        sha256=existing_hash,
                        pinned=str(pinned),
                    )
                    return pd.read_parquet(path)

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
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
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
        self, symbol: str, source: str = "auto", period: str = "6mo", interval: str = "1d"
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
            "yfinance": lambda: (
                self.yfinance_futures(symbol, period, interval)
                if symbol.upper() in ("ES", "NQ", "GC", "CL", "6E", "ZS", "ZM", "ZW")
                else self.yfinance_equity(symbol, period, interval)
            ),
            "ccxt": lambda: self.ccxt_ohlcv("binance", symbol),
            "openbb": lambda: self.openbb_equity(symbol),
        }

        fetcher = sources.get(source)
        if fetcher is None:
            raise ValueError(f"Unknown source: {source}. Use: {', '.join(sources)}")

        return fetcher()

    # ── Polygon.io (intraday futures/stocks) ──────────────────────────

    def polygon_futures_minute(
        self, symbol: str, from_date: str, to_date: str, timespan: str = "minute"
    ) -> pd.DataFrame:
        """Fetch intraday futures data via Polygon.io (requires API key).

        Fills GAP: 1m/5m/15m intraday bars for ES, NQ, GC, CL futures.

        Args:
            symbol: Contract code (e.g. ``ES``, ``NQ``).
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            timespan: Bar size (``minute``, ``hour``, ``day``).

        Returns:
            DataFrame with OHLCV data.
        """
        if not self.config.has_polygon:
            logger.warning("Polygon API key not configured — skipping")
            return pd.DataFrame()

        import httpx

        # Map root symbol to Polygon futures ticker
        ticker_map = {"ES": "ES", "NQ": "NQ", "GC": "GC", "CL": "CL"}
        poly_ticker = f"{ticker_map.get(symbol, symbol)}*5"  # E-mini format

        url = (
            f"https://api.polygon.io/v2/aggs/ticker/{poly_ticker}/range/"
            f"{timespan}/1/{from_date}/{to_date}"
        )
        resp = httpx.get(url, params={"apiKey": self.config.polygon_key, "limit": 50000})
        if resp.status_code != 200:
            logger.warning(f"Polygon API error: {resp.status_code}")
            return pd.DataFrame()

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df["timestamp"] = pd.to_datetime(df["t"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df.rename(
            columns={
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
                "n": "trades",
            },
            inplace=True,
        )

        path = self.DATA_DIR / f"{symbol}_{timespan}.parquet"
        df.to_parquet(path)
        logger.info(f"Polygon {symbol} {timespan}: {len(df)} bars")
        return df

    # ── CCXT Futures (crypto perpetuals) ─────────────────────────────

    def ccxt_futures_ohlcv(
        self,
        exchange_id: str = "binance",
        symbol: str = "BTC/USDT:USDT",
        timeframe: str = "1h",
        limit: int = 500,
    ) -> pd.DataFrame:
        """Fetch crypto perpetual futures OHLCV via CCXT.

        Fills GAP: crypto perpetual futures data with funding rates.
        Uses the ``:USDT`` or ``:USD`` suffix for linear/inverse futures.

        Args:
            exchange_id: Exchange (binance, bybit, okx).
            symbol: Perpetual pair with settle currency (e.g. ``BTC/USDT:USDT``).
            timeframe: 1m, 5m, 15m, 1h, 4h, 1d.
            limit: Number of candles.

        Returns:
            DataFrame with OHLCV + optional funding rate.
        """
        import ccxt

        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({"options": {"defaultType": "future"}})

        logger.info("Fetching CCXT futures", exchange=exchange_id, symbol=symbol)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # Try to fetch funding rate
        try:
            funding = exchange.fetch_funding_rate(symbol)
            if funding and "fundingRate" in funding:
                df["funding_rate"] = float(funding["fundingRate"])
        except Exception:
            pass

        safe_sym = symbol.replace("/", "_").replace(":", "_")
        path = self.DATA_DIR / f"{safe_sym}_{timeframe}.parquet"
        df.to_parquet(path)
        logger.info(f"CCXT futures {symbol} {timeframe}: {len(df)} bars")
        return df

    # ── FRED macro data ──────────────────────────────────────────────

    def fred_series(
        self, series_id: str = "GDP", start: str = "2020-01-01", end: str | None = None
    ) -> pd.DataFrame:
        """Fetch macro-economic data from FRED (Federal Reserve).

        Fills GAP: macro indicators (GDP, CPI, NFP, interest rates, unemployment).

        Free tier: no API key required for basic CSV access.

        Args:
            series_id: FRED series ID (GDP, CPIAUCSL, PAYEMS, UNRATE, FEDFUNDS).
            start: Start date (YYYY-MM-DD).
            end: End date (YYYY-MM-DD, defaults to today).

        Returns:
            DataFrame with date and value columns.
        """
        import httpx

        params = {"id": series_id, "cosd": start}
        if end:
            params["coed"] = end
        if self.config.has_fred:
            params["api_key"] = self.config.fred_key

        resp = httpx.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv", params=params, timeout=15
        )
        if resp.status_code != 200:
            logger.warning(f"FRED error: {resp.status_code} for {series_id}")
            return pd.DataFrame()

        from io import StringIO

        df = pd.read_csv(StringIO(resp.text), parse_dates=["observation_date"])
        df.set_index("observation_date", inplace=True)
        df.columns = [series_id]

        path = self.DATA_DIR / f"fred_{series_id}.parquet"
        df.to_parquet(path)
        logger.info(f"FRED {series_id}: {len(df)} observations")
        return df
