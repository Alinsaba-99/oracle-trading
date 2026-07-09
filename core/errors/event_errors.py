"""Event bus errors."""

from core.errors.base import OracleError


class EventError(OracleError):
    """Base for all event bus errors."""


class EventPublishError(EventError):
    """Failed to publish event."""


class EventSubscribeError(EventError):
    """Failed to subscribe to event subject."""
