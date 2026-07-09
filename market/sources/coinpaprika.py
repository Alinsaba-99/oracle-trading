"""CoinPaprika source — crypto REST backup data.

Uses the public CoinPaprika REST API at ``https://api.coinpaprika.com/v1``.
No API key required.  Provides ticker snapshots and historical OHLCV for
7000+ cryptocurrencies.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from market.sources.base import BaseSource

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coinpaprika.com/v1"
DEFAULT_TIMEOUT = 30.0


class CoinPaprikaSource(BaseSource):
    """REST-based crypto data via the CoinPaprika API.

    Parameters
    ----------
    instrument_ids:
        CoinPaprika coin IDs, e.g. ``["btc-bitcoin", "eth-ethereum"]``.
    """

    def __init__(self, instrument_ids: list[str] | None = None) -> None:
        super().__init__(name="coinpaprika", instrument_ids=instrument_ids)
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Create the HTTP client session."""
        self._client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
        logger.info("CoinPaprika source ready")

    async def disconnect(self) -> None:
        """Close the HTTP client session."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def subscribe(self, instrument_ids: list[str]) -> None:
        """CoinPaprika is REST-based — subscription is a no-op."""
        self.instrument_ids.extend(instrument_ids)

    async def unsubscribe(self, instrument_ids: list[str]) -> None:
        """No-op for REST source."""
        self.instrument_ids = [i for i in self.instrument_ids if i not in instrument_ids]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_ticker(self, coin_id: str) -> dict[str, Any]:
        """Fetch current ticker for a coin.

        Parameters
        ----------
        coin_id:
            CoinPaprika coin ID, e.g. ``"btc-bitcoin"``.

        Returns
        -------
        dict
            Normalized ticker data with keys ``source``, ``instrument_id``,
            ``price``, ``volume_24h``, ``market_cap``, ``timestamp``.

        Raises
        ------
        ValueError
            When the coin ID is not found.
        httpx.HTTPError
            On transport or API errors.
        """
        if self._client is None:
            msg = "Not connected — call connect() first"
            raise RuntimeError(msg)

        resp = await self._client.get(f"{BASE_URL}/tickers/{coin_id}")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        return {
            "source": "coinpaprika",
            "instrument_id": coin_id,
            "name": data.get("name", ""),
            "symbol": data.get("symbol", ""),
            "price": float(data.get("quotes", {}).get("USD", {}).get("price", 0)),
            "volume_24h": float(data.get("quotes", {}).get("USD", {}).get("volume_24h", 0)),
            "market_cap": float(data.get("quotes", {}).get("USD", {}).get("market_cap", 0)),
            "circulating_supply": float(data.get("circulating_supply", 0)),
            "total_supply": float(data.get("total_supply", 0)),
            "max_supply": data.get("max_supply"),
            "timestamp": data.get("last_updated", ""),
        }

    async def get_historical_ohlcv(
        self, coin_id: str, interval: str = "1d", limit: int = 365
    ) -> list[dict[str, Any]]:
        """Fetch historical OHLCV data for a coin.

        Parameters
        ----------
        coin_id:
            CoinPaprika coin ID, e.g. ``"btc-bitcoin"``.
        interval:
            ``"5m"``, ``"10m"``, ``"15m"``, ``"30m"``, ``"1h"``,
            ``"6h"``, ``"12h"``, ``"1d"``.
        limit:
            Number of results (max 2000 for ``1d``, fewer for smaller
            intervals).

        Returns
        -------
        list[dict[str, Any]]
            List of normalized OHLCV dicts.

        Raises
        ------
        ValueError
            When the coin ID is not found.
        """
        if self._client is None:
            msg = "Not connected — call connect() first"
            raise RuntimeError(msg)

        resp = await self._client.get(
            f"{BASE_URL}/coins/{coin_id}/ohlcv/historical",
            params={"interval": interval, "limit": limit},
        )
        resp.raise_for_status()
        raw_list: list[dict[str, Any]] = resp.json()

        result = []
        for entry in raw_list:
            result.append(
                {
                    "source": "coinpaprika",
                    "instrument_id": coin_id,
                    "timestamp": entry.get("time_open", ""),
                    "open": float(entry.get("open", 0)),
                    "high": float(entry.get("high", 0)),
                    "low": float(entry.get("low", 0)),
                    "close": float(entry.get("close", 0)),
                    "volume": float(entry.get("volume", 0)),
                    "market_cap": float(entry.get("market_cap", 0)),
                }
            )
        return result
