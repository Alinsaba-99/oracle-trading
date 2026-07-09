"""Subscription manager for tracking active NATS subscriptions."""

from collections.abc import Callable
from typing import Any


class SubscriptionManager:
    """Manages a registry of active NATS subscriptions.

    Tracks which subjects have registered handlers so they can be
    inspected or torn down cleanly.
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[tuple[Callable[..., Any], str | None]]] = {}

    def add(self, subject: str, handler: Callable[..., Any], queue: str | None = None) -> None:
        """Register a handler for *subject*.

        Args:
            subject: NATS subject to subscribe to.
            handler: Callback invoked when a message arrives.
            queue: Optional queue-group name for competing consumers.
        """
        self._subscriptions.setdefault(subject, []).append((handler, queue))

    def remove(self, subject: str, handler: Callable[..., Any]) -> None:
        """Unregister a specific handler from *subject*.

        Removes the subject entry entirely when the last handler is removed.
        No-op when the subject or handler is not found.
        """
        if subject not in self._subscriptions:
            return
        self._subscriptions[subject] = [
            (h, q) for h, q in self._subscriptions[subject] if h is not handler
        ]
        if not self._subscriptions[subject]:
            del self._subscriptions[subject]

    def list(self) -> list[str]:
        """Return a list of all subjects with active subscriptions."""
        return list(self._subscriptions.keys())
