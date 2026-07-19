"""Unified OHLCV providers + cache for the multi-asset/multi-TF backbone (R0.2/R0.4/R0.5).

Three backends, one cache layout (``data/ohlcv/{instrument}/{timeframe}.parquet``):
  - yfinance : FX / indices / futures / crypto daily proxies + 15m/1h (no creds)
  - ccxt     : crypto spot M15..1d, reliable intraday (no creds)
  - metaapi  : MT5 CFD intraday (EURUSD/XAUUSD/US30 ...) — needs METAAPI_TOKEN +
               METAAPI_ACCOUNT_ID in .env (R0.3, wired when creds exist)

Provider dispatch per instrument (see :func:`_dispatch`): crypto -> ccxt,
else yfinance if a yf ticker exists, else metaapi. The strategy layer reads
``DataRegistry.get_ohlcv(...)`` -> pl.DataFrame (wide OHLCV_SCHEMA), identical
to what ``fx_data`` produces, so signals/eval consume it unchanged.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from analytics.backtest.fx_data import OHLCV_SCHEMA, _to_wide_ohlcv
from analytics.backtest.instruments import Instrument, InstrumentRegistry, default_registry

SUPPORTED_TIMEFRAMES = ("15m", "1h", "4h", "1d")

# interval codes per backend. yfinance has no native 4h -> resample from 60m.
_YF_INTERVAL = {"15m": "15m", "1h": "60m", "4h": "60m", "1d": "1d"}
_YF_PERIOD = {"15m": "60d", "1h": "730d", "4h": "730d", "1d": "2y"}
_CCXT_INTERVAL = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
_METAAPI_TF = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}


def _resample(df: pl.DataFrame, rule: str) -> pl.DataFrame:
    """Resample a 1h OHLCV frame to a coarser rule (e.g. '4h')."""
    if df.is_empty():
        return df
    return (
        df.sort("timestamp")
        .group_by_dynamic("timestamp", every=rule)
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
        )
        .sort("timestamp")
    )


def fetch_yfinance(inst: Instrument, tf: str, *, period: str | None = None) -> pl.DataFrame:
    """Fetch OHLCV via yfinance for an instrument's ``yf`` ticker."""
    import yfinance as yf

    if not inst.yf:
        return pl.DataFrame(schema=OHLCV_SCHEMA)
    yf_int = _YF_INTERVAL[tf]
    period = period or _YF_PERIOD[tf]
    df_pd = yf.download(inst.yf, period=period, interval=yf_int, progress=False, auto_adjust=False)
    if df_pd is None or len(df_pd) == 0:
        return pl.DataFrame(schema=OHLCV_SCHEMA)
    out = _to_wide_ohlcv(df_pd)
    if tf == "4h" and not out.is_empty():
        out = _resample(out, "4h")
    return out


def fetch_ccxt(
    inst: Instrument,
    tf: str,
    *,
    exchange_id: str = "binance",
    limit: int = 1000,
    since: int | None = None,
    max_requests: int = 5,
) -> pl.DataFrame:
    """Fetch OHLCV via ccxt for an instrument's ``ccxt`` symbol (crypto).

    Supports pagination via the *since* timestamp (epoch ms).  When the
    exchange returns a full page (== limit rows), the method continues
    fetching until fewer than *limit* rows are returned or *max_requests*
    is reached.
    """
    import ccxt

    if not inst.ccxt:
        return pl.DataFrame(schema=OHLCV_SCHEMA)
    exchange = getattr(ccxt, exchange_id)()

    all_bars: list[list[float]] = []
    request_count = 0
    current_since = since

    while request_count < max_requests:
        ohlcv = exchange.fetch_ohlcv(
            inst.ccxt, timeframe=_CCXT_INTERVAL[tf], since=current_since, limit=limit
        )
        if not ohlcv:
            break
        all_bars.extend(ohlcv)
        request_count += 1
        if len(ohlcv) < limit:
            break  # last page
        # Advance *since* to the timestamp of the last bar for next page
        current_since = int(ohlcv[-1][0]) + 1

    if not all_bars:
        return pl.DataFrame(schema=OHLCV_SCHEMA)

    rows = [
        {
            "timestamp": datetime.fromtimestamp(bar[0] / 1000.0, tz=UTC),
            "open": float(bar[1]),
            "high": float(bar[2]),
            "low": float(bar[3]),
            "close": float(bar[4]),
            "volume": float(bar[5] or 0.0),
        }
        for bar in all_bars
    ]
    return pl.DataFrame(rows, schema=OHLCV_SCHEMA).unique("timestamp").sort("timestamp")


async def _fetch_metaapi_async(
    inst: Instrument, tf: str, *, start: datetime, end: datetime
) -> pl.DataFrame:
    """Fetch OHLCV via MetaApi (R0.3). Requires METAAPI_TOKEN + METAAPI_ACCOUNT_ID."""
    from execution.brokers.metaapi_client import MetaApiClient

    token = os.environ.get("METAAPI_TOKEN")
    account_id = os.environ.get("METAAPI_ACCOUNT_ID")
    if not token or not account_id:
        raise RuntimeError(
            "MetaApi provider needs METAAPI_TOKEN and METAAPI_ACCOUNT_ID in env "
            f"(instrument {inst.id} has no yfinance/ccxt source)."
        )
    if not inst.metaapi:
        return pl.DataFrame(schema=OHLCV_SCHEMA)
    client = MetaApiClient(token=token, account_id=account_id)
    try:
        await client.connect()
        return await client.historical_candles(inst.metaapi, _METAAPI_TF[tf], start, end)
    finally:
        await client.close()


def fetch_metaapi(inst: Instrument, tf: str, *, start: datetime, end: datetime) -> pl.DataFrame:
    """Sync wrapper around the async MetaApi provider."""
    return asyncio.run(_fetch_metaapi_async(inst, tf, start=start, end=end))


def _dispatch(
    inst: Instrument, tf: str, *, period: str | None, start: datetime | None, end: datetime | None
) -> pl.DataFrame:
    """Pick a provider for the instrument and fetch (no caching).

    When *start* is provided for ccxt, the method paginates from that
    timestamp backward.  Otherwise it uses the default ``limit=1000``.
    """
    if inst.ccxt:  # crypto: ccxt is the reliable intraday + daily source
        since: int | None = None
        if start is not None:
            since = int(start.timestamp() * 1000)
        return fetch_ccxt(inst, tf, since=since)
    if inst.yf:
        return fetch_yfinance(inst, tf, period=period)
    if inst.metaapi:
        end = end or datetime.now(UTC)
        start = start or end - timedelta(days=730)
        return fetch_metaapi(inst, tf, start=start, end=end)
    return pl.DataFrame(schema=OHLCV_SCHEMA)


class DataRegistry:
    """Cached multi-asset/multi-TF OHLCV access (R0.5).

    ``get_ohlcv`` returns a cached Parquet frame or fetches+persists on miss.
    """

    def __init__(
        self, root: Path | str = Path("data/ohlcv"), registry: InstrumentRegistry | None = None
    ) -> None:
        self.root = Path(root)
        self.registry = registry or default_registry()

    def _cache_path(self, instrument_id: str, tf: str) -> Path:
        return self.root / instrument_id.upper() / f"{tf}.parquet"

    def get_ohlcv(
        self,
        instrument_id: str,
        tf: str = "1d",
        *,
        period: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        force: bool = False,
    ) -> pl.DataFrame:
        """Return OHLCV for ``instrument_id`` at ``tf`` (cached on first fetch)."""
        if tf not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe {tf!r}; choose from {SUPPORTED_TIMEFRAMES}")
        inst = self.registry.get(instrument_id)
        cache = self._cache_path(instrument_id, tf)
        if cache.exists() and not force:
            return pl.read_parquet(cache)
        df = _dispatch(inst, tf, period=period, start=start, end=end)
        if df.is_empty():
            return df
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(cache)
        return df

    def warm(
        self,
        instrument_ids: list[str] | None = None,
        tfs: tuple[str, ...] = SUPPORTED_TIMEFRAMES,
        period: str | None = None,
    ) -> dict[tuple[str, str], int]:
        """Pre-fetch+cache many instruments/TFs. Returns {(inst, tf): row_count}."""
        ids = instrument_ids or [i.id for i in self.registry.all()]
        counts: dict[tuple[str, str], int] = {}
        for inst_id in ids:
            for tf in tfs:
                try:
                    df = self.get_ohlcv(inst_id, tf, period=period, force=True)
                    counts[(inst_id, tf)] = df.height
                except Exception as exc:
                    counts[(inst_id, tf)] = -1
                    print(f"[warm] {inst_id}/{tf} failed: {exc}")
        return counts
