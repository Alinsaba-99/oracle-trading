"""IBKR Client Portal REST API — dati OHLCV senza ib_insync.

Usa la REST API di IBKR Client Portal (porta 7497) che e' gia' in esecuzione.

Per prima volta: aprire https://localhost:7497 nel browser e fare login.
Dopo il login, le API REST funzionano senza token.

Usage::
    from market.ingestion.sources import IBKRRestSource
    source = IBKRRestSource()
    bars = source.fetch_historical("ES", "1m", days=5)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests


class IBKRRestSource:
    """IBKR Client Portal Web API — REST-based OHLCV fetcher.

    Porta 7497 = Client Portal Web API (gia' in esecuzione).
    NON richiede ib_insync.
    """

    BASE_URL = "https://localhost:7497/v1/api"

    def __init__(self, timeout: int = 30) -> None:
        self.session = requests.Session()
        self.session.verify = False  # self-signed cert
        self.timeout = timeout

    def _con_id_for(self, symbol: str) -> int | None:
        """Resolve contract ID for a symbol."""
        mapping = {
            "ES": 309311847,  # E-mini S&P 500 Future
            "NQ": 309311848,  # E-mini Nasdaq Future
            "GC": 309311849,  # Gold Future
            "CL": 309311850,  # Crude Oil Future
            "YM": 309311851,  # Mini Dow Futures
            "BTC": 309311852,  # Bitcoin (could differ)
        }
        return mapping.get(symbol.upper())

    def authenticate(self) -> bool:
        """Check if Client Portal is authenticated."""
        try:
            r = self.session.get(f"{self.BASE_URL}/iserver/auth/status", timeout=self.timeout)
            result: Any = r.json()
            return bool(result.get("authenticated", False))
        except Exception:
            return False

    def fetch_historical(self, symbol: str, tf: str = "1d", days: int = 30) -> list[dict[str, Any]]:
        """Fetch historical OHLCV bars via IBKR REST API.

        Args:
            symbol: Trading symbol (e.g. "ES").
            tf: Timeframe: "1m", "5m", "1h", "1d".
            days: Number of days of history.

        Returns:
            List of {timestamp, open, high, low, close, volume} dicts.
        """
        con_id = self._con_id_for(symbol)
        if con_id is None:
            print(f"  IBKR: unknown conId for {symbol}")
            return []

        # Check auth
        if not self.authenticate():
            print("  IBKR: not authenticated. Open https://localhost:7497 in browser and login.")
            return []

        # Map timeframe to IBKR bar size
        bar_size_map = {
            "1m": "1 min",
            "5m": "5 mins",
            "15m": "15 mins",
            "1h": "1 hour",
            "4h": "4 hours",
            "1d": "1 day",
        }
        bar_size = bar_size_map.get(tf, "1 day")

        # IBKR API v1 uses /iserver/marketdata/history endpoint
        params: dict[str, Any] = {
            "conid": con_id,
            "period": f"{days}d",
            "bar": bar_size,
            "outsideRth": True,
        }

        try:
            r = self.session.get(
                f"{self.BASE_URL}/iserver/marketdata/history", params=params, timeout=self.timeout
            )
            data = r.json()
            bars = data.get("data", []) if isinstance(data, dict) else data
        except Exception as e:
            print(f"  IBKR REST error: {e}")
            return []

        # Parse to standard format
        result = []
        for bar in bars:
            ts = bar.get("t") or bar.get("time") or bar.get("timestamp", 0)
            if isinstance(ts, str):
                try:
                    ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
                except ValueError:
                    ts = 0

            result.append(
                {
                    "timestamp": ts,
                    "open": float(bar.get("o", bar.get("open", 0))),
                    "high": float(bar.get("h", bar.get("high", 0))),
                    "low": float(bar.get("l", bar.get("low", 0))),
                    "close": float(bar.get("c", bar.get("close", 0))),
                    "volume": int(bar.get("v", bar.get("volume", 0))),
                }
            )

        print(f"  IBKR REST: {len(result)} {tf} bars for {symbol}")
        return result


__all__ = ["IBKRRestSource"]
