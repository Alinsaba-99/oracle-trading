"""Base plugin abstract class for all Oracle plugins."""

from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar

from core.plugin.lifecycle import PluginLifecycle


class BasePlugin(ABC):  # noqa: B024
    """Abstract base class for all Oracle plugins.

    Every plugin in the system must subclass this and declare metadata
    as class-level attributes. Lifecycle methods control activation:
    validate -> initialize -> start -> stop -> dispose.
    """

    # --- Metadata (declared by concrete subclasses) ---
    name: ClassVar[str] = ""
    version: ClassVar[str] = ""
    description: ClassVar[str] = ""
    dependencies: ClassVar[list[str]] = []
    subjects_in: ClassVar[list[str]] = []
    subjects_out: ClassVar[list[str]] = []
    config_schema: ClassVar[dict[str, Any] | None] = None

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = config or {}
        self._event_bus: Any = None
        self._state: PluginLifecycle = PluginLifecycle.REGISTERED

    # --- State ---

    @property
    def state(self) -> PluginLifecycle:
        """Current lifecycle state of this plugin."""
        return self._state

    @state.setter
    def state(self, value: PluginLifecycle) -> None:
        self._state = value

    # --- Lifecycle ---

    def validate(self) -> list[str]:
        """Validate configuration.

        Returns a list of error messages (empty list means valid).
        """
        return []

    def initialize(self) -> None:  # noqa: B027
        """Allocate resources. Raise on failure."""

    def start(self) -> None:  # noqa: B027
        """Start processing. Raise on failure."""

    def stop(self) -> None:  # noqa: B027
        """Gracefully stop processing."""

    def dispose(self) -> None:  # noqa: B027
        """Release all resources."""

    # --- Event helpers ---

    async def publish(self, subject: str, data: dict[str, Any], **kwargs: Any) -> None:
        """Publish an event via the event bus.

        Passes bare data -- EventBusClient owns the full envelope per ADR-008.
        """
        if self._event_bus is None:
            raise RuntimeError(f"Plugin '{self.name}' has no event bus assigned")
        source = kwargs.pop("source", f"plugin.{self.name}")
        await self._event_bus.publish(subject, data, source=source, **kwargs)
