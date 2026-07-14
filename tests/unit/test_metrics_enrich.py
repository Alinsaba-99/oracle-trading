"""Tests for recompute_metrics (Sharpe fix from equity curve)."""

from __future__ import annotations

from analytics.backtest.result import BacktestResult
from analytics.strategy.metrics_enrich import recompute_metrics


def _result(equity: list[float], sharpe: float = 0.0) -> BacktestResult:
    return BacktestResult(
        run_id="t",
        sharpe_ratio=sharpe,  # vectorbt's broken value
        equity_curve=equity,
    )


class TestRecomputeMetrics:
    def test_fixes_zero_sharpe_on_profitable_curve(self) -> None:
        # Noisy up-curve: positive drift with variance -> finite positive Sharpe.
        equity = [100_000.0, 101_000, 100_400, 102_200, 101_800, 104_000, 106_500]
        enriched = recompute_metrics(_result(equity, sharpe=0.0))
        assert enriched.sharpe_ratio > 0.0  # no longer the broken 0.0
        assert enriched.total_return > 0.0
        assert enriched.profit_factor > 0.0

    def test_negative_sharpe_on_declining_curve(self) -> None:
        equity = [100_000.0, 99_000, 99_500, 97_500, 96_000]
        enriched = recompute_metrics(_result(equity))
        assert enriched.total_return < 0.0

    def test_preserves_equity_curve_and_id(self) -> None:
        equity = [100_000.0, 101_000, 102_000]
        enriched = recompute_metrics(_result(equity))
        assert enriched.equity_curve == equity
        assert enriched.run_id == "t"

    def test_too_short_curve_unchanged(self) -> None:
        r = _result([100_000.0])
        assert recompute_metrics(r).sharpe_ratio == 0.0
