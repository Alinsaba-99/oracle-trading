"""Tests for BacktestResultStore and the dashboard summary bridge."""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.backtest.result import BacktestResult
from analytics.backtest.store import (
    BacktestResultStore,
    to_equity_points,
    to_performance_summary,
)


def _sample(**overrides: object) -> BacktestResult:
    base: dict[str, object] = {
        "run_id": "test-1",
        "instrument": "EURUSD",
        "total_return": 0.15,
        "sharpe_ratio": 1.8,
        "sortino_ratio": 2.2,
        "calmar_ratio": 1.1,
        "max_drawdown": 0.08,
        "volatility": 0.12,
        "cagr": 0.20,
        "total_trades": 42,
        "win_rate": 0.55,
        "profit_factor": 2.1,
        "avg_win": 120.0,
        "avg_loss": 60.0,
        "final_equity": 115_000.0,
        "equity_curve": [100_000.0, 105_000.0, 110_000.0, 115_000.0],
    }
    base.update(overrides)
    return BacktestResult(**base)  # type: ignore[arg-type]


class TestStoreRoundtrip:
    def test_save_and_load_latest(self, tmp_path: object) -> None:
        store = BacktestResultStore(directory=str(tmp_path))
        store.save(_sample())
        loaded = store.load_latest()
        assert loaded is not None
        assert loaded.run_id == "test-1"
        assert loaded.total_return == pytest.approx(0.15)
        assert loaded.profit_factor == pytest.approx(2.1)
        assert loaded.equity_curve == [100_000.0, 105_000.0, 110_000.0, 115_000.0]

    def test_load_latest_none_when_empty(self, tmp_path: object) -> None:
        assert BacktestResultStore(directory=str(tmp_path)).load_latest() is None

    def test_load_by_run_id(self, tmp_path: object) -> None:
        store = BacktestResultStore(directory=str(tmp_path))
        store.save(_sample(run_id="abc"))
        assert store.load("abc") is not None
        assert store.load("missing") is None

    def test_save_overwrites_latest(self, tmp_path: object) -> None:
        store = BacktestResultStore(directory=str(tmp_path))
        store.save(_sample(run_id="first", total_return=0.10))
        store.save(_sample(run_id="second", total_return=0.25))
        loaded = store.load_latest()
        assert loaded is not None
        assert loaded.run_id == "second"
        assert loaded.total_return == pytest.approx(0.25)


class TestSummaryBridge:
    def test_summary_has_real_not_placeholder_fields(self) -> None:
        summary = to_performance_summary(_sample())
        # The whole point of Fase 3: these are NO LONGER placeholder zeros.
        assert summary["profit_factor"] == pytest.approx(2.1)
        assert summary["cagr"] == pytest.approx(0.20)
        assert summary["total_return"] == pytest.approx(0.15)
        assert summary["sharpe"] == pytest.approx(1.8)
        assert summary["total_trades"] == 42
        assert summary["instrument"] == "EURUSD"

    def test_equity_points_shape(self) -> None:
        pts = to_equity_points(_sample(equity_curve=[100.0, 110.0, 105.0]))
        assert pts == [
            {"index": 0.0, "equity": 100.0},
            {"index": 1.0, "equity": 110.0},
            {"index": 2.0, "equity": 105.0},
        ]

    def test_equity_points_empty(self) -> None:
        assert to_equity_points(_sample(equity_curve=[])) == []


class TestCheckpointReaderIntegration:
    """End-to-end: the API summary/equity now serve REAL persisted metrics."""

    def test_summary_and_equity_from_persisted_result(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import analytics.backtest.store as store_mod
        from apps.api.services import checkpoint_reader

        monkeypatch.setattr(store_mod, "_DEFAULT_DIR", tmp_path)
        BacktestResultStore(directory=str(tmp_path)).save(
            _sample(
                profit_factor=2.5,
                cagr=0.18,
                total_return=0.14,
                equity_curve=[100_000.0, 110_000.0, 105_000.0],
            )
        )

        summary = checkpoint_reader.get_latest_run_summary()
        assert summary is not None
        # Real values, not placeholder zeros.
        assert summary["profit_factor"] == pytest.approx(2.5)
        assert summary["total_return"] == pytest.approx(0.14)
        assert summary["cagr"] == pytest.approx(0.18)

        equity = checkpoint_reader.get_equity_curve()
        assert [p["equity"] for p in equity] == [100_000.0, 110_000.0, 105_000.0]
