"""Custom exceptions for the agent system."""

from __future__ import annotations


class AgentError(Exception):
    """Base exception for all agent errors."""


class ModelCallError(AgentError):
    """Raised when an LLM call fails."""


class DebateTimeoutError(AgentError):
    """Raised when a debate round exceeds the timeout."""


class CircuitBreakerOpenError(AgentError):
    """Raised when the circuit breaker is open and calls are blocked."""
