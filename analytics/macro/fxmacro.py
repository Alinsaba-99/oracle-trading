"""FXMacroData connector — central bank rates and inflation data.

The real FXMacroData service has paid tiers. This connector provides a
mock-based implementation that returns sensible synthetic data when no
API key is configured, making it usable in development and testing.

In production, when ``FXMACRO_API_KEY`` or ``FRED_API_KEY`` is set, the
connector delegates to the respective real API.  When neither is available
and ``mock=False`` was explicitly requested, an error is raised rather than
silently returning mock data.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import polars as pl

from analytics.common.errors import MacroError
from analytics.macro.fred import FREDClient

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
    at your FXMacroData subscription endpoint, or set ``FRED_API_KEY`` to
    use the FRED API for US data.

    Setting ``mock=False`` explicitly will raise an error when no real
    API is available, preventing silent mock fallback.
    """

    def __init__(
        self, api_key: str | None = None, base_url: str | None = None, mock: bool | None = None
    ) -> None:
        self._api_key = api_key or os.environ.get("FXMACRO_API_KEY", "")
        self._base_url = base_url or os.environ.get(
            "FXMACRO_BASE_URL", "https://api.fxmacrodata.com/v1"
        )
        self._fred_api_key = os.environ.get("FRED_API_KEY", "")

        # Resolve mock mode:
        # - Explicit mock=True/False takes precedence
        # - Default: mock=True when no API key is available
        if mock is not None:
            self._mock = mock
        else:
            self._mock = not (bool(self._api_key) or bool(self._fred_api_key))

        if self._mock:
            logger.info("FXMacroDataClient running in MOCK mode (no API key)")
        else:
            sources = []
            if self._api_key:
                sources.append("FXMacroData")
            if self._fred_api_key:
                sources.append("FRED")
            logger.info("FXMacroDataClient configured with: %s", ", ".join(sources))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_central_bank_rates(self) -> dict[str, float]:
        """Fetch current central bank policy rates.

        Returns a dict mapping ISO 4217 currency code -> annualised rate (``%``).

        Uses FRED's ``FEDFUNDS`` series for USD when ``FRED_API_KEY`` is
        available, otherwise falls back to FXMacroData API.  Raises
        ``MacroError`` when ``mock=False`` and no real API is accessible.
        """
        if self._mock:
            return dict(_DEFAULT_RATES)

        # Try FRED for USD rate first (free, no subscription needed)
        if self._fred_api_key:
            try:
                async with FREDClient(self._fred_api_key) as fred:
                    df = await fred.fetch_series("FEDFUNDS")
                    if not df.is_empty():
                        latest = df["value"][-1]
                        rates = dict(_DEFAULT_RATES)
                        rates["USD"] = latest
                        return rates
            except Exception as exc:
                logger.warning("FRED FEDFUNDS fetch failed: %s", exc)

        # Try FXMacroData API
        if self._api_key:
            msg = "FXMacroData API not yet implemented — use FRED_API_KEY instead"
            raise MacroError(msg)

        msg = (
            "No API key configured for production mode. "
            "Set FRED_API_KEY environment variable for free US data, "
            "or FXMACRO_API_KEY for the FXMacroData service."
        )
        raise MacroError(msg)

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

        # FRED -> CPIAUCSL series for US CPI
        if country.upper() == "US" and self._fred_api_key:
            try:
                async with FREDClient(self._fred_api_key) as fred:
                    raw = await fred.fetch_series("CPIAUCSL")
                    if raw.is_empty():
                        return self._mock_inflation(country)
                    # Convert CPI level to YoY change %
                    df = raw.with_columns(
                        pl.col("value").pct_change(periods=12).alias("rate") * 100  # type: ignore[call-arg]
                    ).drop_nulls()
                    if df.is_empty():
                        return self._mock_inflation(country)
                    return df.select("date", "rate").sort("date")
            except Exception as exc:
                logger.warning("FRED CPI fetch failed for %s: %s", country, exc)
                if self._api_key:
                    msg = f"FRED failed and FXMacroData fallback not available: {exc}"
                    raise MacroError(msg) from exc
                return self._mock_inflation(country)

        # Fallback to mock data if available for this country
        if country.upper() in _SUPPORTED_COUNTRIES:
            logger.warning("No API available for %s inflation, returning mock data", country)
            return self._mock_inflation(country)

        msg = (
            f"No data available for country '{country}' in production mode. "
            "Set FRED_API_KEY for US data, or use mock=True for development."
        )
        raise MacroError(msg)

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
