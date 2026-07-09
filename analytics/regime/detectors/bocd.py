"""Bayesian Online Changepoint Detection via binary segmentation.

Wraps ``ruptures.Binseg`` as a practical approximation of Bayesian online
changepoint detection.  Identifies structural break points in a time series.
"""

from __future__ import annotations

import numpy as np
import ruptures as rpt

from analytics.common.errors import RegimeError


class BOCDDetector:
    """Changepoint detector using ruptures.Binseg (binary segmentation).

    Parameters
    ----------
    model : str
        Cost function (``"l1"``, ``"l2"``, ``"rbf"``, …).  Default ``"l2"``.
    min_window : int
        Minimum segment length for a changepoint.
    """

    def __init__(self, model: str = "l2", min_window: int = 5) -> None:
        self._model_name = model
        self._min_window = min_window
        self._changepoints: list[int] = []
        self._algo: rpt.Binseg | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, data: np.ndarray, pen: int | None = None) -> BOCDDetector:
        """Fit the binary segmentation algorithm.

        Parameters
        ----------
        data : np.ndarray
            1-D or 2-D time series.
        pen : int | None
            Penalty value (default 10).

        Returns
        -------
        BOCDDetector
        """
        data = self._validate(data)
        if data.shape[0] < self._min_window * 2:
            raise RegimeError(
                f"Need at least {self._min_window * 2} samples for BOCD, got {data.shape[0]}"
            )
        self._algo = rpt.Binseg(model=self._model_name, min_size=self._min_window).fit(data)
        self._changepoints = list(self._algo.predict(pen=pen or 10))
        _trim_trailing_boundary(self._changepoints, data.shape[0])
        return self

    def get_changepoints(self) -> list[int]:
        """Return sorted list of changepoint indices in the fitted data."""
        return list(self._changepoints)

    def has_changed(self) -> bool:
        """``True`` when at least one changepoint was detected."""
        return len(self._changepoints) > 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(data: np.ndarray) -> np.ndarray:
        if not isinstance(data, np.ndarray):
            raise RegimeError(f"Expected np.ndarray, got {type(data).__name__}")
        if data.ndim == 0 or data.size == 0:
            raise RegimeError("Empty or scalar array passed to BOCDDetector")
        if np.any(~np.isfinite(data)):
            raise RegimeError("BOCDDetector input contains NaN or Inf values")
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return data


def _trim_trailing_boundary(changepoints: list[int], n_samples: int) -> None:
    """Remove the artificial last-sample boundary ruptures always appends."""
    while changepoints and changepoints[-1] >= n_samples:
        changepoints.pop()
