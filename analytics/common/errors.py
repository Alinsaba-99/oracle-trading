"""Analytics error hierarchy."""

from core.errors import OracleError


class AnalyticsError(OracleError):
    """Base for all analytics errors."""


class IndicatorError(AnalyticsError):
    """Technical indicator computation error."""


class RegimeError(AnalyticsError):
    """Regime detection error."""


class StoreError(AnalyticsError):
    """Feature store error."""


class IngestionError(AnalyticsError):
    """Data ingestion error."""


class MacroError(AnalyticsError):
    """Macro data fetch or processing error."""
