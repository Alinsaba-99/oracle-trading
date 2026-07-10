"""Simple broker registry — maps names to broker instances."""

from __future__ import annotations

from typing import Any


class BrokerRegistry:
    """Map broker names to their instances and switch the active one."""

    def __init__(self) -> None:
        self._brokers: dict[str, Any] = {}
        self._active: str = "paper"

    def register(self, name: str, broker: Any) -> None:
        self._brokers[name] = broker

    def get(self, name: str | None = None) -> Any:
        return self._brokers.get(name or self._active)

    def set_active(self, name: str) -> None:
        if name not in self._brokers:
            raise ValueError(f"Broker {name!r} not registered")
        self._active = name

    def active_name(self) -> str:
        return self._active

    def list_brokers(self) -> list[str]:
        return list(self._brokers)
