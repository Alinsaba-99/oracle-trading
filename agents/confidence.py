"""Tracks historical accuracy of LLM signals for confidence calibration."""

from __future__ import annotations

from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger("oracle.agents")

__all__ = ["ConfidenceTracker"]


@dataclass
class _PredictionRecord:
    """A single prediction-observation pair for calibration tracking."""

    predicted: str
    actual: str
    confidence: float


class ConfidenceTracker:
    """Tracks historical accuracy of LLM signals for confidence calibration.

    For each agent type, records how often the LLM's directional prediction
    was correct versus actual market movement. Produces calibration weights
    used by SignalScorer to adjust vote weights.
    """

    def __init__(self) -> None:
        self._history: dict[str, list[_PredictionRecord]] = {}

    def record(self, agent: str, predicted: str, actual: str, confidence: float) -> None:
        """Record a single prediction-observation pair for an agent."""
        if agent not in self._history:
            self._history[agent] = []
        self._history[agent].append(
            _PredictionRecord(predicted=predicted, actual=actual, confidence=confidence)
        )

    def accuracy(self, agent: str, min_samples: int = 5) -> float:
        """Return the historical accuracy for an agent.

        Returns 0.0 if fewer than min_samples records exist.
        """
        records = self._history.get(agent, [])
        if len(records) < min_samples:
            return 0.0
        correct = sum(1 for r in records if r.predicted == r.actual)
        return correct / len(records)

    def calibration_weight(self, agent: str) -> float:
        """Return a weight based on historical accuracy.

        Returns 1.0 if insufficient history (< 5 samples).
        Otherwise returns the raw accuracy.
        """
        records = self._history.get(agent, [])
        if len(records) < 5:
            return 1.0
        correct = sum(1 for r in records if r.predicted == r.actual)
        return correct / len(records)

    def calibrated_confidence(self, agent: str, raw_confidence: float) -> float:
        """Adjust raw LLM confidence by historical accuracy.

        calibrated = raw_confidence * accuracy  (if enough history)
        If accuracy < 0.3, cap confidence at 0.3.
        If no history yet, return raw_confidence unchanged.
        """
        records = self._history.get(agent, [])
        if len(records) < 5:
            return raw_confidence

        acc = self.accuracy(agent)
        # acc is guaranteed >= 0.0 and <= 1.0 since len(records) >= 5
        calibrated = raw_confidence * acc
        if acc < 0.3:
            calibrated = min(calibrated, 0.3)
        return calibrated

    def stats(self) -> dict[str, dict[str, int | float]]:
        """Return per-agent statistics: sample count and accuracy."""
        result: dict[str, dict[str, int | float]] = {}
        for agent, records in self._history.items():
            result[agent] = {"samples": len(records), "accuracy": self.accuracy(agent)}
        return result
