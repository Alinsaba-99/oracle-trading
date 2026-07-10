"""Tests for ConfidenceTracker — accuracy, calibration, and edge cases."""

from __future__ import annotations

import pytest

from agents.confidence import ConfidenceTracker


class TestConfidenceTracker:
    """Tests for ConfidenceTracker."""

    # ── Recording and accuracy ──────────────────────────────────────────────

    def test_record_and_accuracy_perfect(self) -> None:
        """All correct predictions yield accuracy 1.0."""
        tracker = ConfidenceTracker()
        for _ in range(5):
            tracker.record("bull", predicted="up", actual="up", confidence=0.8)
        assert tracker.accuracy("bull") == 1.0

    def test_record_and_accuracy_partial(self) -> None:
        """Mixed predictions yield proportional accuracy."""
        tracker = ConfidenceTracker()
        for _ in range(4):
            tracker.record("macro", predicted="up", actual="up", confidence=0.8)
        tracker.record("macro", predicted="up", actual="down", confidence=0.8)
        assert tracker.accuracy("macro") == 4 / 5

    def test_accuracy_below_min_samples(self) -> None:
        """Fewer than min_samples records returns 0.0."""
        tracker = ConfidenceTracker()
        tracker.record("tech", predicted="up", actual="up", confidence=0.8)
        assert tracker.accuracy("tech") == 0.0

    def test_accuracy_custom_min_samples(self) -> None:
        """Custom min_samples threshold works."""
        tracker = ConfidenceTracker()
        tracker.record("tech", predicted="up", actual="up", confidence=0.8)
        assert tracker.accuracy("tech", min_samples=1) == 1.0

    # ── Calibration weight ──────────────────────────────────────────────────

    def test_calibration_weight_less_than_one(self) -> None:
        """Calibration weight equals accuracy when accuracy < 1.0."""
        tracker = ConfidenceTracker()
        for _ in range(4):
            tracker.record("macro", predicted="up", actual="up", confidence=0.8)
        tracker.record("macro", predicted="up", actual="down", confidence=0.8)
        weight = tracker.calibration_weight("macro")
        assert weight == pytest.approx(0.8)  # 4/5

    def test_calibration_weight_no_history(self) -> None:
        """No history yields weight 1.0."""
        tracker = ConfidenceTracker()
        assert tracker.calibration_weight("unknown") == 1.0

    def test_calibration_weight_insufficient_samples(self) -> None:
        """Fewer than 5 samples yields weight 1.0."""
        tracker = ConfidenceTracker()
        for _ in range(3):
            tracker.record("new", predicted="up", actual="up", confidence=0.8)
        assert tracker.calibration_weight("new") == 1.0

    def test_calibration_weight_perfect(self) -> None:
        """All correct yields weight 1.0."""
        tracker = ConfidenceTracker()
        for _ in range(5):
            tracker.record("gold", predicted="up", actual="up", confidence=0.8)
        assert tracker.calibration_weight("gold") == 1.0

    # ── Calibrated confidence ───────────────────────────────────────────────

    def test_calibrated_confidence_no_history(self) -> None:
        """No history returns raw_confidence unchanged."""
        tracker = ConfidenceTracker()
        assert tracker.calibrated_confidence("unknown", 0.9) == 0.9

    def test_calibrated_confidence_insufficient_samples(self) -> None:
        """Fewer than 5 samples returns raw_confidence unchanged."""
        tracker = ConfidenceTracker()
        for _ in range(3):
            tracker.record("new", predicted="up", actual="up", confidence=0.8)
        assert tracker.calibrated_confidence("new", 0.9) == 0.9

    def test_calibrated_confidence_scaled(self) -> None:
        """With accuracy 0.8, calibrated = raw * 0.8."""
        tracker = ConfidenceTracker()
        for _ in range(4):
            tracker.record("macro", predicted="up", actual="up", confidence=0.8)
        tracker.record("macro", predicted="up", actual="down", confidence=0.8)
        result = tracker.calibrated_confidence("macro", 1.0)
        assert result == pytest.approx(0.8)

    def test_calibrated_confidence_low_accuracy_cap(self) -> None:
        """With accuracy 0.0, calibrated = 0.0 (capped at 0.3, but 0.0 < 0.3)."""
        tracker = ConfidenceTracker()
        for _ in range(5):
            tracker.record("bad", predicted="up", actual="down", confidence=0.8)
        result = tracker.calibrated_confidence("bad", 0.9)
        assert result == 0.0  # 0.9 * 0.0 = 0.0, min(0.0, 0.3) = 0.0

    def test_calibrated_confidence_very_low_accuracy_cap(self) -> None:
        """With accuracy ~0, calibrated is still capped at min(0,bias) but actual min is 0.3."""
        tracker = ConfidenceTracker()
        for _ in range(10):
            tracker.record("terrible", predicted="up", actual="down", confidence=0.8)
        result = tracker.calibrated_confidence("terrible", 0.9)
        # accuracy = 0.0, so calibrated = raw * 0.0 = 0.0, but acc < 0.3 so cap at 0.3
        # 0.9 * 0.0 = 0.0, min(0.0, 0.3) = 0.0
        # Actually with accuracy 0.0, calibrated = 0.9 * 0.0 = 0.0, min(0.0, 0.3) = 0.0
        assert result == 0.0  # 0.9 * 0.0 = 0.0, capped at 0.3 but 0.0 < 0.3

    # ── Stats ───────────────────────────────────────────────────────────────

    def test_stats_empty(self) -> None:
        """Empty tracker returns empty stats."""
        tracker = ConfidenceTracker()
        assert tracker.stats() == {}

    def test_stats_multiple_agents(self) -> None:
        """Stats reflect tracking for multiple agents."""
        tracker = ConfidenceTracker()
        tracker.record("bull", predicted="up", actual="up", confidence=0.8)
        tracker.record("bear", predicted="down", actual="up", confidence=0.8)

        stats = tracker.stats()
        assert set(stats) == {"bull", "bear"}

    # ── Multiple agents ────────────────────────────────────────────────────

    def test_multiple_agents_isolated(self) -> None:
        """Each agent's history is tracked independently."""
        tracker = ConfidenceTracker()
        for _ in range(5):
            tracker.record("bull", predicted="up", actual="up", confidence=0.8)
            tracker.record("bear", predicted="down", actual="down", confidence=0.8)

        assert tracker.accuracy("bull") == 1.0
        assert tracker.accuracy("bear") == 1.0

    def test_accuracy_agent_not_found(self) -> None:
        """Unknown agent returns 0.0 accuracy."""
        tracker = ConfidenceTracker()
        assert tracker.accuracy("nonexistent") == 0.0

    def test_record_updates_stats(self) -> None:
        """Stats sample count matches number of records."""
        tracker = ConfidenceTracker()
        for i in range(5):
            tracker.record("alpha", predicted="up", actual="up", confidence=0.8 - i * 0.1)
        stats = tracker.stats()
        assert stats["alpha"]["samples"] == 5
