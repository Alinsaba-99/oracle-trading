"""Plugin system errors."""

from core.errors.base import OracleError, OracleFatalError


class PluginError(OracleError):
    """Recoverable plugin error."""


class PluginNotFoundError(PluginError):
    """Plugin not found in registry."""


class PluginRegistrationError(PluginError):
    """Plugin registration failed."""


class PluginDependencyError(PluginError):
    """Plugin dependency missing or incompatible."""


class PluginFatalError(OracleFatalError):
    """Non-recoverable plugin failure — plugin must be disabled."""
