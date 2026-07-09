"""yfinance source — US equities EOD historical data.

Uses the ``yfinance`` library (free, no API key) to fetch historical
OHLCV data for US equities and ETFs.  Returns data as Polars DataFrames.
"""

from __future__ import annotations

import asyncio
import functools
import logging

import polars as pl
import yfinance as yf

from market.sources.base import BaseSource

logger = logging.getLogger(__name__)

COLUMN_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "stock_splits",
}


class yfinanceSource(BaseSource):  # noqa: N801
    """Historical OHLCV data via the yfinance library.

    Parameters
    ----------
    instrument_ids:
        Ticker symbols, e.g. ``["AAPL", "MSFT"]``.
    """

    def __init__(self, instrument_ids: list[str] | None = None) -> None:
        super().__init__(name="yfinance", instrument_ids=instrument_ids)

    async def connect(self) -> None:
        """yfinance is stateless — no persistent connection needed."""
        logger.info("yfinance source ready (stateless)")

    async def disconnect(self) -> None:
        """Nothing to clean up."""

    async def subscribe(self, instrument_ids: list[str]) -> None:
        """yfinance does not support streaming subscriptions — no-op."""
        self.instrument_ids.extend(instrument_ids)

    async def unsubscribe(self, instrument_ids: list[str]) -> None:
        """No-op for stateless source."""
        self.instrument_ids = [i for i in self.instrument_ids if i not in instrument_ids]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_history(
        self, instrument_id: str, period: str = "1mo", interval: str = "1d"
    ) -> pl.DataFrame:
        """Fetch historical OHLCV data for a single instrument.

        Parameters
        ----------
        instrument_id:
            Ticker symbol, e.g. ``"AAPL"``.
        period:
            Valid periods: ``1d``, ``5d``, ``1mo``, ``3mo``, ``6mo``,
            ``1y``, ``2y``, ``5y``, ``10y``, ``ytd``, ``max``.
        interval:
            Valid intervals: ``1m``, ``2m``, ``5m``, ``15m``, ``30m``,
            ``60m``, ``90m``, ``1h``, ``1d``, ``5d``, ``1wk``, ``1mo``,
            ``3mo``.

        Returns
        -------
        pl.DataFrame
            Polars DataFrame with columns ``timestamp``, ``open``,
            ``high``, ``low``, ``close``, ``volume``, ``instrument_id``.

        Raises
        ------
        ValueError
            When the ticker symbol is not found or returns no data.
        """
        ticker = yf.Ticker(instrument_id)

        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(
            None, functools.partial(ticker.history, period=period, interval=interval)
        )

        if df is None or df.empty:
            msg = f"No data for {instrument_id} (period={period}, interval={interval})"
            raise ValueError(msg)

        # Convert pandas DataFrame to Polars with standardised columns
        pl_df = pl.from_pandas(df.reset_index())
        pl_df = pl_df.rename({c: COLUMN_MAP.get(c, c) for c in pl_df.columns})
        pl_df = pl_df.with_columns(
            pl.lit(instrument_id).alias("instrument_id"), pl.lit("yfinance").alias("source")
        )
        return pl_df

    async def fetch_multi(
        self, instrument_ids: list[str] | None = None, period: str = "1mo", interval: str = "1d"
    ) -> dict[str, pl.DataFrame]:
        """Fetch history for multiple instruments concurrently.

        Returns a dict mapping ``instrument_id -> DataFrame``.
        """
        ids = instrument_ids or self.instrument_ids
        results: dict[str, pl.DataFrame] = {}
        for sid in ids:
            try:
                results[sid] = await self.fetch_history(sid, period=period, interval=interval)
            except ValueError:
                logger.warning("No data for %s, skipping", sid)
        return results
