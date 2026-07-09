"""Oracle logging — structlog with stdlib bridging."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import structlog

from core.logging.config import configure_logging

__all__ = ["configure_logging", "get_logger"]


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with caller context."""
    import structlog

    return structlog.get_logger(name or __name__)  # type: ignore[no-any-return]
