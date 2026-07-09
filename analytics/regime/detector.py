# ruff: noqa: E402
from __future__ import annotations

"""RegimeDetector orchestrator.

Runs all six detectors on a batch of market data, normalises their outputs
into a common regime vocabulary, and resolves the final regime through the
``EnsembleVoter``.
"""


import numpy as np

from analytics.common.errors import RegimeError
from analytics.regime.config import RegimeSettings
from analytics.regime.detectors import (
    BOCDDetector,
    CorrelationDetector,
    HMMDetector,
    PELTDetector,
    VolClusterDetector,
)
from analytics.regime.ensemble import EnsembleVoter

# Maps from sub-regime labels emitted by individual detectors to the
# canonical regime vocabulary: bull / bear / choppy / volatile.
_VOL_TO_REGIME: dict[str, str] = {
    "low": "bull",
    "normal": "choppy",
    "high": "volatile",
    "panic": "bear",
}

_CORR_TO_REGIME: dict[str, str] = {"risk_on": "bull", "risk_off": "bear", "mixed": "choppy"}


class RegimeDetector:
    """Orchestrator — runs all six detectors and returns the ensemble regime.

    Usage::

        detector = RegimeDetector(settings).fit(returns, prices)
        regime, confidence, details = detector.detect(returns, prices)

    Parameters
    ----------
    settings : RegimeSettings | None
    """

    def __init__(self, settings: RegimeSettings | None = None) -> None:
        self._settings = settings or RegimeSettings()
        self._voter = EnsembleVoter(
            min_confidence=self._settings.ensemble_min_confidence,
            min_bars=self._settings.ensemble_min_bars,
        )

        # Lazy-initialised detectors
        self._hmm: HMMDetector | None = None
        self._bocd: BOCDDetector = BOCDDetector()
        self._pelt: PELTDetector = PELTDetector()
        self._vol_cluster: VolClusterDetector | None = None
        self._correlation: CorrelationDetector = CorrelationDetector()

        self._fitted: bool = False

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, returns: np.ndarray, prices: np.ndarray | None = None) -> RegimeDetector:
        """Fit all applicable detectors on historical data.

        Parameters
        ----------
        returns : np.ndarray
            1-D array of historical returns.
        prices : np.ndarray | None
            2-D price matrix ``(n_periods, n_assets)`` (optional — used to
            pre-compute fitted correlation stats in future).

        Returns
        -------
        RegimeDetector
        """
        if not isinstance(returns, np.ndarray) or returns.size == 0:
            raise RegimeError("Cannot fit RegimeDetector on empty or non-array data")

        returns_1d = returns.ravel()

        self._hmm = HMMDetector(n_states=self._settings.hmm_n_states).fit(returns_1d)
        self._bocd.fit(returns)
        self._pelt.fit(returns)
        self._vol_cluster = VolClusterDetector(n_clusters=self._settings.vol_cluster_n).fit(
            returns_1d
        )

        _ = prices  # reserved for future correlation pre-fit
        self._fitted = True
        return self

    # ------------------------------------------------------------------
    # Detect
    # ------------------------------------------------------------------

    def detect(
        self, returns: np.ndarray, prices: np.ndarray | None = None
    ) -> tuple[str, float, dict[str, object]]:
        """Run all six detectors on recent data and return the ensemble regime.

        Parameters
        ----------
        returns : np.ndarray
            Recent returns (1-D).  Pass the **same** array used during
            ``fit()`` (or a longer one) — the full history is used for HMM
            decoding.
        prices : np.ndarray | None
            2-D price matrix ``(n_periods, n_assets)`` for correlation
            computation.  When ``None`` the correlation detector contributes
            zero confidence.

        Returns
        -------
        regime : str
        confidence : float
        details : dict
        """
        if not self._fitted:
            raise RegimeError("RegimeDetector not fitted — call fit() first")

        self._voter.reset()

        # 1. HMM — state index → regime label
        state = self._hmm.predict(returns)  # type: ignore[union-attr]
        hmm_regime = self._hmm.state_to_regime(state)  # type: ignore[union-attr]
        self._voter.add_vote("hmm", hmm_regime, 0.8)

        # 2. Volatility cluster
        vol_raw = self._vol_cluster.predict(returns)  # type: ignore[union-attr]
        vol_regime = _VOL_TO_REGIME.get(vol_raw, "choppy")
        self._voter.add_vote("vol", vol_regime, 0.7)

        # 3. BOCD — changepoint signal
        bocd_regime, bocd_conf = _changepoint_vote(
            self._bocd.has_changed(), self._bocd.get_changepoints(), returns
        )
        self._voter.add_vote("bocd", bocd_regime, bocd_conf)

        # 4. PELT — changepoint signal
        pelt_regime, pelt_conf = _changepoint_vote(
            len(self._pelt.get_changepoints()) > 0, self._pelt.get_changepoints(), returns
        )
        self._voter.add_vote("pelt", pelt_regime, pelt_conf)

        # 5. Correlation
        corr_regime, corr_conf = _correlation_vote(
            prices, self._correlation, self._settings.correlation_window
        )
        self._voter.add_vote("corr", corr_regime, corr_conf)

        # 6. Macro (placeholder — fed from M8 in production)
        self._voter.add_vote("macro", "choppy", 0.3)

        return self._voter.resolve()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def fitted(self) -> bool:
        """``True`` once ``fit()`` has been called."""
        return self._fitted


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _changepoint_vote(
    has_changed: bool, changepoints: list[int], returns: np.ndarray
) -> tuple[str, float]:
    """Derive a regime vote from a changepoint detector.

    When a changepoint is detected near the end of the series, the recent
    return sign determines bull / bear.  Otherwise vote choppy with low
    confidence.
    """
    if not has_changed or not changepoints:
        return ("choppy", 0.5)

    cp = max(changepoints)
    r = returns.ravel()
    recent = r[max(cp - 5, 0) :] if len(r) > 0 else r
    mean_recent = float(np.mean(recent)) if len(recent) > 0 else 0.0

    if mean_recent > 0.001:
        return ("bull", 0.55)
    if mean_recent < -0.001:
        return ("bear", 0.55)
    return ("volatile", 0.5)


def _correlation_vote(
    prices: np.ndarray | None, detector: CorrelationDetector, window: int
) -> tuple[str, float]:
    """Compute the correlation regime vote from a price matrix."""
    if prices is None:
        return ("choppy", 0.0)

    avg_corr = detector.compute(prices, window=window)
    corr_label = detector.classify(avg_corr)
    corr_regime = _CORR_TO_REGIME.get(corr_label, "choppy")
    corr_conf = min(0.8, max(0.3, abs(avg_corr)))
    return (corr_regime, corr_conf)
