"""HMM-based regime detector.

Fits a GaussianHMM on returns and decodes the most likely hidden state
sequence. Each state is mapped to a human-readable market regime label.
"""

from __future__ import annotations

import numpy as np
from hmmlearn import hmm

from analytics.common.errors import RegimeError

# Default mapping from state index to regime label.
# The actual assignment depends on the fitted means; this is initial mapping.
_STATE_MAP: dict[int, str] = {0: "bull", 1: "bear", 2: "choppy", 3: "volatile"}


class HMMDetector:
    """Hidden Markov Model for market regime detection.

    Parameters
    ----------
    n_states : int
        Number of hidden states (default 4 → bull, bear, choppy, volatile).
    random_state : int
        Seed for reproducibility.
    """

    def __init__(self, n_states: int = 4, random_state: int = 42) -> None:
        self.n_states = n_states
        self._random_state = random_state
        self._model: hmm.GaussianHMM | None = None
        self._state_map: dict[int, str] = {
            i: _STATE_MAP.get(i, f"state_{i}") for i in range(n_states)
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, returns: np.ndarray) -> HMMDetector:
        """Fit the HMM on historical returns.

        Parameters
        ----------
        returns : np.ndarray
            Shape ``(n_samples,)`` or ``(n_samples, n_features)``.

        Returns
        -------
        HMMDetector
        """
        returns = self._validate(returns)
        if returns.shape[0] < self.n_states * 2:
            raise RegimeError(
                f"Need at least {self.n_states * 2} samples to fit HMM, got {returns.shape[0]}"
            )
        self._model = hmm.GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            random_state=self._random_state,
            n_iter=1000,
            tol=1e-4,
            init_params="stmc",
        )
        self._model.fit(returns)
        _remap_states_by_mean(self._model, self._state_map)
        return self

    def predict(self, returns: np.ndarray) -> int:
        """Return the decoded state index for the last observation.

        Parameters
        ----------
        returns : np.ndarray
            Shape ``(n_samples,)`` or ``(n_samples, n_features)``.

        Returns
        -------
        int
            Hidden state index (0 … n_states-1).
        """
        if self._model is None:
            raise RegimeError("HMM not fitted — call fit() first")
        returns = self._validate(returns)
        return int(self._model.predict(returns)[-1])

    def state_to_regime(self, state: int) -> str:
        """Map a numeric state index to a human-readable regime label."""
        return self._state_map.get(state, f"state_{state}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(returns: np.ndarray) -> np.ndarray:
        if not isinstance(returns, np.ndarray):
            raise RegimeError(f"Expected np.ndarray, got {type(returns).__name__}")
        if returns.ndim == 0 or returns.size == 0:
            raise RegimeError("Empty or scalar array passed to HMMDetector")
        if returns.ndim == 1:
            returns = returns.reshape(-1, 1)
        if np.any(~np.isfinite(returns)):
            raise RegimeError("HMMDetector input contains NaN or Inf values")
        return returns


def _remap_states_by_mean(model: hmm.GaussianHMM, state_map: dict[int, str]) -> None:
    """Re-order ``state_map`` so that low-mean states → bear/choppy and
    high-mean states → bull/volatile based on the fitted means.

    This is a heuristic — HMM state indices are arbitrary after fitting.
    """
    if model.n_components != len(state_map):
        return  # custom mapping, leave as-is

    means = model.means_.ravel()
    sorted_idx = np.argsort(means)

    # ordered labels from most-negative-mean → most-positive-mean
    ordered_labels = ["bear", "choppy", "bull", "volatile"]
    if len(ordered_labels) < len(state_map):
        ordered_labels += [f"state_{i}" for i in range(len(ordered_labels), len(state_map))]

    for new_idx, orig_idx in enumerate(sorted_idx):
        label = ordered_labels[new_idx] if new_idx < len(ordered_labels) else f"state_{orig_idx}"
        state_map[int(orig_idx)] = label
