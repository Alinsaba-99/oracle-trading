"""M8 Macro — economic indicators, central bank rates, inflation, macro state.

Provides FRED API integration, FXMacroData connector, and macro state
publishing for regime detection context.
"""

from analytics.macro.fred import FREDClient
from analytics.macro.fxmacro import FXMacroDataClient
from analytics.macro.state import MacroStatePublisher

__all__ = ["FREDClient", "FXMacroDataClient", "MacroStatePublisher"]
