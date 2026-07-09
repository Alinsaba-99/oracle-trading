"""Logging configuration errors."""

from core.errors.base import OracleError


class LoggingConfigurationError(OracleError):
    """Failed to configure logging."""
