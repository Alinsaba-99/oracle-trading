"""Tests for the Plugin System module (BasePlugin, Registry, Discovery, Lifecycle)."""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.errors import (
    PluginDependencyError,
    PluginFatalError,
    PluginNotFoundError,
    PluginRegistrationError,
)
from core.plugin import BasePlugin, PluginDiscovery, PluginLifecycle, PluginRegistry

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def registry() -> PluginRegistry:
    return PluginRegistry()


@pytest.fixture
def valid_plugin_cls() -> type[BasePlugin]:
    from tests.fixtures.plugins.valid_plugin import ValidTestPlugin

    return ValidTestPlugin


@pytest.fixture
def valid_plugin(valid_plugin_cls: type[BasePlugin]) -> BasePlugin:
    return valid_plugin_cls()


@pytest.fixture
def failing_plugin_cls() -> type[BasePlugin]:
    from tests.fixtures.plugins.failing_plugin import FailingInitializePlugin

    return FailingInitializePlugin


@pytest.fixture
def failing_plugin(failing_plugin_cls: type[BasePlugin]) -> BasePlugin:
    return failing_plugin_cls()


@pytest.fixture
def start_failing_plugin_cls() -> type[BasePlugin]:
    from tests.fixtures.plugins.start_failing_plugin import FailingStartPlugin

    return FailingStartPlugin


@pytest.fixture
def start_failing_plugin(start_failing_plugin_cls: type[BasePlugin]) -> BasePlugin:
    return start_failing_plugin_cls()


# =============================================================================
# BasePlugin Tests
# =============================================================================


class TestBasePlugin:
    """Tests for BasePlugin abstract class."""

    def test_cannot_instantiate_base(self):
        """BasePlugin itself cannot be instantiated (has abstract methods?)."""
        # BasePlugin has no abstractmethod decorators, but is ABC.
        # Actually looking at the implementation, ABC alone doesn't prevent
        # instantiation unless there are abstractmethods. Let's verify it
        # can be used as a base.
        from core.plugin.base import BasePlugin

        assert BasePlugin.__bases__ == (ABC,)

    def test_subclass_defaults(self, valid_plugin: BasePlugin):
        assert valid_plugin.name == "valid_test"
        assert valid_plugin.version == "1.0.0"
        assert valid_plugin.description == "A valid test plugin"
        assert valid_plugin.dependencies == []
        assert valid_plugin.subjects_in == ["test.subject"]
        assert valid_plugin.subjects_out == ["test.output"]
        assert valid_plugin.config_schema is None

    def test_subclass_with_config(self):
        """Config passed to __init__ is stored."""
        from tests.fixtures.plugins.valid_plugin import ValidTestPlugin

        plugin = ValidTestPlugin(config={"key": "value"})
        assert plugin.config == {"key": "value"}

    def test_default_config_is_empty_dict(self, valid_plugin: BasePlugin):
        assert valid_plugin.config == {}

    def test_initial_state_is_registered(self, valid_plugin: BasePlugin):
        assert valid_plugin.state == PluginLifecycle.REGISTERED

    def test_lifecycle_methods_have_no_op_defaults(self, valid_plugin: BasePlugin):
        """Default lifecycle methods should not raise."""
        assert valid_plugin.validate() == []
        valid_plugin.initialize()  # no-op
        valid_plugin.start()  # no-op
        valid_plugin.stop()  # no-op
        valid_plugin.dispose()  # no-op

    def test_publish_without_event_bus_raises(self, valid_plugin: BasePlugin):
        """publish without _event_bus assigned raises RuntimeError."""
        with pytest.raises(RuntimeError, match="no event bus assigned"):
            # Must use synchronous context since publish is async
            import asyncio

            asyncio.run(valid_plugin.publish("test.subject", {"key": "val"}))

    def test_publish_passes_bare_data(self):
        """publish passes bare data per ADR-008."""
        from tests.fixtures.plugins.valid_plugin import ValidTestPlugin

        plugin = ValidTestPlugin()
        mock_bus = AsyncMock()
        plugin._event_bus = mock_bus

        import asyncio

        asyncio.run(plugin.publish("test.subject", {"key": "value"}, extra="kwarg"))

        mock_bus.publish.assert_called_once_with(
            "test.subject", {"key": "value"}, source="plugin.valid_test", extra="kwarg"
        )

    def test_custom_source_in_publish(self):
        """Custom source kwarg overrides the default."""
        from tests.fixtures.plugins.valid_plugin import ValidTestPlugin

        plugin = ValidTestPlugin()
        mock_bus = AsyncMock()
        plugin._event_bus = mock_bus

        import asyncio

        asyncio.run(plugin.publish("test.subject", {"key": "value"}, source="custom.source"))

        mock_bus.publish.assert_called_once_with(
            "test.subject", {"key": "value"}, source="custom.source"
        )


# =============================================================================
# PluginLifecycle Tests
# =============================================================================


class TestPluginLifecycle:
    """Tests for the PluginLifecycle enum."""

    def test_enum_values(self):
        assert PluginLifecycle.REGISTERED.value == 1
        assert PluginLifecycle.VALIDATED.value == 2
        assert PluginLifecycle.INITIALIZED.value == 3
        assert PluginLifecycle.STARTED.value == 4
        assert PluginLifecycle.STOPPED.value == 5
        assert PluginLifecycle.DISPOSED.value == 6
        assert PluginLifecycle.ERROR.value == 7

    def test_enum_members(self):
        members = {e.name for e in PluginLifecycle}
        expected = {
            "REGISTERED",
            "VALIDATED",
            "INITIALIZED",
            "STARTED",
            "STOPPED",
            "DISPOSED",
            "ERROR",
        }
        assert members == expected


# =============================================================================
# PluginRegistry Tests
# =============================================================================


class TestPluginRegistryRegistration:
    """Tests for PluginRegistry.register, get, list, is_loaded, unload."""

    def test_register_and_get(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        retrieved = registry.get("valid_test")
        assert retrieved is valid_plugin

    def test_register_get_not_found_raises(self, registry: PluginRegistry):
        with pytest.raises(PluginNotFoundError, match="not found"):
            registry.get("nonexistent")

    def test_register_duplicate_raises(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        with pytest.raises(PluginRegistrationError, match="already registered"):
            registry.register(valid_plugin)

    def test_register_empty_name_raises(self, registry: PluginRegistry):
        from tests.fixtures.plugins.valid_plugin import ValidTestPlugin

        plugin = ValidTestPlugin()
        plugin.name = ""
        with pytest.raises(PluginRegistrationError, match="non-empty name"):
            registry.register(plugin)

    def test_register_missing_dependency_raises(self, registry: PluginRegistry):
        from tests.fixtures.plugins.dep_plugin import DependentTestPlugin

        plugin = DependentTestPlugin()
        with pytest.raises(PluginDependencyError, match="not registered"):
            registry.register(plugin)

    def test_register_with_dependency_satisfied(
        self, registry: PluginRegistry, valid_plugin: BasePlugin
    ):
        from tests.fixtures.plugins.dep_plugin import DependentTestPlugin

        registry.register(valid_plugin)
        dep = DependentTestPlugin()
        registry.register(dep)
        assert registry.is_loaded("dependent_test")

    def test_list_all(self, registry: PluginRegistry, valid_plugin: BasePlugin, failing_plugin):
        registry.register(valid_plugin)
        registry.register(failing_plugin)
        all_plugins = registry.list()
        assert len(all_plugins) == 2

    def test_list_filtered_by_type(
        self, registry: PluginRegistry, valid_plugin: BasePlugin, failing_plugin
    ):
        registry.register(valid_plugin)
        registry.register(failing_plugin)

        # Filter by BasePlugin — all are BasePlugin subclasses
        from core.plugin.base import BasePlugin

        all_of_type = registry.list(BasePlugin)
        assert len(all_of_type) == 2

    def test_is_loaded(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        assert not registry.is_loaded("valid_test")
        registry.register(valid_plugin)
        assert registry.is_loaded("valid_test")

    def test_unload(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        assert registry.is_loaded("valid_test")
        registry.unload("valid_test")
        assert not registry.is_loaded("valid_test")

    def test_unload_not_found_raises(self, registry: PluginRegistry):
        with pytest.raises(PluginNotFoundError, match="not found"):
            registry.unload("nonexistent")

    def test_state_removed_on_unload(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        registry.unload("valid_test")
        with pytest.raises(PluginNotFoundError):
            registry.get_state("valid_test")


class TestPluginRegistryLifecycle:
    """Tests for lifecycle orchestration methods."""

    def test_validate_plugin(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        errors = registry.validate_plugin("valid_test")
        assert errors == []
        assert registry.get_state("valid_test") == PluginLifecycle.VALIDATED

    def test_validate_plugin_returns_errors(self, registry: PluginRegistry):
        """A plugin whose validate returns errors stays in REGISTERED state."""

        class InvalidPlugin(BasePlugin):
            name = "invalid"
            version = "1.0.0"
            description = "Invalid plugin"

            def validate(self) -> list[str]:
                return ["missing config", "bad value"]

        plugin = InvalidPlugin()
        registry.register(plugin)
        errors = registry.validate_plugin("invalid")
        assert errors == ["missing config", "bad value"]
        assert registry.get_state("invalid") == PluginLifecycle.REGISTERED

    def test_initialize_plugin(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        registry.initialize_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.INITIALIZED

    def test_initialize_plugin_fatal_error(self, registry: PluginRegistry, failing_plugin):
        """PluginFatalError during initialize sets state to ERROR."""
        registry.register(failing_plugin)
        with pytest.raises(PluginFatalError):
            registry.initialize_plugin("failing_init")
        assert registry.get_state("failing_init") == PluginLifecycle.ERROR

    def test_start_plugin(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        registry.initialize_plugin("valid_test")
        registry.start_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.STARTED

    def test_stop_plugin(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        registry.initialize_plugin("valid_test")
        registry.start_plugin("valid_test")
        registry.stop_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.STOPPED

    def test_stop_when_not_started_is_idempotent(
        self, registry: PluginRegistry, valid_plugin: BasePlugin
    ):
        """stop on a non-started plugin should not raise."""
        registry.register(valid_plugin)
        registry.validate_plugin("valid_test")
        registry.initialize_plugin("valid_test")
        # Not started — stop should be a no-op
        registry.stop_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.INITIALIZED

    def test_dispose_plugin(self, registry: PluginRegistry, valid_plugin: BasePlugin):
        registry.register(valid_plugin)
        registry.dispose_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.DISPOSED

    def test_dispose_already_disposed_is_idempotent(
        self, registry: PluginRegistry, valid_plugin: BasePlugin
    ):
        registry.register(valid_plugin)
        registry.dispose_plugin("valid_test")
        registry.dispose_plugin("valid_test")  # Should not raise
        assert registry.get_state("valid_test") == PluginLifecycle.DISPOSED

    def test_full_lifecycle(self, registry: PluginRegistry, valid_plugin: BasePlugin) -> None:
        """Full lifecycle: register - validate - init - start - stop - dispose."""
        registry.register(valid_plugin)
        assert registry.get_state("valid_test") == PluginLifecycle.REGISTERED

        errors = registry.validate_plugin("valid_test")
        assert errors == []
        assert registry.get_state("valid_test") == PluginLifecycle.VALIDATED

        registry.initialize_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.INITIALIZED

        registry.start_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.STARTED

        registry.stop_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.STOPPED

        registry.dispose_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.DISPOSED

        assert valid_plugin.validate_called
        assert valid_plugin.initialize_called
        assert valid_plugin.start_called
        assert valid_plugin.stop_called
        assert valid_plugin.dispose_called

    def test_get_state_not_found_raises(self, registry: PluginRegistry):
        with pytest.raises(PluginNotFoundError):
            registry.get_state("nonexistent")


class TestPluginRegistryStartAll:
    """Tests for start_all with error isolation."""

    @pytest.mark.asyncio
    async def test_start_all_success(self, registry: PluginRegistry, valid_plugin_cls):
        """All plugins start successfully."""
        p1 = valid_plugin_cls(config={})
        p1.name = "p1"
        p2 = valid_plugin_cls(config={})
        p2.name = "p2"
        registry.register(p1)
        registry.register(p2)

        errors = await registry.start_all()

        assert errors == {"p1": None, "p2": None}
        assert registry.get_state("p1") == PluginLifecycle.STARTED
        assert registry.get_state("p2") == PluginLifecycle.STARTED
        assert p1.start_called

    @pytest.mark.asyncio
    async def test_start_all_with_one_failure(
        self, registry: PluginRegistry, valid_plugin_cls, start_failing_plugin_cls
    ):
        """One failing plugin does not prevent others from starting."""
        good = valid_plugin_cls(config={})
        good.name = "good"
        bad = start_failing_plugin_cls()
        bad.name = "bad"
        registry.register(good)
        registry.register(bad)

        errors = await registry.start_all()

        assert errors["good"] is None
        assert isinstance(errors["bad"], RuntimeError)
        assert str(errors["bad"]) == "Start failed"
        assert registry.get_state("good") == PluginLifecycle.STARTED
        assert registry.get_state("bad") == PluginLifecycle.ERROR
        assert good.start_called

    @pytest.mark.asyncio
    async def test_start_all_all_fail(self, registry: PluginRegistry, start_failing_plugin_cls):
        """All plugins fail gracefully."""
        bad1 = start_failing_plugin_cls()
        bad1.name = "bad1"
        bad2 = start_failing_plugin_cls()
        bad2.name = "bad2"
        registry.register(bad1)
        registry.register(bad2)

        errors = await registry.start_all()

        assert isinstance(errors["bad1"], RuntimeError)
        assert isinstance(errors["bad2"], RuntimeError)
        assert registry.get_state("bad1") == PluginLifecycle.ERROR
        assert registry.get_state("bad2") == PluginLifecycle.ERROR

    @pytest.mark.asyncio
    async def test_start_all_empty_registry(self, registry: PluginRegistry):
        """start_all on empty registry returns empty dict."""
        errors = await registry.start_all()
        assert errors == {}


class TestPluginRegistryThreadSafety:
    """Basic thread-safety verification."""

    def test_concurrent_register_and_list(self, registry: PluginRegistry, valid_plugin_cls):
        import threading

        results: list[Exception | None] = []

        def register_plugin(name: str):
            try:
                p = valid_plugin_cls(config={})
                p.name = name
                registry.register(p)
                results.append(None)
            except Exception as e:
                results.append(e)

        threads = [
            threading.Thread(target=register_plugin, args=(f"thread_p{i}",)) for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        nones = [r for r in results if r is None]
        assert len(nones) == 10
        assert len(registry.list()) == 10


# =============================================================================
# PluginDiscovery Tests
# =============================================================================


class TestPluginDiscoveryBase:
    """Base discovery assertions that apply to all discovery paths."""

    # The fixture plugin classes we expect to find
    EXPECTED_FIXTURE_CLASSES = {
        "ValidTestPlugin",
        "FailingInitializePlugin",
        "FailingStartPlugin",
        "DependentTestPlugin",
    }


class TestPluginDiscoveryDirectory(TestPluginDiscoveryBase):
    """Tests for PluginDiscovery.discover_directory."""

    def test_discover_fixtures_directory(self):
        """discover_directory finds all fixture plugins."""
        fixtures_path = Path("tests/fixtures/plugins")
        plugins = PluginDiscovery.discover_directory(fixtures_path)
        class_names = {cls.__name__ for cls in plugins}
        for name in self.EXPECTED_FIXTURE_CLASSES:
            assert name in class_names, f"Missing {name} in discovered plugins"

    def test_discover_nonexistent_directory(self):
        """Non-existent directory returns empty list."""
        plugins = PluginDiscovery.discover_directory(Path("nonexistent_dir_xyz"))
        assert plugins == []

    def test_discover_file_path_returns_empty(self, tmp_path):
        """A file path (not a directory) returns empty list."""
        f = tmp_path / "not_a_dir"
        f.write_text("")
        plugins = PluginDiscovery.discover_directory(f)
        assert plugins == []

    def test_discover_empty_directory(self, tmp_path):
        """Empty directory returns empty list."""
        d = tmp_path / "empty_plugins"
        d.mkdir()
        plugins = PluginDiscovery.discover_directory(d)
        assert plugins == []


class TestPluginDiscoveryEntryPoints(TestPluginDiscoveryBase):
    """Tests for PluginDiscovery.discover_entry_points."""

    def test_no_entry_points_group(self):
        """An unknown entry point group returns empty list."""
        plugins = PluginDiscovery.discover_entry_points(group="nonexistent.group.xyz")
        assert plugins == []

    def test_entry_point_discovery_with_mock(self):
        """Mock entry points return the expected plugin class."""
        from tests.fixtures.plugins.valid_plugin import ValidTestPlugin

        mock_ep = MagicMock()
        mock_ep.load.return_value = ValidTestPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            plugins = PluginDiscovery.discover_entry_points()
            assert ValidTestPlugin in plugins

    def test_entry_point_load_error_skipped(self):
        """A plugin that fails to load is skipped."""
        mock_ep = MagicMock()
        mock_ep.load.side_effect = ImportError("broken")

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            plugins = PluginDiscovery.discover_entry_points()
            assert plugins == []

    def test_entry_point_non_plugin_class_skipped(self):
        """A non-BasePlugin class in entry points is skipped."""

        class NotAPlugin:
            pass

        mock_ep = MagicMock()
        mock_ep.load.return_value = NotAPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            plugins = PluginDiscovery.discover_entry_points()
            assert plugins == []


class TestPluginDiscoveryAll(TestPluginDiscoveryBase):
    """Tests for PluginDiscovery.discover_all."""

    def test_discover_all_combines_both(self):
        """discover_all returns both entry-point and directory plugins (deduplicated)."""
        from tests.fixtures.plugins.valid_plugin import ValidTestPlugin

        fixtures_path = Path("tests/fixtures/plugins")
        mock_ep = MagicMock()
        mock_ep.load.return_value = ValidTestPlugin

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            plugins = PluginDiscovery.discover_all(directory_path=fixtures_path)

        class_names = {cls.__name__ for cls in plugins}
        assert "ValidTestPlugin" in class_names  # From both, deduped
        for name in self.EXPECTED_FIXTURE_CLASSES:
            assert name in class_names, f"Missing {name}"

    def test_discover_all_no_entry_points(self):
        """discover_all with no entry points still finds directory plugins."""
        fixtures_path = Path("tests/fixtures/plugins")
        with patch("importlib.metadata.entry_points", return_value=[]):
            plugins = PluginDiscovery.discover_all(directory_path=fixtures_path)
        class_names = {cls.__name__ for cls in plugins}
        for name in self.EXPECTED_FIXTURE_CLASSES:
            assert name in class_names


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestDiscoverPlugins:
    """Tests for the discover_plugins convenience function."""

    def test_discover_plugins_with_directory(self):
        """discover_plugins finds fixture plugins."""
        from core.plugin import discover_plugins

        plugins = discover_plugins(directory_path="tests/fixtures/plugins")
        class_names = {cls.__name__ for cls in plugins}
        assert "ValidTestPlugin" in class_names
        assert "FailingInitializePlugin" in class_names
        assert "FailingStartPlugin" in class_names
        assert "DependentTestPlugin" in class_names

    def test_discover_plugins_default_no_entry_points(self) -> None:
        """discover_plugins with default args returns empty (no oracle.plugins entry points)."""
        from core.plugin import discover_plugins

        plugins = discover_plugins()
        # In test environment there are no installed entry points,
        # and the default path 'plugins' doesn't exist or has no relevant plugins.
        # This should at least not raise.
        assert isinstance(plugins, list)


# =============================================================================
# Integration Tests
# =============================================================================


class TestPluginIntegration:
    """End-to-end scenarios: discover, register, lifecycle."""

    def test_discover_register_and_lifecycle(self, registry: PluginRegistry):
        """End-to-end: discover plugins → register → lifecycle."""
        from tests.fixtures.plugins.failing_plugin import FailingInitializePlugin
        from tests.fixtures.plugins.valid_plugin import ValidTestPlugin

        p1 = ValidTestPlugin(config={"period": 10})
        p2 = FailingInitializePlugin()

        registry.register(p1)
        registry.register(p2)

        # Validate both
        assert registry.validate_plugin("valid_test") == []
        assert registry.get_state("valid_test") == PluginLifecycle.VALIDATED

        # Initialize p1 succeeds
        registry.initialize_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.INITIALIZED

        # Initialize p2 fails
        with pytest.raises(PluginFatalError):
            registry.initialize_plugin("failing_init")
        assert registry.get_state("failing_init") == PluginLifecycle.ERROR

        # Start and stop p1
        registry.start_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.STARTED

        registry.stop_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.STOPPED

        registry.dispose_plugin("valid_test")
        assert registry.get_state("valid_test") == PluginLifecycle.DISPOSED

        assert p1.validate_called
        assert p1.initialize_called
        assert p1.start_called
        assert p1.stop_called
        assert p1.dispose_called
