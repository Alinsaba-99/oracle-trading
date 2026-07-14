"""FX / metals / indices data ingestion via yfinance.

Provides OHLCV for the instruments prop firms trade (forex, gold, indices),
normalized to the wide schema used by :class:`BacktestDataProvider`
(``timestamp, open, high, low, close, volume``).  Downloaded data is cached
to Parquet so the orchestrator reads it transparently.

The symbol map covers the common The5ers/Lucid instruments.  yfinance daily
bars are fine for strategy prototyping; realistic intraday (M5/H1) data
arrives later from the MetaTrader5 historical bridge (Fase 5a) — the
``fetch_ohlcv`` ``interval`` parameter already supports it once that feed
is wired.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

#: Wide OHLCV schema matching :class:`BacktestDataProvider`.
OHLCV_SCHEMA: dict[str, pl.DataType] = {
    "timestamp": pl.Datetime,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
}

#: Prop-firm instrument id -> yfinance ticker.
YFINANCE_SYMBOL_MAP: dict[str, str] = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCHF": "USDCHF=X",
    "USDCAD": "USDCAD=X",
    "XAUUSD": "GC=F",  # gold futures (proxy for spot gold)
    "US30": "^DJI",  # Dow Jones
    "NAS100": "^NDX",  # Nasdaq 100
    "SPX500": "^GSPC",  # S&P 500
}


def _to_wide_ohlcv(df_pd: Any) -> pl.DataFrame:
    """Flatten a yfinance (MultiIndex) DataFrame to wide OHLCV polars."""
    import pandas as pd

    if isinstance(df_pd.columns, pd.MultiIndex):
        df_pd = df_pd.copy()
        df_pd.columns = [c[0] if isinstance(c, tuple) else c for c in df_pd.columns]

    df_pd = df_pd.reset_index()
    df_pd = df_pd.rename(columns={c: str(c).lower() for c in df_pd.columns})
    # Resolve the timestamp column from whatever reset_index named it
    # (yfinance uses "Date"/"Datetime"; an unnamed index becomes "index").
    if "timestamp" not in df_pd.columns:
        for cand in ("date", "datetime", "index", "level_0"):
            if cand in df_pd.columns:
                df_pd = df_pd.rename(columns={cand: "timestamp"})
                break
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df_pd.columns:
            df_pd[col] = 0.0
    df_pd = df_pd[list(OHLCV_SCHEMA.keys())]
    df_pd = df_pd.dropna(subset=["timestamp"])
    if df_pd.empty:
        return pl.DataFrame(schema=OHLCV_SCHEMA)
    return pl.from_pandas(df_pd)


def fetch_ohlcv(
    instrument_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    period: str | None = None,
    interval: str = "1d",
) -> pl.DataFrame:
    """Fetch OHLCV for a prop-firm instrument via yfinance.

    Either *period* (e.g. ``"2y"``) or *start*/*end* must be supplied.
    Unknown instrument ids are passed through to yfinance verbatim.
    """
    import yfinance as yf

    ticker = YFINANCE_SYMBOL_MAP.get(instrument_id.upper(), instrument_id)
    if period:
        df_pd = yf.download(ticker, period=period, interval=interval, progress=False)
    else:
        df_pd = yf.download(ticker, start=start, end=end, interval=interval, progress=False)
    if df_pd is None or len(df_pd) == 0:
        return pl.DataFrame(schema=OHLCV_SCHEMA)
    return _to_wide_ohlcv(df_pd)


def download_fx(
    instruments: list[str],
    ohlcv_path: Path | str = Path("data/ohlcv"),
    start: datetime | None = None,
    end: datetime | None = None,
    period: str | None = "2y",
    interval: str = "1d",
) -> dict[str, int]:
    """Download and cache OHLCV Parquet for each instrument.

    Returns a mapping ``{instrument_id: row_count}``.
    """
    path = Path(ohlcv_path)
    path.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for inst in instruments:
        df = fetch_ohlcv(inst, start=start, end=end, period=period, interval=interval)
        if df.is_empty():
            counts[inst] = 0
            continue
        df.write_parquet(str(path / f"{inst.upper()}.parquet"))
        counts[inst] = df.height
    return counts
