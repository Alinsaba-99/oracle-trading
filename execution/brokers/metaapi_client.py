"""MetaApi cloud client — native-Linux MT5 access (data + orders).

This is the Linux-friendly backend for :class:`MetaTraderBroker` /
``MT5Client``.  Unlike the official ``MetaTrader5`` package (Windows-only),
``metaapi-cloud-sdk`` runs in native Python via MetaApi's cloud proxy.

NOTE: method names follow the canonical MetaApi SDK (v29.x).  Verify on
first connect — minor signature drift between SDK versions is possible.
Requires a MetaApi account: a token + a provisioned account id (the MT5
demo account is added at https://metaapi.cloud).  See ``.env.example``.

The immediate use case is **historical intraday bars** (M5) which unblock
the strategy leap past the ~67% daily-bar wall (Fase 6).  Live order
methods are included but unused until a strategy validates at 85%+.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import polars as pl

from analytics.backtest.fx_data import OHLCV_SCHEMA


class MetaApiClient:
    """Async wrapper over the MetaApi cloud SDK for one MT5 account."""

    def __init__(self, token: str, account_id: str) -> None:
        if not token or not account_id:
            raise ValueError("MetaApi token and account_id are required")
        self._token = token
        self._account_id = account_id
        self._api: Any = None
        self._account: Any = None
        self._connection: Any = None

    async def connect(self) -> None:
        """Deploy + connect the account's RPC connection."""
        from metaapi_cloud_sdk import MetaApi

        self._api = MetaApi(token=self._token)
        acct_api = self._api.metatrader_account_api
        self._account = await acct_api.get_account(self._account_id)
        await self._account.deploy()
        await self._account.wait_deployed()
        self._connection = self._account.get_rpc_connection()
        await self._connection.connect()
        await self._connection.wait_connected()

    async def account_info(self) -> dict[Any, Any]:
        """Return {balance, equity, margin, currency, leverage, server, ...}."""
        self._require()
        return await self._connection.get_account_information()  # type: ignore[no-any-return]

    async def positions(self) -> list[dict[Any, Any]]:
        """Return open positions as a list of dicts."""
        self._require()
        return await self._connection.get_positions()  # type: ignore[no-any-return]

    async def historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pl.DataFrame:
        """Fetch historical candles and return wide OHLCV (matches fx_data schema).

        Args:
            symbol: Broker symbol, e.g. ``"EURUSD"`` (use the SymbolMapper for suffixes).
            timeframe: MetaApi timeframe code — ``"1m"``, ``"5m"``, ``"15m"``,
                ``"30m"``, ``"1h"``, ``"4h"``, ``"1d"``.
            start: Inclusive start (UTC).
            end: Inclusive end (UTC).
        """
        self._require()
        candles = await self._connection.get_historical_candles(
            symbol, timeframe, start, end
        )
        return _candles_to_ohlcv(candles)

    async def market_buy(
        self,
        symbol: str,
        volume: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[Any, Any]:
        """Place a market buy. Returns the broker response dict."""
        self._require()
        result: dict[Any, Any] = await self._connection.create_market_buy_order(
            symbol, volume, stop_loss or 0.0, take_profit or 0.0
        )
        return result

    async def market_sell(
        self,
        symbol: str,
        volume: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[Any, Any]:
        """Place a market sell. Returns the broker response dict."""
        self._require()
        result: dict[Any, Any] = await self._connection.create_market_sell_order(
            symbol, volume, stop_loss or 0.0, take_profit or 0.0
        )
        return result

    async def close(self) -> None:
        """Disconnect cleanly."""
        if self._connection is not None:
            await self._connection.close()
        self._connection = None

    def _require(self) -> None:
        if self._connection is None:
            raise RuntimeError("MetaApiClient not connected — call connect() first")


def _candles_to_ohlcv(candles: list[Any]) -> pl.DataFrame:
    """Convert MetaApi candle objects/dicts to wide OHLCV polars."""
    if not candles:
        return pl.DataFrame(schema=OHLCV_SCHEMA)
    rows = []
    for raw in candles:
        if isinstance(raw, dict):
            c = raw
        elif hasattr(raw, "as_dict"):
            c = raw.as_dict()
        else:
            c = {
                k: getattr(raw, k)
                for k in ("time", "open", "high", "low", "close", "volume")
            }
        ts_ms = c.get("time")
        ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC) if ts_ms else None
        rows.append(
            {
                "timestamp": ts,
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c.get("volume", 0.0) or 0.0),
            }
        )
    return pl.DataFrame(rows, schema=OHLCV_SCHEMA).sort("timestamp")
