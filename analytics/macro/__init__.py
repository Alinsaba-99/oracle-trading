"""M8 Macro — economic indicators, central bank rates, inflation, macro state.

Provides FRED API integration, FXMacroData connector, macro state
publishing for regime detection context, and the BL-724 economic events
calendar for news-blackout guards.
"""

from analytics.macro.calendar import (
    ASSET_CURRENCIES,
    DEFAULT_CALENDAR_PATH,
    SCHEMA_VERSION,
    ImpactLevel,
    MacroCalendar,
    MacroEvent,
    get_upcoming_events,
    is_in_blackout_window,
)
from analytics.macro.fred import FREDClient
from analytics.macro.fxmacro import FXMacroDataClient
from analytics.macro.state import MacroStatePublisher

__all__ = [
    "ASSET_CURRENCIES",
    "DEFAULT_CALENDAR_PATH",
    "SCHEMA_VERSION",
    "FREDClient",
    "FXMacroDataClient",
    "ImpactLevel",
    "MacroCalendar",
    "MacroEvent",
    "MacroStatePublisher",
    "get_upcoming_events",
    "is_in_blackout_window",
]
