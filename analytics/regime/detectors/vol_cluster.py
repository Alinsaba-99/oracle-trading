"""Volatility-based regime clustering.

Uses KMeans on rolling volatility features to categorise market conditions
into discrete volatility regimes (low / normal / high / panic).
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from analytics.common.errors import RegimeError


class VolClusterDetector:
    """Cluster rolling volatility features into regime categories.

    Parameters
    ----------
    n_clusters : int
        Number of volatility regimes (default 3 → low / normal / high).
    window : int
        Rolling window for feature computation (default 20).
    """

    def __init__(self, n_clusters: int = 3, window: int = 20) -> None:
        self.n_clusters = n_clusters
        self._window = window
        self._model: KMeans | None = None
        self._scaler: StandardScaler = StandardScaler()
        self._label_map: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, returns: np.ndarray) -> VolClusterDetector:
        """Fit KMeans on rolling volatility features from historical returns.

        Parameters
        ----------
        returns : np.ndarray
            1-D array of returns.

        Returns
        -------
        VolClusterDetector
        """
        returns = self._validate(returns)
        if len(returns) < self._window + self.n_clusters:
            raise RegimeError(
                f"Need at least {self._window + self.n_clusters} samples to fit "
                f"VolClusterDetector, got {len(returns)}"
            )
        features = _compute_vol_features(returns, self._window)
        scaled = self._scaler.fit_transform(features)
        self._model = KMeans(n_clusters=self.n_clusters, random_state=42, n_init="auto")
        self._model.fit(scaled)
        self._label_map = _build_label_map(self._model, self.n_clusters)
        return self

    def predict(self, returns: np.ndarray) -> str:
        """Return the volatility regime for recent returns.

        Parameters
        ----------
        returns : np.ndarray
            Recent returns (uses the last ``window`` elements).

        Returns
        -------
        str
            ``"low"``, ``"normal"``, ``"high"``, or ``"panic"``.
        """
        if self._model is None:
            raise RegimeError("VolClusterDetector not fitted — call fit() first")
        returns = self._validate(returns)
        if len(returns) < self._window + 1:
            return "unknown"
        feature = _compute_vol_features(returns, self._window)
        if len(feature) == 0:
            return "unknown"
        scaled = self._scaler.transform(feature[-1:])
        label_idx = int(self._model.predict(scaled)[0])
        return self._label_map[label_idx] if label_idx < len(self._label_map) else "unknown"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(returns: np.ndarray) -> np.ndarray:
        if not isinstance(returns, np.ndarray):
            raise RegimeError(f"Expected np.ndarray, got {type(returns).__name__}")
        if returns.ndim == 0 or returns.size == 0:
            raise RegimeError("Empty or scalar array passed to VolClusterDetector")
        if np.any(~np.isfinite(returns)):
            raise RegimeError("VolClusterDetector input contains NaN or Inf values")
        return returns.ravel()


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _compute_vol_features(returns: np.ndarray, window: int) -> np.ndarray:
    """Build a feature matrix from rolling volatility statistics.

    Each row corresponds to one sliding window and contains:
      - raw volatility (std)
      - mean absolute return
      - 95th percentile of absolute return
    """
    n = len(returns)
    features = []
    for i in range(window, n):
        chunk = returns[i - window : i]
        rv = float(np.std(chunk, ddof=1))
        features.append(
            [rv, float(np.mean(np.abs(chunk))), float(np.percentile(np.abs(chunk), 95))]
        )
    return np.asarray(features, dtype=float)


def _build_label_map(model: KMeans, n_clusters: int) -> list[str]:
    """Order cluster labels by ascending cluster-centre volatility."""
    centers = model.cluster_centers_
    labelled = [(i, float(centers[i][0])) for i in range(n_clusters)]
    labelled.sort(key=lambda x: x[1])

    pool = ["low", "normal", "high", "panic"]
    label_map = [""] * n_clusters
    for rank, (cluster_idx, _) in enumerate(labelled):
        label_map[cluster_idx] = pool[rank] if rank < len(pool) else f"cluster_{cluster_idx}"
    return label_map
