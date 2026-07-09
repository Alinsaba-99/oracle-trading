"""PELT (Pruned Exact Linear Time) changepoint detection.

Uses ``ruptures.Pelt`` with the ``"rbf"`` kernel to detect structural breaks.
"""

from __future__ import annotations

import numpy as np
import ruptures as rpt

from analytics.common.errors import RegimeError


class PELTDetector:
    """Changepoint detector using ruptures.Pelt.

    Parameters
    ----------
    model : str
        Cost function (``"rbf"``, ``"l1"``, ``"l2"``, …). Default ``"rbf"``.
    min_window : int
        Minimum segment length for a changepoint.
    """

    def __init__(self, model: str = "rbf", min_window: int = 5) -> None:
        self._model_name = model
        self._min_window = min_window
        self._changepoints: list[int] = []
        self._algo: rpt.Pelt | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, data: np.ndarray, pen: int = 10) -> PELTDetector:
        """Fit the PELT algorithm.

        Parameters
        ----------
        data : np.ndarray
            1-D or 2-D time series.
        pen : int
            Penalty value (default 10).

        Returns
        -------
        PELTDetector
        """
        data = self._validate(data)
        if data.shape[0] < self._min_window * 2:
            raise RegimeError(
                f"Need at least {self._min_window * 2} samples for PELT, got {data.shape[0]}"
            )
        self._algo = rpt.Pelt(model=self._model_name, min_size=self._min_window).fit(data)
        self._changepoints = list(self._algo.predict(pen=pen))
        _trim_trailing_boundary(self._changepoints, data.shape[0])
        return self

    def get_changepoints(self) -> list[int]:
        """Return sorted list of changepoint indices in the fitted data."""
        return list(self._changepoints)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(data: np.ndarray) -> np.ndarray:
        if not isinstance(data, np.ndarray):
            raise RegimeError(f"Expected np.ndarray, got {type(data).__name__}")
        if data.ndim == 0 or data.size == 0:
            raise RegimeError("Empty or scalar array passed to PELTDetector")
        if np.any(~np.isfinite(data)):
            raise RegimeError("PELTDetector input contains NaN or Inf values")
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return data


def _trim_trailing_boundary(changepoints: list[int], n_samples: int) -> None:
    """Remove the artificial last-sample boundary ruptures always appends."""
    while changepoints and changepoints[-1] >= n_samples:
        changepoints.pop()
