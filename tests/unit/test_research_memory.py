"""Tests for BL-090 — ResearchMemory (SQLite-backed decision tracking).

Run with: ``python -m pytest tests/unit/test_research_memory.py -x -v``
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import polars as pl
import pytest

from analytics.research.memory import ResearchMemory, build_features
from analytics.strategy.regime_ensemble import (
    RegimeAwareEnsemble,
    RoutingDecision,
    SpecialistId,
)


# ── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mem() -> ResearchMemory:
    """In-memory SQLite database for testing."""
    m = ResearchMemory(":memory:")
    yield m
    m.close()


def _make_trending_df(n: int = 260) -> pl.DataFrame:
    """Monotonically increasing close prices (strong uptrend)."""
    import numpy as np

    rng = np.random.default_rng(42)
    close = list(100.0 + np.cumsum(rng.standard_normal(n) * 0.3 + 0.1))
    return pl.DataFrame({"close": close})


# ── ResearchMemory tests ────────────────────────────────────────────────


class TestResearchMemoryCore:
    """Core CRUD operations."""

    def test_record_and_count(self, mem: ResearchMemory) -> None:
        did = mem.record_decision(
            regime="bull", regime_confidence=0.85, specialist="trend",
        )
        assert isinstance(did, int)
        assert did >= 1
        assert mem.count() == 1

    def test_record_and_retrieve(self, mem: ResearchMemory) -> None:
        did = mem.record_decision(
            regime="choppy",
            regime_confidence=0.72,
            specialist="mean_rev",
            reason="sma heuristic",
            signal=1,
            features={"close": 4500.0, "volatility": 0.015},
            session_id="session-1",
        )
        rows = mem.get_recent_decisions(10)
        assert len(rows) == 1
        r = rows[0]
        assert r["id"] == did
        assert r["regime"] == "choppy"
        assert r["regime_confidence"] == 0.72
        assert r["specialist"] == "mean_rev"
        assert r["reason"] == "sma heuristic"
        assert r["signal"] == 1
        assert r["session_id"] == "session-1"
        # features should be JSON string
        feats = json.loads(r["features"])
        assert feats["close"] == 4500.0

    def test_outcome_updates(self, mem: ResearchMemory) -> None:
        did = mem.record_decision(
            regime="bull", regime_confidence=0.9, specialist="trend",
        )
        mem.record_outcome(did, pnl=125.0, market_return=0.02)

        rows = mem.get_recent_decisions(10)
        assert len(rows) == 1
        assert rows[0]["pnl"] == 125.0
        assert rows[0]["market_return"] == 0.02

    def test_outcome_updates_only_specified_row(self, mem: ResearchMemory) -> None:
        d1 = mem.record_decision(regime="bull", regime_confidence=0.9, specialist="trend")
        d2 = mem.record_decision(regime="choppy", regime_confidence=0.7, specialist="mean_rev")
        mem.record_outcome(d1, pnl=100.0, market_return=0.01)

        rows = mem.get_recent_decisions(10)
        rows_by_id = {r["id"]: r for r in rows}
        assert rows_by_id[d1]["pnl"] == 100.0
        assert rows_by_id[d2]["pnl"] is None

    def test_close_and_reopen(self) -> None:
        """Verify persistence across close/reopen cycles."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            mem1 = ResearchMemory(db_path)
            did = mem1.record_decision(
                regime="bear", regime_confidence=0.6, specialist="flat",
            )
            mem1.record_outcome(did, pnl=-50.0, market_return=-0.01)
            mem1.close()

            # Reopen and verify data persists.
            mem2 = ResearchMemory(db_path)
            assert mem2.count() == 1
            rows = mem2.get_recent_decisions(10)
            assert rows[0]["pnl"] == -50.0
            mem2.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestResearchMemoryAnalytics:
    """Analytics queries (regime accuracy, specialist performance)."""

    def test_regime_accuracy_no_outcomes(self, mem: ResearchMemory) -> None:
        mem.record_decision(regime="bull", regime_confidence=0.9, specialist="trend")
        stats = mem.get_regime_accuracy()
        assert "bull" in stats
        assert stats["bull"]["n"] == 1
        assert stats["bull"]["win_rate"] is None  # no outcomes yet

    def test_regime_accuracy_with_outcomes(self, mem: ResearchMemory) -> None:
        for i in range(10):
            d = mem.record_decision(
                regime="bull" if i < 8 else "choppy",
                regime_confidence=0.85,
                specialist="trend",
            )
            mem.record_outcome(d, pnl=100.0 if i < 6 else -50.0, market_return=0.01)

        stats = mem.get_regime_accuracy()
        assert "bull" in stats
        assert stats["bull"]["n"] == 8
        # 6 wins out of 8
        assert stats["bull"]["win_rate"] == pytest.approx(6 / 8, rel=0.01)

    def test_regime_accuracy_filtered(self, mem: ResearchMemory) -> None:
        for _ in range(5):
            d = mem.record_decision(regime="bull", regime_confidence=0.8, specialist="trend")
            mem.record_outcome(d, pnl=10.0, market_return=0.0)
        for _ in range(3):
            d = mem.record_decision(regime="choppy", regime_confidence=0.7, specialist="mean_rev")
            mem.record_outcome(d, pnl=5.0, market_return=0.0)

        bull_stats = mem.get_regime_accuracy(regime="bull")
        assert bull_stats["n"] == 5

        choppy_stats = mem.get_regime_accuracy(regime="choppy")
        assert choppy_stats["n"] == 3

    def test_specialist_performance(self, mem: ResearchMemory) -> None:
        # Trend: 3 wins, 1 loss
        for _ in range(4):
            d = mem.record_decision(regime="bull", regime_confidence=0.8, specialist="trend")
            mem.record_outcome(d, pnl=100.0 if _ < 3 else -50.0, market_return=0.01)

        # Mean_rev: 1 win, 3 losses
        for _ in range(4):
            d = mem.record_decision(regime="choppy", regime_confidence=0.7, specialist="mean_rev")
            mem.record_outcome(d, pnl=30.0 if _ < 1 else -20.0, market_return=0.0)

        perf = mem.get_specialist_performance()
        assert "trend" in perf
        assert "mean_rev" in perf
        assert perf["trend"]["n"] == 4
        assert perf["trend"]["win_rate"] == pytest.approx(3 / 4, rel=0.01)
        assert perf["mean_rev"]["win_rate"] == pytest.approx(1 / 4, rel=0.01)

    def test_specialist_performance_filtered(self, mem: ResearchMemory) -> None:
        for _ in range(5):
            d = mem.record_decision(regime="bull", regime_confidence=0.8, specialist="trend")
            mem.record_outcome(d, pnl=10.0, market_return=0.0)

        trend_perf = mem.get_specialist_performance(specialist="trend")
        assert trend_perf["n"] == 5

    def test_get_decisions_by_session(self, mem: ResearchMemory) -> None:
        for i in range(5):
            mem.record_decision(
                regime="bull", regime_confidence=0.8, specialist="trend",
                session_id="session-1",
            )
        for i in range(3):
            mem.record_decision(
                regime="choppy", regime_confidence=0.7, specialist="mean_rev",
                session_id="session-2",
            )

        s1 = mem.get_decisions_by_session("session-1")
        assert len(s1) == 5

        s2 = mem.get_decisions_by_session("session-2")
        assert len(s2) == 3


class TestBuildFeatures:
    """build_features helper."""

    def test_returns_only_non_none(self) -> None:
        f = build_features(close=4500.0, volatility=0.015)
        assert f == {"close": 4500.0, "volatility": 0.015}

    def test_extra_fields(self) -> None:
        f = build_features(close=4500.0, extra_field="hello")
        assert f["extra_field"] == "hello"

    def test_empty(self) -> None:
        f = build_features()
        assert f == {}


class TestResearchMemoryEdgeCases:
    """Edge cases: empty memory, missing data, large values."""

    def test_empty_stats(self, mem: ResearchMemory) -> None:
        assert mem.count() == 0
        assert mem.get_regime_accuracy() == {}
        assert mem.get_specialist_performance() == {}
        assert mem.get_recent_decisions(10) == []

    def test_specialist_performance_no_outcomes(self, mem: ResearchMemory) -> None:
        mem.record_decision(regime="bull", regime_confidence=0.8, specialist="trend")
        perf = mem.get_specialist_performance()
        # No pnl data, so perf should be empty for this specialist
        # (the inner query filters WHERE pnl IS NOT NULL)
        assert perf == {}

    def test_context_manager(self) -> None:
        with ResearchMemory(":memory:") as mem:
            did = mem.record_decision(regime="bull", regime_confidence=0.5, specialist="flat")
            assert did >= 1
