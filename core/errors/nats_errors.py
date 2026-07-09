"""NATS connection errors."""

from core.errors.base import OracleError


class NATSConnectionError(OracleError):
    """Failed to connect or disconnected from NATS."""


class NATSDisconnectedError(NATSConnectionError):
    """Lost connection to NATS."""


class NATSTimeoutError(NATSConnectionError):
    """NATS operation timed out."""
