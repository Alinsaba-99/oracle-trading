"""A test plugin with dependencies."""

from core.plugin.base import BasePlugin


class DependentTestPlugin(BasePlugin):
    """Plugin that depends on another plugin."""

    name = "dependent_test"
    version = "1.0.0"
    description = "A plugin with dependencies"
    dependencies = ["valid_test"]
