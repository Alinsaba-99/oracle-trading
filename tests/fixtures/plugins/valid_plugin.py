"""A valid test plugin for unit tests."""

from typing import Any, ClassVar

from core.plugin.base import BasePlugin


class ValidTestPlugin(BasePlugin):
    """A minimal working plugin for testing."""

    name = "valid_test"
    version = "1.0.0"
    description = "A valid test plugin"
    dependencies: ClassVar[list[str]] = []
    subjects_in: ClassVar[list[str]] = ["test.subject"]
    subjects_out: ClassVar[list[str]] = ["test.output"]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.validate_called = False
        self.initialize_called = False
        self.start_called = False
        self.stop_called = False
        self.dispose_called = False

    def validate(self) -> list[str]:
        self.validate_called = True
        return []

    def initialize(self) -> None:
        self.initialize_called = True

    def start(self) -> None:
        self.start_called = True

    def stop(self) -> None:
        self.stop_called = True

    def dispose(self) -> None:
        self.dispose_called = True
