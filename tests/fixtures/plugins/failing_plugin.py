"""A test plugin that fails on initialize."""

from core.errors import PluginFatalError
from core.plugin.base import BasePlugin


class FailingInitializePlugin(BasePlugin):
    """Plugin that raises PluginFatalError during initialize()."""

    name = "failing_init"
    version = "1.0.0"
    description = "A plugin that fails on initialize"

    def initialize(self) -> None:
        raise PluginFatalError("Cannot initialize")
