"""A test plugin that fails on start."""

from core.plugin.base import BasePlugin


class FailingStartPlugin(BasePlugin):
    """Plugin that raises an exception during start()."""

    name = "failing_start"
    version = "1.0.0"
    description = "A plugin that fails on start"

    def start(self) -> None:
        msg = "Start failed"
        raise RuntimeError(msg)
