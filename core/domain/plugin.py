"""Plugin base class and lifecycle."""

from abc import ABC, abstractmethod
from typing import Any

from core.domain.enums import PluginLifecycle


class BasePlugin(ABC):
    name: str = ""
    version: str = "0.1.0"
    description: str = ""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.lifecycle = PluginLifecycle.registered
        self.dependencies: list[str] = []
        self.subjects_in: list[str] = []
        self.subjects_out: list[str] = []
        self.config_schema: dict[str, Any] | None = None

    @abstractmethod
    def execute(self, data: dict[str, Any]) -> dict[str, Any]: ...

    def validate(self) -> list[str]:
        return []

    def initialize(self) -> None:
        self.lifecycle = PluginLifecycle.initialized

    def start(self) -> None:
        self.lifecycle = PluginLifecycle.started

    def stop(self) -> None:
        self.lifecycle = PluginLifecycle.stopped

    def dispose(self) -> None:
        self.lifecycle = PluginLifecycle.disposed
