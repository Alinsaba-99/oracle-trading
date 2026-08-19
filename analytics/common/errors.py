"""Analytics error hierarchy."""

from core.errors import OracleError

# Backward-compatible re-export: canonical home is core.errors.data_errors.
from core.errors.data_errors import IngestionError


class AnalyticsError(OracleError):
    """Base for all analytics errors."""


class IndicatorError(AnalyticsError):
    """Technical indicator computation error."""


class RegimeError(AnalyticsError):
    """Regime detection error."""


class StoreError(AnalyticsError):
    """Feature store error."""


class MacroError(AnalyticsError):
    """Macro data fetch or processing error."""


__all__ = [
    "AnalyticsError",
    "IndicatorError",
    "IngestionError",
    "MacroError",
    "RegimeError",
    "StoreError",
]
