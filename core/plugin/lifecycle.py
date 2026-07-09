"""Plugin lifecycle state machine."""

from __future__ import annotations

from enum import Enum, auto


class PluginLifecycle(Enum):
    """Possible states in the plugin lifecycle state machine."""

    REGISTERED = auto()
    VALIDATED = auto()
    INITIALIZED = auto()
    STARTED = auto()
    STOPPED = auto()
    DISPOSED = auto()
    ERROR = auto()
