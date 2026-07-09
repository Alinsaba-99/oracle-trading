"""Oracle Plugin System.

Provides the framework for discovering, registering, and managing
the lifecycle of plugins within the Oracle platform.
"""

from __future__ import annotations

from core.plugin.base import BasePlugin
from core.plugin.discovery import PluginDiscovery
from core.plugin.lifecycle import PluginLifecycle
from core.plugin.registry import PluginRegistry


def discover_plugins(
    entry_point_group: str = "oracle.plugins", directory_path: str | None = None
) -> list[type[BasePlugin]]:
    """Convenience function to discover all available plugin classes.

    Args:
        entry_point_group: The entry point group to scan.
        directory_path: Optional directory path to scan for plugins.

    Returns:
        A list of discovered BasePlugin subclasses.
    """
    from pathlib import Path

    discovery = PluginDiscovery()
    path = Path(directory_path) if directory_path else None
    return discovery.discover_all(entry_point_group=entry_point_group, directory_path=path)


__all__ = ["BasePlugin", "PluginDiscovery", "PluginLifecycle", "PluginRegistry", "discover_plugins"]
