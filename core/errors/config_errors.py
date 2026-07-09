"""Configuration-related errors."""

from core.errors.base import OracleError


class ConfigError(OracleError):
    """Base for all configuration errors."""


class ConfigNotFoundError(ConfigError):
    """Config file or key not found."""


class ConfigValidationError(ConfigError):
    """Config value failed validation."""
