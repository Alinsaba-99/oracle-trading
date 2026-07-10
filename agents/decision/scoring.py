"""Deterministic vote aggregation and consensus detection.

Aggrega voti degli analyst con pesi basati su confidence + accuratezza storica.
100% deterministico — nessun LLM.
"""

from __future__ import annotations

from typing import Any

from agents.confidence import ConfidenceTracker
from agents.protocol import AnalystSignal

__all__ = ["SignalScorer"]


class SignalScorer:
    """Aggrega voti degli analyst con pesi basati su confidence + accuratezza storica.
    100% deterministico — nessun LLM.
    """

    def __init__(self, confidence_tracker: Any | None = None) -> None:
        self._tracker: ConfidenceTracker | None = confidence_tracker

    def weighted_vote(self, signals: list[AnalystSignal]) -> tuple[float, float, float]:
        """Returns (buy_weight, sell_weight, hold_weight) normalized sum.

        Each signal contributes its confidence as weight.
        If ConfidenceTracker available, adjust by calibration_weight.
        """
        buy = 0.0
        sell = 0.0
        hold = 0.0

        for s in signals:
            weight = s.vote.confidence
            if self._tracker is not None:
                weight = self._tracker.calibrated_confidence(str(s.source), weight)
            if s.vote.direction == "buy":
                buy += weight
            elif s.vote.direction == "sell":
                sell += weight
            elif s.vote.direction == "hold":
                hold += weight

        total = buy + sell + hold or 1.0
        return (buy / total, sell / total, hold / total)

    def consensus(self, signals: list[AnalystSignal], threshold: float = 0.5) -> str | None:
        """Return 'buy', 'sell', 'hold' if above threshold, None if no consensus."""
        buy_w, sell_w, hold_w = self.weighted_vote(signals)
        if buy_w > threshold:
            return "buy"
        if sell_w > threshold:
            return "sell"
        if hold_w > threshold:
            return "hold"
        return None
