"""Oracle error hierarchy — base exception classes."""

from __future__ import annotations


class OracleError(Exception):
    """Base exception for all Oracle errors (recoverable)."""

    def __init__(
        self, message: str, code: str = "UNKNOWN", details: dict[str, str] | None = None
    ) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        parts = [f"[{self.code}]", str(self.args[0])]
        if self.details:
            parts.append(str(self.details))
        return " ".join(parts)


class OracleFatalError(Exception):
    """Non-recoverable error. Intentionally NOT a subclass of OracleError.
    `except OracleError` will NOT catch this.
    """
