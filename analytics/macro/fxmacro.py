"""FXMacroData connector — central bank rates and inflation data.

The real FXMacroData service has paid tiers. This connector provides a
mock-based implementation that returns sensible synthetic data when no
API key is configured, making it usable in development and testing.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import polars as pl

from analytics.common.errors import MacroError

logger = logging.getLogger(__name__)

# Default mock central bank rates (USD-centric)
_DEFAULT_RATES: dict[str, float] = {
    "USD": 5.50,  # US Federal Reserve
    "EUR": 4.50,  # European Central Bank
    "GBP": 5.25,  # Bank of England
    "JPY": 0.25,  # Bank of Japan
    "CHF": 1.75,  # Swiss National Bank
    "AUD": 4.35,  # Reserve Bank of Australia
    "CAD": 5.00,  # Bank of Canada
    "NZD": 5.50,  # Reserve Bank of New Zealand
    "SEK": 4.00,  # Sveriges Riksbank
    "NOK": 4.50,  # Norges Bank
}

_DEFAULT_INFLATION: dict[str, list[dict[str, Any]]] = {
    "US": [
        {"date": "2023-01-01", "rate": 6.4},
        {"date": "2023-04-01", "rate": 4.9},
        {"date": "2023-07-01", "rate": 3.2},
        {"date": "2023-10-01", "rate": 3.1},
        {"date": "2024-01-01", "rate": 3.1},
        {"date": "2024-04-01", "rate": 3.4},
        {"date": "2024-07-01", "rate": 2.9},
        {"date": "2024-10-01", "rate": 2.6},
        {"date": "2025-01-01", "rate": 2.8},
    ],
    "GB": [
        {"date": "2023-01-01", "rate": 10.1},
        {"date": "2023-04-01", "rate": 8.7},
        {"date": "2023-07-01", "rate": 6.8},
        {"date": "2023-10-01", "rate": 4.6},
        {"date": "2024-01-01", "rate": 4.0},
        {"date": "2024-04-01", "rate": 2.3},
        {"date": "2024-07-01", "rate": 2.2},
        {"date": "2024-10-01", "rate": 2.3},
    ],
    "JP": [
        {"date": "2023-01-01", "rate": 4.3},
        {"date": "2023-04-01", "rate": 3.2},
        {"date": "2023-07-01", "rate": 3.3},
        {"date": "2023-10-01", "rate": 2.8},
        {"date": "2024-01-01", "rate": 2.2},
        {"date": "2024-04-01", "rate": 2.5},
        {"date": "2024-07-01", "rate": 2.8},
        {"date": "2024-10-01", "rate": 2.6},
    ],
    "DE": [
        {"date": "2023-01-01", "rate": 8.7},
        {"date": "2023-04-01", "rate": 7.2},
        {"date": "2023-07-01", "rate": 6.2},
        {"date": "2023-10-01", "rate": 3.8},
        {"date": "2024-01-01", "rate": 2.9},
        {"date": "2024-04-01", "rate": 2.2},
        {"date": "2024-07-01", "rate": 2.3},
        {"date": "2024-10-01", "rate": 2.0},
    ],
}

_SUPPORTED_COUNTRIES: set[str] = set(_DEFAULT_INFLATION.keys())


class FXMacroDataClient:
    """FXMacroData connector for central bank rates and inflation.

    Operates in **mock mode** when ``FXMACRO_API_KEY`` is not set, returning
    synthetic default data suitable for development and testing.

    In production, set ``FXMACRO_API_KEY`` and ``FXMACRO_BASE_URL`` to point
    at your FXMacroData subscription endpoint.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("FXMACRO_API_KEY", "")
        self._base_url = base_url or os.environ.get(
            "FXMACRO_BASE_URL", "https://api.fxmacrodata.com/v1"
        )
        self._mock = not self._api_key

        if self._mock:
            logger.info("FXMacroDataClient running in MOCK mode (no API key)")
        else:
            logger.info("FXMacroDataClient configured for %s", self._base_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_central_bank_rates(self) -> dict[str, float]:
        """Fetch current central bank policy rates.

        Returns a dict mapping ISO 4217 currency code → annualised rate (``%``).

        In mock mode returns the default rates defined in ``_DEFAULT_RATES``.
        """
        if self._mock:
            return dict(_DEFAULT_RATES)

        # Production path — would call the real FXMacroData API.
        # Placeholder awaiting API subscription credentials.
        logger.warning("FXMacroData real API not yet implemented — returning mock data")
        return dict(_DEFAULT_RATES)

    async def fetch_inflation_data(self, country: str) -> pl.DataFrame:
        """Fetch historical CPI inflation data for a country.

        Args:
            country: ISO 3166-1 alpha-2 country code (``"US"``, ``"GB"``,
                ``"JP"``, ``"DE"``, etc.).

        Returns:
            ``pl.DataFrame`` with columns ``date`` (``pl.Date``) and
            ``rate`` (``pl.Float64``), sorted chronologically.

        Raises:
            MacroError: On unsupported country in mock mode or API error.
        """
        if self._mock:
            return self._mock_inflation(country)

        # Production path placeholder.
        logger.warning("FXMacroData real API not yet implemented — falling back to mock")
        return self._mock_inflation(country)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _mock_inflation(self, country: str) -> pl.DataFrame:
        """Return mock inflation data for a country."""
        country_upper = country.upper()
        rows = _DEFAULT_INFLATION.get(country_upper)
        if rows is None:
            supported = sorted(_SUPPORTED_COUNTRIES)
            msg = f"Unsupported country ``{country}`` in mock mode. Supported: {supported}"
            raise MacroError(msg)

        df = pl.DataFrame(rows).with_columns(pl.col("date").str.to_date("%Y-%m-%d")).sort("date")
        return df

    def supported_countries(self) -> list[str]:
        """Return the list of country codes with available mock data."""
        return sorted(_SUPPORTED_COUNTRIES)
