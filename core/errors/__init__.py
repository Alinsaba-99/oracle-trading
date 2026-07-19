"""Oracle error hierarchy — all exception classes."""

from core.errors.base import OracleError, OracleFatalError, RiskGateError, SafetyError
from core.errors.config_errors import ConfigError, ConfigNotFoundError, ConfigValidationError
from core.errors.event_errors import EventError, EventPublishError, EventSubscribeError
from core.errors.logging_errors import LoggingConfigurationError
from core.errors.nats_errors import NATSConnectionError, NATSDisconnectedError, NATSTimeoutError
from core.errors.plugin_errors import (
    PluginDependencyError,
    PluginError,
    PluginFatalError,
    PluginNotFoundError,
    PluginRegistrationError,
)

__all__ = [
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "EventError",
    "EventPublishError",
    "EventSubscribeError",
    "LoggingConfigurationError",
    "NATSConnectionError",
    "NATSDisconnectedError",
    "NATSTimeoutError",
    "OracleError",
    "OracleFatalError",
    "PluginDependencyError",
    "PluginError",
    "PluginFatalError",
    "PluginNotFoundError",
    "PluginRegistrationError",
    "RiskGateError",
    "SafetyError",
]
