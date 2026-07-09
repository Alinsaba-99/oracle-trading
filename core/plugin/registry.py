"""Thread-safe plugin registry with lifecycle management."""

from __future__ import annotations

import asyncio
import builtins
import threading
from typing import TYPE_CHECKING

from core.errors import (
    PluginDependencyError,
    PluginFatalError,
    PluginNotFoundError,
    PluginRegistrationError,
)
from core.plugin.lifecycle import PluginLifecycle

if TYPE_CHECKING:
    from core.plugin.base import BasePlugin


class PluginRegistry:
    """Thread-safe registry managing plugin registration and lifecycle.

    Maintains an internal mapping of plugin names to instances along with
    per-plugin state tracking. Lifecycle transitions are orchestrated here
    to ensure consistency.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plugins: dict[str, BasePlugin] = {}
        self._states: dict[str, PluginLifecycle] = {}

    # --- Registration ---

    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin into the registry.

        Raises PluginRegistrationError if the plugin name is empty, a
        plugin with the same name is already registered, or a dependency
        is not (yet) registered.
        """
        if not plugin.name:
            raise PluginRegistrationError(
                "Plugin must have a non-empty name", code="PLUGIN_EMPTY_NAME"
            )

        with self._lock:
            if plugin.name in self._plugins:
                raise PluginRegistrationError(
                    f"Plugin '{plugin.name}' is already registered",
                    code="PLUGIN_ALREADY_REGISTERED",
                )

            for dep in plugin.dependencies:
                if dep not in self._plugins:
                    raise PluginDependencyError(
                        f"Plugin '{plugin.name}' depends on '{dep}' which is not registered",
                        code="PLUGIN_MISSING_DEPENDENCY",
                    )

            self._plugins[plugin.name] = plugin
            self._states[plugin.name] = PluginLifecycle.REGISTERED

    def get(self, name: str) -> BasePlugin:
        """Retrieve a plugin by name.

        Raises PluginNotFoundError if the plugin is not registered.
        """
        with self._lock:
            plugin = self._plugins.get(name)
        if plugin is None:
            raise PluginNotFoundError(
                f"Plugin '{name}' not found in registry", code="PLUGIN_NOT_FOUND"
            )
        return plugin

    def list(self, plugin_type: type | None = None) -> builtins.list[BasePlugin]:
        with self._lock:
            plugins = list(self._plugins.values())
        if plugin_type is not None:
            return [p for p in plugins if isinstance(p, plugin_type)]
        return plugins

    def is_loaded(self, name: str) -> bool:
        """Check whether a plugin is registered in the registry."""
        with self._lock:
            return name in self._plugins

    def unload(self, name: str) -> None:
        """Unload (remove) a plugin from the registry.

        Raises PluginNotFoundError if the plugin is not registered.
        """
        with self._lock:
            if name not in self._plugins:
                raise PluginNotFoundError(
                    f"Plugin '{name}' not found in registry", code="PLUGIN_NOT_FOUND"
                )
            del self._plugins[name]
            self._states.pop(name, None)

    # --- State queries ---

    def get_state(self, name: str) -> PluginLifecycle:
        """Get the current lifecycle state of a plugin.

        Raises PluginNotFoundError if the plugin is not registered.
        """
        with self._lock:
            state = self._states.get(name)
        if state is None:
            raise PluginNotFoundError(
                f"Plugin '{name}' not found in registry", code="PLUGIN_NOT_FOUND"
            )
        return state

    # --- Lifecycle orchestration ---

    def validate_plugin(self, name: str) -> builtins.list[str]:
        """Validate a registered plugin.

        Transitions state to VALIDATED on success.
        Returns validation errors.
        Raises PluginNotFoundError if not registered.
        """
        plugin = self.get(name)
        errors = plugin.validate()
        if not errors:
            self._states[name] = PluginLifecycle.VALIDATED
        return errors

    def initialize_plugin(self, name: str) -> None:
        """Initialize a registered plugin.

        Transitions state to INITIALIZED on success.
        Transitions state to ERROR if PluginFatalError is raised.
        Raises other exceptions normally.
        """
        plugin = self.get(name)
        try:
            plugin.initialize()
        except PluginFatalError:
            self._states[name] = PluginLifecycle.ERROR
            raise
        self._states[name] = PluginLifecycle.INITIALIZED

    def start_plugin(self, name: str) -> None:
        """Start a registered plugin.

        Transitions state to STARTED on success.
        """
        plugin = self.get(name)
        plugin.start()
        self._states[name] = PluginLifecycle.STARTED

    def stop_plugin(self, name: str) -> None:
        """Stop a registered and started plugin.

        Transitions state to STOPPED on success.
        """
        with self._lock:
            state = self._states.get(name)
        if state != PluginLifecycle.STARTED:
            return  # Idempotent — nothing to stop
        plugin = self.get(name)
        plugin.stop()
        self._states[name] = PluginLifecycle.STOPPED

    def dispose_plugin(self, name: str) -> None:
        """Dispose a plugin, releasing its resources.

        Transitions state to DISPOSED.
        """
        with self._lock:
            state = self._states.get(name)
        if state in (PluginLifecycle.DISPOSED, None):
            return  # Already disposed or not registered
        plugin = self.get(name)
        plugin.dispose()
        self._states[name] = PluginLifecycle.DISPOSED

    # --- Batch operations ---

    async def start_all(self) -> dict[str, Exception | None]:
        """Start all registered plugins concurrently.

        Uses asyncio.gather with return_exceptions=True so that a single
        plugin failure does not prevent others from starting.

        Returns a dict mapping plugin name to Exception (if failed) or
        None (if successful). Failed plugins have their state set to ERROR.
        """
        with self._lock:
            names = list(self._plugins.keys())

        results = await asyncio.gather(
            *(self._start_one(name) for name in names), return_exceptions=True
        )

        errors: dict[str, Exception | None] = {}
        for name, result in zip(names, results, strict=True):
            if isinstance(result, Exception):
                errors[name] = result
                self._states[name] = PluginLifecycle.ERROR
            else:
                errors[name] = None
        return errors

    async def _start_one(self, name: str) -> None:
        """Start a single plugin by name — used internally by start_all."""
        plugin = self.get(name)
        plugin.start()
        self._states[name] = PluginLifecycle.STARTED
