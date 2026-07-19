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


class SafetyError(OracleError):
    """A safety control plane violation was detected.

    Raised when a safety-critical invariant is violated (e.g. risk gate
    rejects an order, mode guard blocks an action, hard limit exceeded).
    Always deterministic, never raised by LLM code.
    """

    def __init__(
        self, message: str, code: str = "SAFETY", details: dict[str, str] | None = None
    ) -> None:
        super().__init__(message, code=code, details=details)


class RiskGateError(SafetyError):
    """A risk gate rejected an order or action.

    Raised by the deterministic risk kernel when an order exceeds a hard
    limit (position size, daily loss, drawdown, contract cap, …).
    """

    def __init__(
        self, message: str, code: str = "RISK_GATE", details: dict[str, str] | None = None
    ) -> None:
        super().__init__(message, code=code, details=details)


class OracleFatalError(Exception):
    """Non-recoverable error. Intentionally NOT a subclass of OracleError.
    `except OracleError` will NOT catch this.
    """
