from __future__ import annotations

"""Weighted ensemble voter with hysteresis.

Aggregates votes from all six detectors using fixed weights, enforces a
confidence threshold, and provides hysteresis to prevent regime flapping.
"""


# Default detector weights (sum = 1.0)
_DEFAULT_WEIGHTS: dict[str, float] = {
    "macro": 0.3,
    "hmm": 0.2,
    "vol": 0.2,
    "corr": 0.1,
    "bocd": 0.1,
    "pelt": 0.1,
}


class EnsembleVoter:
    """Weighted ensemble voting with hysteresis and confidence threshold.

    Parameters
    ----------
    min_confidence : float
        Minimum weighted confidence required to transition to a new regime.
    min_bars : int
        Minimum number of bars the ensemble must remain in a regime before
        switching (hysteresis).
    weights : dict[str, float] | None
        Per-detector weights.  Keys are detector names; values sum to 1.0.
    """

    def __init__(
        self,
        min_confidence: float = 0.6,
        min_bars: int = 5,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._min_confidence = min_confidence
        self._min_bars = min_bars
        self._weights = dict(weights) if weights else dict(_DEFAULT_WEIGHTS)
        self._votes: list[tuple[str, str, float]] = []
        self._previous_regime: str | None = None
        self._bars_since_change: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_vote(self, detector_name: str, regime: str, confidence: float) -> None:
        """Register a single detector's vote.

        Parameters
        ----------
        detector_name : str
            Detector identifier (e.g. ``"hmm"``, ``"vol"``).
        regime : str
            Voted regime label (e.g. ``"bull"``, ``"bear"``).
        confidence : float
            How confident the detector is in its vote [0, 1].
        """
        self._votes.append((detector_name, regime, confidence))

    def resolve(self) -> tuple[str, float, dict[str, object]]:
        """Aggregate votes and return the final regime decision.

        Returns
        -------
        regime : str
            Winning regime label after hysteresis.
        confidence : float
            Weighted confidence of the winning regime.
        details : dict
            Full breakdown for debugging / logging.
        """
        if not self._votes:
            return ("unknown", 0.0, _empty_details())

        # 1. Aggregate weighted votes per regime label
        scores: dict[str, float] = {}
        vote_details: list[dict[str, object]] = []
        for name, regime, conf in self._votes:
            weight = self._weights.get(name, 0.1)
            weighted = weight * conf
            scores[regime] = scores.get(regime, 0.0) + weighted
            vote_details.append(
                {
                    "detector": name,
                    "regime": regime,
                    "confidence": conf,
                    "weight": weight,
                    "weighted": round(weighted, 4),
                }
            )

        # 2. Find the winner
        winner = max(scores, key=scores.__getitem__)
        confidence = scores[winner]

        # 3. Hysteresis gate
        effective_regime, transition = self._apply_hysteresis(winner, confidence)

        details: dict[str, object] = {
            "scores": {k: round(v, 4) for k, v in scores.items()},
            "winner": winner,
            "winner_confidence": round(confidence, 4),
            "votes": vote_details,
            "effective_regime": effective_regime,
            "transition": transition,
            "bars_since_change": self._bars_since_change,
            "previous_regime": self._previous_regime,
        }
        return (effective_regime, confidence, details)

    def reset(self) -> None:
        """Clear accumulated votes for the next bar.

        Does **not** reset hysteresis state (``previous_regime`` and
        ``bars_since_change`` are retained across bars).
        """
        self._votes.clear()

    # ------------------------------------------------------------------
    # Hysteresis
    # ------------------------------------------------------------------

    def _apply_hysteresis(self, winner: str, confidence: float) -> tuple[str, bool]:
        """Decide whether to transition regimes based on confidence + time."""
        transition = False
        effective_regime = winner

        if self._previous_regime is None:
            # First ever vote — accept immediately
            self._previous_regime = winner
            return (effective_regime, transition)

        if winner == self._previous_regime:
            self._bars_since_change += 1
            return (effective_regime, transition)

        # winner != previous_regime
        if confidence < self._min_confidence:
            # Not confident enough — stay
            effective_regime = self._previous_regime
            self._bars_since_change += 1
        elif self._bars_since_change < self._min_bars:
            # Hysteresis — stay a bit longer
            effective_regime = self._previous_regime
            self._bars_since_change += 1
        else:
            # Transition allowed
            self._previous_regime = winner
            self._bars_since_change = 0
            transition = True

        return (effective_regime, transition)


def _empty_details() -> dict[str, object]:
    return {
        "scores": {},
        "winner": None,
        "winner_confidence": 0.0,
        "votes": [],
        "effective_regime": "unknown",
        "transition": False,
        "bars_since_change": 0,
        "previous_regime": None,
    }
