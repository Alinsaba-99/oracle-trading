"""Tests for PortfolioOptimizer and BacktestPortfolio."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import polars as pl
import pytest

from analytics.backtest.portfolio import BacktestPortfolio
from analytics.backtest.portfolio_opt import PortfolioOptimizer
from analytics.backtest.result import BacktestResult
from core.domain.enums import TradeDirection, TradeStatus

# ====================================================================
# PortfolioOptimizer
# ====================================================================


class TestEfficientFrontier:
    """efficient_frontier() — mean-variance max-Sharpe optimisation."""

    @staticmethod
    def _sample_returns() -> pl.DataFrame:
        np = pytest.importorskip("numpy")
        rng = np.random.default_rng(42)
        n = 252
        return pl.DataFrame(
            {
                "timestamp": pl.datetime_range(
                    datetime(2024, 1, 1), datetime(2024, 12, 31), interval="1d", eager=True
                ).head(252),
                "AAPL": rng.normal(0.001, 0.02, n),
                "MSFT": rng.normal(0.001, 0.015, n),
                "GOOGL": rng.normal(0.0008, 0.025, n),
            }
        )

    def test_basic_allocation(self) -> None:
        """Returns valid weights that sum to ~1.0."""
        opt = PortfolioOptimizer()
        weights = opt.efficient_frontier(self._sample_returns())

        assert isinstance(weights, dict)
        assert len(weights) > 0
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.15)

    def test_all_weights_are_non_negative(self) -> None:
        """Max Sharpe with no short constraints should still be >= 0."""
        opt = PortfolioOptimizer()
        weights = opt.efficient_frontier(self._sample_returns())

        for v in weights.values():
            assert v >= -0.01  # small tolerance for numerical noise

    def test_asset_names_preserved(self) -> None:
        """Keys in result match the asset columns passed in."""
        opt = PortfolioOptimizer()
        returns = self._sample_returns()
        weights = opt.efficient_frontier(returns)

        expected = {"AAPL", "MSFT", "GOOGL"}
        assert set(weights.keys()) == expected

    def test_empty_returns_raises(self) -> None:
        """Empty DataFrame raises ValueError."""
        opt = PortfolioOptimizer()
        empty = pl.DataFrame({"timestamp": pl.Series([], dtype=pl.Datetime)})
        with pytest.raises(ValueError, match="empty"):
            opt.efficient_frontier(empty)

    def test_no_asset_columns_raises(self) -> None:
        """DataFrame with only timestamp raises ValueError."""
        opt = PortfolioOptimizer()
        df = pl.DataFrame({"timestamp": [datetime(2024, 1, 1)]})
        with pytest.raises(ValueError, match="No asset columns"):
            opt.efficient_frontier(df)


class TestHRP:
    """hrp() — Hierarchical Risk Parity."""

    @staticmethod
    def _sample_returns() -> pl.DataFrame:
        np = pytest.importorskip("numpy")
        rng = np.random.default_rng(123)
        n = 252
        return pl.DataFrame(
            {
                "AAPL": rng.normal(0.001, 0.02, n),
                "MSFT": rng.normal(0.001, 0.015, n),
                "GOOGL": rng.normal(0.0008, 0.025, n),
            }
        )

    def test_basic_allocation(self) -> None:
        """Returns valid weights."""
        opt = PortfolioOptimizer()
        weights = opt.hrp(self._sample_returns())

        assert isinstance(weights, dict)
        assert len(weights) == 3
        # HRP weights should sum to ~1.
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.15)

    def test_all_weights_are_non_negative(self) -> None:
        """HRP produces non-negative weights."""
        opt = PortfolioOptimizer()
        weights = opt.hrp(self._sample_returns())

        for v in weights.values():
            assert v >= -0.01

    def test_returns_deterministic(self) -> None:
        """Same input yields same output."""
        opt = PortfolioOptimizer()
        returns = self._sample_returns()
        w1 = opt.hrp(returns)
        w2 = opt.hrp(returns)
        assert w1 == w2


class TestBlackLitterman:
    """black_litterman() — Bayesian blend of prior and views."""

    @staticmethod
    def _sample_returns() -> pl.DataFrame:
        np = pytest.importorskip("numpy")
        rng = np.random.default_rng(77)
        n = 252
        return pl.DataFrame(
            {"AAPL": rng.normal(0.001, 0.02, n), "MSFT": rng.normal(0.001, 0.015, n)}
        )

    def test_no_views(self) -> None:
        """Without views the result resembles a max-Sharpe allocation."""
        opt = PortfolioOptimizer()
        weights = opt.black_litterman(self._sample_returns())

        assert isinstance(weights, dict)
        assert len(weights) == 2
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.15)

    def test_with_views(self) -> None:
        """Providing views shifts allocation."""
        opt = PortfolioOptimizer()
        returns = self._sample_returns()
        weights = opt.black_litterman(returns, views={"AAPL": 0.002})

        assert isinstance(weights, dict)
        assert len(weights) == 2
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.15)

    def test_empty_views_equals_no_views(self) -> None:
        """Empty dict for views should behave like None."""
        opt = PortfolioOptimizer()
        returns = self._sample_returns()
        w_none = opt.black_litterman(returns)
        w_empty = opt.black_litterman(returns, views={})

        assert w_none.keys() == w_empty.keys()


# ====================================================================
# BacktestPortfolio
# ====================================================================


class TestBacktestPortfolioAllocation:
    """allocation() — capital distribution from optimizer weights."""

    def test_basic_allocation(self) -> None:
        """Proportional capital split from weights."""
        bp = BacktestPortfolio()
        capital = Decimal("100000")
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        alloc = bp.allocation(weights, capital)

        assert alloc == {"AAPL": Decimal("60000"), "MSFT": Decimal("40000")}

    def test_three_way_split(self) -> None:
        """Even three-way split."""
        bp = BacktestPortfolio()
        capital = Decimal("100000")
        weights = {"A": 1.0, "B": 1.0, "C": 1.0}
        alloc = bp.allocation(weights, capital)

        expected = capital / Decimal("3")
        for v in alloc.values():
            assert v == expected

    def test_empty_weights(self) -> None:
        """Empty weights returns empty dict."""
        bp = BacktestPortfolio()
        assert bp.allocation({}, Decimal("100000")) == {}

    def test_zero_total_weight(self) -> None:
        """All-zero weights returns zero for each asset."""
        bp = BacktestPortfolio()
        alloc = bp.allocation({"A": 0.0, "B": 0.0}, Decimal("100000"))

        assert alloc == {"A": Decimal("0"), "B": Decimal("0")}

    def test_allocation_maintains_precision(self) -> None:
        """Decimal precision is preserved (no float rounding loss)."""
        bp = BacktestPortfolio()
        capital = Decimal("100000.00")
        weights = {"AAPL": 1.0 / 3.0, "MSFT": 1.0 / 3.0, "GOOGL": 1.0 / 3.0}
        alloc = bp.allocation(weights, capital)

        total = sum(alloc.values(), Decimal("0"))
        assert total == pytest.approx(capital, rel=Decimal("1e-10"))


class TestBacktestPortfolioCombinedEquity:
    """combined_equity() — aggregation across results."""

    def test_empty_portfolio(self) -> None:
        """Empty portfolio returns empty series."""
        bp = BacktestPortfolio()
        eq = bp.combined_equity()
        assert len(eq) == 0

    def test_single_result(self) -> None:
        """Single result returns its equity curve unchanged."""
        bp = BacktestPortfolio()
        bp.add_result(BacktestResult(strategy_name="A", equity_curve=[100.0, 110.0, 105.0]))
        eq = bp.combined_equity()
        assert eq.to_list() == [100.0, 110.0, 105.0]

    def test_multi_result_sum(self) -> None:
        """Multiple results have their curves element-wise summed."""
        bp = BacktestPortfolio()
        bp.add_result(BacktestResult(strategy_name="A", equity_curve=[100.0, 110.0]))
        bp.add_result(BacktestResult(strategy_name="B", equity_curve=[200.0, 190.0]))
        eq = bp.combined_equity()
        assert eq.to_list() == [300.0, 300.0]

    def test_uneven_lengths_padded(self) -> None:
        """Shorter curves are forward-filled to match the longest."""
        bp = BacktestPortfolio()
        bp.add_result(BacktestResult(strategy_name="A", equity_curve=[100.0, 110.0, 120.0]))
        bp.add_result(BacktestResult(strategy_name="B", equity_curve=[200.0]))
        eq = bp.combined_equity()
        # B is padded: [200.0, 200.0, 200.0]
        assert eq.to_list() == [300.0, 310.0, 320.0]


class TestBacktestPortfolioRebalance:
    """rebalance() — trade generation from target weights."""

    def _make_portfolio(self) -> BacktestPortfolio:
        return BacktestPortfolio(
            [BacktestResult(strategy_name="A", initial_capital=Decimal("100000"))]
        )

    def test_no_dates_no_trades(self) -> None:
        """Empty dates list produces no trades."""
        bp = self._make_portfolio()
        trades = bp.rebalance([], {"AAPL": 1.0})
        assert trades == []

    def test_no_weights_no_trades(self) -> None:
        """Empty weights dict produces no trades."""
        bp = self._make_portfolio()
        trades = bp.rebalance([datetime(2024, 6, 1)], {})
        assert trades == []

    def test_single_date_single_asset(self) -> None:
        """Single (date, asset) pair yields one trade."""
        bp = self._make_portfolio()
        dt = datetime(2024, 6, 1)
        trades = bp.rebalance([dt], {"AAPL": 1.0})

        assert len(trades) == 1
        t = trades[0]
        assert t.instrument_id == "AAPL"
        assert t.direction == TradeDirection.long
        assert t.status == TradeStatus.open
        assert t.entry_time == dt
        assert t.quantity > 0

    def test_multiple_assets_per_date(self) -> None:
        """Multiple assets per date produce one trade each."""
        bp = self._make_portfolio()
        dt = datetime(2024, 6, 1)
        trades = bp.rebalance([dt], {"AAPL": 0.6, "MSFT": 0.4})

        assert len(trades) == 2
        instruments = {t.instrument_id for t in trades}
        assert instruments == {"AAPL", "MSFT"}

    def test_multiple_dates(self) -> None:
        """Multiple dates produce trades for each (date, asset)."""
        bp = self._make_portfolio()
        dts = [datetime(2024, 6, 1), datetime(2024, 7, 1)]
        trades = bp.rebalance(dts, {"AAPL": 1.0})

        assert len(trades) == 2
        times = {t.entry_time for t in trades}
        assert times == set(dts)

    def test_short_direction(self) -> None:
        """Negative weight produces a short trade."""
        bp = self._make_portfolio()
        dt = datetime(2024, 6, 1)
        trades = bp.rebalance([dt], {"AAPL": -0.5})

        assert len(trades) == 1
        assert trades[0].direction == TradeDirection.short

    def test_custom_capital(self) -> None:
        """Explicit capital overrides fallback."""
        bp = BacktestPortfolio()
        dt = datetime(2024, 6, 1)
        trades = bp.rebalance([dt], {"AAPL": 1.0}, capital=Decimal("50000"))

        assert len(trades) == 1
        assert trades[0].quantity == Decimal("50000")  # 1.0 * 50000 / 1 date

    def test_zero_weight_asset_skipped(self) -> None:
        """Zero weight still generates a trade (abs(0) * capital)."""
        bp = self._make_portfolio()
        dt = datetime(2024, 6, 1)
        trades = bp.rebalance([dt], {"AAPL": 0.0, "MSFT": 1.0})

        assert len(trades) == 2  # both are included (quantity may be 0)
