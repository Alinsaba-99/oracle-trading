"""Portfolio construction — HRP (Hierarchical Risk Parity) + covariance.

Wraps PyPortfolioOpt's ``HRPOpt`` and ``risk_models`` to compute
per-strategy allocation weights from historical return series.

Integration point: the RegimeAwareEnsemble uses these weights instead
of fixed binary routing (one specialist flat-out replaces another).
With HRP, multiple strategies coexist with fractional weights.

Usage::

    from analytics.portfolio.hrp import compute_hrp_weights

    returns_df = pd.DataFrame({
        "EmaTrend": [...],
        "RsiReversion": [...],
        "DonchianBreakout": [...],
    })
    weights = compute_hrp_weights(returns_df)
    # {"EmaTrend": 0.25, "RsiReversion": 0.45, "DonchianBreakout": 0.30}
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("oracle.analytics.portfolio.hrp")


def compute_hrp_weights(
    returns_df: pd.DataFrame, *, method: str = "single", covariance_estimator: str = "ledoit_wolf"
) -> dict[str, float]:
    """Compute Hierarchical Risk Parity weights for a collection of strategies.

    HRP (López de Prado 2016) uses hierarchical clustering to build a
    diversified portfolio without requiring a full covariance matrix
    inversion. It naturally handles highly-correlated strategies by
    grouping them and allocating within/between clusters.

    Args:
        returns_df: DataFrame where each column is a strategy and
            each row is a per-bar return.  Index can be datetime or
            positional.
        method: Linkage method for hierarchical clustering
            (``"single"``, ``"ward"``, ``"average"``, ``"complete"``).
            ``"single"`` (default) is the fastest and most commonly used
            for HRP.
        covariance_estimator: Which covariance estimator to use
            (``"ledoit_wolf"``, ``"sample"``, ``"shrunk"``).
            ``"ledoit_wolf"`` shrinks the sample covariance toward a
            constant-correlation target, which is robust with few
            observations.

    Returns:
        Dict mapping column name to allocation weight (sums to 1.0).
        Strategies with zero or negative allocation are excluded.

    Raises:
        ValueError: if ``returns_df`` has fewer than 2 columns or
            fewer than 5 rows.
    """
    if returns_df.shape[1] < 2:
        raise ValueError("HRP requires at least 2 strategies")
    if returns_df.shape[0] < 3:
        raise ValueError(f"HRP requires at least 3 rows, got {returns_df.shape[0]}")

    try:
        from pypfopt import HRPOpt, risk_models
    except ImportError:
        logger.warning("pypfopt not installed — install with ``uv add pypfopt``")
        return _fallback_equal_weight(returns_df)

    # Estimate covariance matrix
    try:
        if covariance_estimator == "ledoit_wolf":
            cov = risk_models.CovarianceShrinkage(returns_df).ledoit_wolf()
        elif covariance_estimator == "shrunk":
            cov = risk_models.CovarianceShrinkage(returns_df).shrunk_covariance()
        else:
            cov = risk_models.sample_cov(returns_df)
    except Exception as exc:
        logger.warning("Covariance estimation failed: %s; using equal weights", exc)
        return _fallback_equal_weight(returns_df)

    # Build HRP portfolio
    try:
        hrp = HRPOpt(returns_df, cov)
        weights = hrp.optimize(linkage_method=method)
    except Exception as exc:
        logger.warning("HRP optimization failed: %s; using equal weights", exc)
        return _fallback_equal_weight(returns_df)

    # Filter out zero/negative weights
    result = {k: round(float(v), 4) for k, v in weights.items() if v > 0}
    return result


def compute_equal_weights(strategies: list[str]) -> dict[str, float]:
    """Return equal weights for a list of strategies (1/N)."""
    w = round(1.0 / max(len(strategies), 1), 4)
    return dict.fromkeys(strategies, w)


def _fallback_equal_weight(returns_df: pd.DataFrame) -> dict[str, float]:
    """Fallback to equal weighting when PyPortfolioOpt is unavailable."""
    return compute_equal_weights(list(returns_df.columns))


# ── Convenience: build returns from ResearchMemory ─────────────────────


def build_returns_from_memory(
    memory: object,  # ResearchMemory
    specialist_filter: str | None = None,
    window: int = 500,
) -> pd.DataFrame:
    """Build per-bar returns DataFrame from ResearchMemory decisions.

    Reads decision records (specialist, pnl, timestamp) and pivots them
    into columnar format suitable for HRP.

    Args:
        memory: ``ResearchMemory`` instance.
        specialist_filter: If set, only include this specialist.
        window: Number of recent rows to scan.

    Returns:
        DataFrame with columns = specialists, rows = per-bar P&L.
        Index is positional (0..N-1) — the ordering preserves time.
    """
    import polars as pl

    decisions = memory.get_recent_decisions(n=window)
    if not decisions:
        return pd.DataFrame()

    records = [
        {"specialist": d.get("specialist", "unknown"), "pnl": d.get("pnl", 0.0)}
        for d in decisions
        if d.get("pnl") is not None
    ]

    if not records:
        return pd.DataFrame()

    df = pl.DataFrame(records)

    if specialist_filter is not None:
        df = df.filter(pl.col("specialist") == specialist_filter)

    # Pivot: one column per specialist, keeping ordering
    pdf = df.to_pandas()
    pdf["seq"] = range(len(pdf))
    pivoted = pdf.pivot_table(
        index="seq", columns="specialist", values="pnl", aggfunc="sum"
    ).fillna(0.0)

    return pivoted


__all__ = ["build_returns_from_memory", "compute_equal_weights", "compute_hrp_weights"]
