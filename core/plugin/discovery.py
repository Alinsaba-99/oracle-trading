"""Plugin discovery via entry points and directory scanning."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.plugin.base import BasePlugin


class PluginDiscovery:
    """Discovers BasePlugin subclasses via two mechanisms:

    1. Package entry points (importlib.metadata) for pip-installed plugins.
    2. Directory scanning for local development plugins.
    """

    @staticmethod
    def discover_entry_points(group: str = "oracle.plugins") -> list[type[BasePlugin]]:
        """Discover plugins registered via package entry points.

        Scans the named entry point group (default ``oracle.plugins``)
        and returns a list of discovered plugin classes.
        """
        from core.plugin.base import BasePlugin

        try:
            from importlib.metadata import entry_points

            eps = entry_points(group=group)
        except (ImportError, TypeError):
            return []

        plugins: list[type[BasePlugin]] = []
        for ep in eps:
            try:
                cls = ep.load()
                if isinstance(cls, type) and issubclass(cls, BasePlugin) and cls is not BasePlugin:
                    plugins.append(cls)
            except Exception:
                continue
        return plugins

    @staticmethod
    def discover_directory(path: Path | None = None) -> list[type[BasePlugin]]:
        """Discover plugins by scanning a directory for BasePlugin subclasses.

        Scans all ``.py`` files in *path* (defaults to ``plugins`` relative
        to the working directory), imports each, and collects any
        ``BasePlugin`` subclass (excluding ``BasePlugin`` itself).
        """

        if path is None:
            path = Path("plugins")

        if not path.is_dir():
            return []

        resolved = path.resolve()
        parent = resolved.parent

        # Ensure parent is on sys.path so imports resolve
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))

        plugins: list[type[BasePlugin]] = []

        # If the directory is a package, use pkgutil to walk all submodules
        if (resolved / "__init__.py").exists():
            pkg_name = resolved.name
            try:
                pkg = importlib.import_module(pkg_name)
                _collect_from_package(pkg, plugins)
                return plugins
            except ImportError:
                pass

        # Fallback: scan .py files directly
        plugins.extend(_scan_directory_direct(resolved))
        return plugins

    @staticmethod
    def discover_all(
        entry_point_group: str = "oracle.plugins", directory_path: Path | None = None
    ) -> list[type[BasePlugin]]:
        """Discover plugins from both entry points and directory scanning.

        Returns a deduplicated combined list (entry-point plugins first).
        """
        ep_plugins = PluginDiscovery.discover_entry_points(group=entry_point_group)
        dir_plugins = PluginDiscovery.discover_directory(path=directory_path)
        seen: set[type[BasePlugin]] = set()
        result: list[type[BasePlugin]] = []
        for cls in ep_plugins + dir_plugins:
            if cls not in seen:
                seen.add(cls)
                result.append(cls)
        return result


def _collect_from_package(pkg: ModuleType, result: list[type[BasePlugin]]) -> None:
    """Recursively walk a package collecting BasePlugin subclasses."""
    import pkgutil

    prefix = f"{pkg.__name__}."

    # Scan the top-level module
    _scan_module(pkg, result)

    for _finder, modname, _is_pkg in pkgutil.walk_packages(
        path=getattr(pkg, "__path__", []), prefix=prefix, onerror=lambda _: None
    ):
        try:
            module = importlib.import_module(modname)
        except Exception:
            continue
        _scan_module(module, result)


def _scan_module(module: ModuleType, result: list[type[BasePlugin]]) -> None:
    """Scan a module's public attributes for BasePlugin subclasses."""
    from core.plugin.base import BasePlugin

    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue
        attr = getattr(module, attr_name, None)
        if (
            isinstance(attr, type)
            and issubclass(attr, BasePlugin)
            and attr is not BasePlugin
            and attr not in result
        ):
            result.append(attr)


def _scan_directory_direct(path: Path) -> list[type[BasePlugin]]:
    """Scan .py files in a directory for BasePlugin subclasses."""
    from core.plugin.base import BasePlugin

    plugins: list[type[BasePlugin]] = []

    for py_file in sorted(path.glob("*.py")):
        if py_file.stem.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            continue

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name, None)
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
                and attr not in plugins
            ):
                plugins.append(attr)

    return plugins
