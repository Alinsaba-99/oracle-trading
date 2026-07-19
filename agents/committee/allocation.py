"""Deterministic HedgeAgents-style budget allocation tool."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize


@dataclass(frozen=True)
class AllocationResult:
    """Optimized desk weights and objective components."""

    weights: dict[str, float]
    expected_return: float
    portfolio_variance: float
    cvar_penalty: float


class HedgeAllocationOptimizer:
    """Optimize expected return minus covariance and CVaR penalties.

    The LLM proposes expected returns and risk preferences; this tool performs
    the numerical constrained optimization used by the portfolio council.
    """

    def allocate(
        self,
        *,
        instruments: list[str],
        expected_returns: np.ndarray,
        covariance: np.ndarray,
        cvar: np.ndarray,
        variance_aversion: float = 1.0,
        cvar_aversion: float = 1.0,
        max_weights: np.ndarray | None = None,
    ) -> AllocationResult:
        count = len(instruments)
        if count == 0:
            raise ValueError("at least one instrument is required")
        if expected_returns.shape != (count,):
            raise ValueError("expected_returns shape must match instruments")
        if covariance.shape != (count, count):
            raise ValueError("covariance shape must be square and match instruments")
        if cvar.shape != (count,):
            raise ValueError("cvar shape must match instruments")
        if variance_aversion < 0.0 or cvar_aversion < 0.0:
            raise ValueError("risk aversion values cannot be negative")

        caps = max_weights if max_weights is not None else np.ones(count)
        if caps.shape != (count,) or np.any(caps <= 0.0) or np.any(caps > 1.0):
            raise ValueError("max_weights must contain values in (0, 1]")
        if float(np.sum(caps)) < 1.0:
            raise ValueError("max_weights do not permit a fully allocated portfolio")

        def objective(weights: np.ndarray) -> float:
            expected = float(weights @ expected_returns)
            variance = float(weights @ covariance @ weights)
            tail_risk = float(weights @ cvar)
            return -(expected - variance_aversion * variance - cvar_aversion * tail_risk)

        result = minimize(
            objective,
            np.full(count, 1.0 / count),
            method="SLSQP",
            bounds=[(0.0, float(cap)) for cap in caps],
            constraints=[{"type": "eq", "fun": lambda weights: float(np.sum(weights) - 1.0)}],
            options={"ftol": 1e-12, "maxiter": 500},
        )
        if not result.success:
            raise ValueError(f"allocation optimization failed: {result.message}")

        weights = np.asarray(result.x, dtype=float)
        return AllocationResult(
            weights={
                instrument: float(weight)
                for instrument, weight in zip(instruments, weights, strict=True)
            },
            expected_return=float(weights @ expected_returns),
            portfolio_variance=float(weights @ covariance @ weights),
            cvar_penalty=float(weights @ cvar),
        )
