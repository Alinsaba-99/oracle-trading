"""Portfolio optimisation — PyPortfolioOpt wrappers.

All public methods accept Polars DataFrames and convert internally.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import polars as pl

from analytics.common.converters import to_pandas


class PortfolioOptimizer:
    """Portfolio optimisation using the PyPortfolioOpt library.

    Usage
    -----
        opt = PortfolioOptimizer()
        returns = pl.DataFrame(...)
        weights = opt.efficient_frontier(returns)
        hrp_weights = opt.hrp(returns)
        bl_weights = opt.black_litterman(returns, views={"AAPL": 0.15})
    """

    # ── helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _validate_returns(returns: pl.DataFrame) -> pd.DataFrame:
        """Convert Polars return columns to pandas and validate."""

        if returns is None or len(returns) == 0:
            msg = "Returns DataFrame is empty"
            raise ValueError(msg)

        # Identify asset columns (skip known time/date columns).
        skip = {"timestamp", "date", "datetime", "time"}
        asset_cols = [c for c in returns.columns if c.lower() not in skip]

        if not asset_cols:
            msg = "No asset columns found in returns DataFrame"
            raise ValueError(msg)

        pdf: pd.DataFrame = to_pandas(returns.select(asset_cols))
        pdf = pdf.dropna(how="all")

        if pdf.empty:
            msg = "Returns DataFrame is empty after dropping NaN rows"
            raise ValueError(msg)

        return pdf

    # ── public API ──────────────────────────────────────────────────

    def efficient_frontier(self, returns: pl.DataFrame, **kwargs: Any) -> dict[str, float]:
        """Mean-variance optimisation (max Sharpe).

        Args:
            returns: Polars DataFrame with asset **return** columns
                     (not prices).  May include a *timestamp* column
                     which is ignored.
            **kwargs: Forwarded to ``EfficientFrontier.max_sharpe()``.

        Returns:
            Dict mapping asset names to target weights.
        """
        import numpy as np
        from pypfopt import EfficientFrontier

        pdf = self._validate_returns(returns)

        # *pdf* contains daily returns (not prices), so we compute the
        # annualised covariance and expected returns directly.
        cov = np.cov(pdf.values, rowvar=False) * 252
        cov_matrix = pd.DataFrame(cov, index=pdf.columns, columns=pdf.columns)
        mu = pdf.mean() * 252  # annualised mean return

        ef = EfficientFrontier(mu, cov_matrix)
        weights = ef.max_sharpe(**kwargs)

        return {k: float(v) for k, v in weights.items()}

    def hrp(self, returns: pl.DataFrame) -> dict[str, float]:
        """Hierarchical Risk Parity.

        Args:
            returns: Polars DataFrame with asset return columns.

        Returns:
            Dict mapping asset names to target weights.
        """
        import scipy.cluster.hierarchy as sch
        from pypfopt import HRPOpt

        # PyPortfolioOpt 1.6.0 references sch._LINKAGE_METHODS which was
        # removed in scipy >= 1.15.  Patch it back for compatibility.
        _hrp_linkage_methods = [
            "single",
            "complete",
            "average",
            "weighted",
            "centroid",
            "median",
            "ward",
        ]
        if not hasattr(sch, "_LINKAGE_METHODS"):
            sch._LINKAGE_METHODS = _hrp_linkage_methods

        pdf = self._validate_returns(returns)

        hrp = HRPOpt(pdf)
        weights = hrp.optimize()

        return {k: float(v) for k, v in weights.items()}

    def black_litterman(
        self, returns: pl.DataFrame, views: dict[str, float] | None = None
    ) -> dict[str, float]:
        """Black-Litterman model.

        Combines a market-implied prior with optional absolute investor
        views.  When *views* is ``None`` (or empty), the posterior
        collapses to the prior and the result is equivalent to a
        mean-variance optimisation on the historical mean returns.

        Args:
            returns: Polars DataFrame with asset return columns.
            views: Optional dict ``{asset_name: expected_return}``.

            Dict mapping asset names to target weights.
        """
        import numpy as np
        from pypfopt import BlackLittermanModel, EfficientFrontier

        pdf = self._validate_returns(returns)

        # *pdf* contains daily returns, so compute covariance and
        # prior returns directly.
        cov = np.cov(pdf.values, rowvar=False) * 252
        cov_matrix = pd.DataFrame(cov, index=pdf.columns, columns=pdf.columns)
        prior = pdf.mean() * 252  # annualised mean return

        # Determine absolute views — if provided, use them; otherwise
        # Black-Litterman with no views collapses to the prior.
        absolute_views: dict[str, float] | None = (
            {k: v for k, v in views.items() if k in pdf.columns} if views else None
        )
        if absolute_views:
            bl = BlackLittermanModel(cov_matrix, pi=prior, absolute_views=absolute_views)
        else:
            bl = BlackLittermanModel(cov_matrix, pi=prior, absolute_views={})

        bl_returns = bl.bl_returns()

        ef = EfficientFrontier(bl_returns, cov_matrix)
        weights = ef.max_sharpe()

        return {k: float(v) for k, v in weights.items()}
