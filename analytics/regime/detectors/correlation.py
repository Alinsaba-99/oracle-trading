"""Pairwise correlation regime detection.

Computes rolling average pairwise correlation across a universe of
instruments and classifies the market correlation regime
(risk-on / risk-off / mixed).
"""

from __future__ import annotations

import numpy as np

from analytics.common.errors import RegimeError


class CorrelationDetector:
    """Rolling pairwise correlation across instruments.

    This detector does **not** require a fit step — call ``compute()``
    directly on a price matrix.
    """

    def compute(self, prices_matrix: np.ndarray, window: int = 20) -> float:
        """Compute the average pairwise correlation over a rolling window.

        Parameters
        ----------
        prices_matrix : np.ndarray
            2-D array ``(n_periods, n_instruments)`` of price levels.
        window : int
            Rolling window length (default 20).

        Returns
        -------
        float
            Average pairwise correlation (nan → 0.0).
        """
        prices_matrix = self._validate(prices_matrix)
        n_periods, n_assets = prices_matrix.shape

        if n_periods < window or n_assets < 2:
            return 0.0

        recent = prices_matrix[-window:, :]
        log_returns = np.diff(np.log(np.maximum(recent, 1e-12)), axis=0)

        if log_returns.shape[0] < 2 or np.all(~np.isfinite(log_returns)):
            return 0.0

        corr_matrix = np.corrcoef(log_returns.T)
        upper = np.triu_indices(n_assets, k=1)
        values = corr_matrix[upper]
        valid = values[np.isfinite(values)]
        if len(valid) == 0:
            return 0.0
        return float(np.mean(valid))

    @staticmethod
    def classify(avg_corr: float) -> str:
        """Classify the average pairwise correlation.

        Parameters
        ----------
        avg_corr : float
            Average pairwise correlation.

        Returns
        -------
        str
            ``"risk_on"`` (> 0.5), ``"risk_off"`` (< -0.2), or ``"mixed"``.
        """
        if avg_corr > 0.5:
            return "risk_on"
        if avg_corr < -0.2:
            return "risk_off"
        return "mixed"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(prices_matrix: np.ndarray) -> np.ndarray:
        if not isinstance(prices_matrix, np.ndarray):
            raise RegimeError(f"Expected np.ndarray, got {type(prices_matrix).__name__}")
        if prices_matrix.ndim != 2 or prices_matrix.size == 0:
            if prices_matrix.size == 0:
                raise RegimeError("Empty prices_matrix passed to CorrelationDetector")
            raise RegimeError(
                f"prices_matrix must be 2-D (n_periods, n_instruments), "
                f"got {prices_matrix.ndim} dimensions"
            )
        return prices_matrix
