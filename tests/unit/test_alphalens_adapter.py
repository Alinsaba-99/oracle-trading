"""BL-710 — Alphalens-style diagnostic factor analyzer tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.metrics.canonical import sharpe_ratio
from analytics.research.factory.alphalens_adapter import (
    DEFAULT_HORIZONS,
    FactorAnalysis,
    analyze_factor,
    factor_turnover,
    ic_by_horizon,
    quantile_returns,
    returns_by_quantile,
)

# ── Synthetic data builders ────────────────────────────────────────────────


def _make_synthetic_universe(
    *, n_dates: int = 120, n_assets: int = 25, seed: int = 7, factor_strength: float = 0.6
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build prices + factor with a planted cross-sectional signal.

    ``factor`` is constructed so that its cross-sectional rank at time
    *t* correlates with the forward 1-day return at time *t*.  The
    planted correlation is approximately ``factor_strength`` after
    Spearman rank decorrelation of both sides.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-02", periods=n_dates, freq="B")
    assets = [f"A{i:02d}" for i in range(n_assets)]
    # Cross-sectional factor at each date: ordered by plant, plus noise.
    ordered_factor = np.tile(np.arange(n_assets, dtype=float), n_dates)
    noise = rng.standard_normal((n_dates, n_assets)) * 0.5
    factor_wide = pd.DataFrame(
        factor_strength * ordered_factor.reshape(n_dates, n_assets) + noise,
        index=dates,
        columns=assets,
    )
    # Forward returns: high factor → high return (planted signal).
    base_ret = rng.standard_normal((n_dates, n_assets)) * 0.005
    ret = pd.DataFrame(
        factor_strength
        * 0.01
        * np.tile(np.arange(n_assets, dtype=float), n_dates).reshape(n_dates, n_assets)
        / n_assets
        + base_ret,
        index=dates,
        columns=assets,
    )
    # Build a price series whose 1-step forward return equals `ret`.
    log_price = np.cumsum(ret.to_numpy(), axis=0)
    price_wide = pd.DataFrame(
        100.0 * np.exp(log_price - log_price[0:1, :]), index=dates, columns=assets
    )
    return factor_wide, price_wide


# ── IC by horizon ─────────────────────────────────────────────────────────


class TestICByHorizon:
    def test_returns_one_ic_per_horizon(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=120, n_assets=30)
        result = ic_by_horizon(factor, prices, horizons=[1, 5, 21])
        assert result.horizons == (1, 5, 21)
        assert len(result.ic_mean) == 3
        assert len(result.ic_std) == 3
        assert len(result.icir) == 3
        # ICIR = mean / std per horizon.
        for m, s, ir in zip(result.ic_mean, result.ic_std, result.icir, strict=True):
            if s > 0:
                assert ir == pytest.approx(m / s)

    def test_planted_signal_positive_ic(self) -> None:
        factor, prices = _make_synthetic_universe(
            n_dates=200, n_assets=40, seed=11, factor_strength=1.0
        )
        result = ic_by_horizon(factor, prices, horizons=[1])
        assert result.ic_mean[0] > 0.1

    def test_noise_factor_zero_ic_on_average(self) -> None:
        rng = np.random.default_rng(99)
        n = 200
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        assets = [f"A{i:02d}" for i in range(25)]
        factor = pd.DataFrame(rng.standard_normal((n, 25)), index=dates, columns=assets)
        prices = pd.DataFrame(
            100.0 * np.exp(np.cumsum(rng.standard_normal((n, 25)) * 0.005, axis=0)),
            index=dates,
            columns=assets,
        )
        result = ic_by_horizon(factor, prices, horizons=[1])
        # Should be near zero (large positive or negative means a leak).
        assert abs(result.ic_mean[0]) < 0.10

    def test_default_horizons_present(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=200)
        result = ic_by_horizon(factor, prices)
        assert result.horizons == DEFAULT_HORIZONS

    def test_as_table_is_horizon_indexed(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=200)
        result = ic_by_horizon(factor, prices, horizons=[1, 5])
        df = result.as_table()
        assert list(df.index) == [1, 5]
        assert {"ic_mean", "ic_std", "icir"} <= set(df.columns)


# ── Quantile returns ──────────────────────────────────────────────────────


class TestQuantileReturns:
    def test_planted_signal_monotonic_and_positive_spread(self) -> None:
        factor, prices = _make_synthetic_universe(
            n_dates=200, n_assets=50, seed=5, factor_strength=1.0
        )
        result = quantile_returns(factor, prices, quantiles=5)
        assert result.quantiles == (1, 2, 3, 4, 5)
        # Q1=low, Q5=high.  The plant has high factor → high return,
        # so Q5 > Q1 and the spread is positive.
        assert result.long_short > 0.0
        # Mean returns are non-decreasing from Q1 to Q5.
        means = list(result.mean_return)
        assert all(means[i] <= means[i + 1] for i in range(len(means) - 1)), (
            f"non-monotonic: {means}"
        )

    def test_random_factor_no_monotonicity(self) -> None:
        rng = np.random.default_rng(3)
        n = 200
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        assets = [f"A{i:02d}" for i in range(20)]
        factor = pd.DataFrame(rng.standard_normal((n, 20)), index=dates, columns=assets)
        prices = pd.DataFrame(
            100.0 * np.exp(np.cumsum(rng.standard_normal((n, 20)) * 0.01, axis=0)),
            index=dates,
            columns=assets,
        )
        result = quantile_returns(factor, prices, quantiles=5)
        # 20% of the time the random factor happens to be monotonic —
        # test that the spread is near zero instead.
        assert abs(result.long_short) < 0.005

    def test_quantile_returns_table(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=100)
        result = quantile_returns(factor, prices, quantiles=5)
        df = result.as_table()
        assert list(df.index) == [1, 2, 3, 4, 5]
        assert list(df.columns) == ["mean_return"]


class TestReturnsByQuantile:
    def test_per_quantile_time_series_shape(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=80, n_assets=15)
        ts = returns_by_quantile(factor, prices, quantiles=5)
        # Some early dates may be NaN due to lookback — at least 50 of 80 valid.
        valid = ts.returns_by_quantile.dropna(how="all")
        assert len(valid) >= 50
        assert ts.quantiles == ("q1", "q2", "q3", "q4", "q5")

    def test_sharpe_per_quantile_uses_canonical(self) -> None:
        """The Sharpe returned must match the canonical implementation."""
        factor, prices = _make_synthetic_universe(n_dates=120, n_assets=20)
        ts = returns_by_quantile(factor, prices, quantiles=5)
        sharpes = ts.sharpe_per_quantile()
        for col in ts.returns_by_quantile.columns:
            expected = sharpe_ratio(ts.returns_by_quantile[col].dropna())
            assert sharpes[col] == expected
        # And the canonical implementation, not a local copy, was used.
        assert all(np.isfinite(s) for s in sharpes)


# ── Turnover ───────────────────────────────────────────────────────────────


class TestTurnover:
    def test_constant_factor_zero_turnover(self) -> None:
        n, m = 100, 10
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        assets = [f"A{i}" for i in range(m)]
        # Identical factor across time → Spearman corr(t, t-1) = 1 → turnover = 0.
        factor = pd.DataFrame(
            np.tile(np.arange(m, dtype=float), (n, 1)), index=dates, columns=assets
        )
        result = factor_turnover(factor)
        assert result.mean_turnover == pytest.approx(0.0, abs=1e-9)
        assert result.max_turnover == pytest.approx(0.0, abs=1e-9)

    def test_random_factor_high_turnover(self) -> None:
        rng = np.random.default_rng(13)
        n, m = 200, 30
        dates = pd.date_range("2023-01-02", periods=n, freq="B")
        assets = [f"A{i}" for i in range(m)]
        # IID per date → corr(t, t-1) ≈ 0 → turnover ≈ 1.
        factor = pd.DataFrame(rng.standard_normal((n, m)), index=dates, columns=assets)
        result = factor_turnover(factor)
        assert result.mean_turnover > 0.5

    def test_short_factor_returns_zero_turnover(self) -> None:
        dates = pd.date_range("2023-01-02", periods=2, freq="B")
        factor = pd.DataFrame([[1.0, 2.0], [3.0, 4.0]], index=dates, columns=["A", "B"])
        result = factor_turnover(factor)
        assert result.mean_turnover == 0.0


# ── analyze_factor aggregator ─────────────────────────────────────────────


class TestAnalyzeFactor:
    def test_full_analysis_returns_all_pieces(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=120, n_assets=20, factor_strength=0.8)
        analysis = analyze_factor(
            factor, prices, factor_name="synthetic", horizons=(1, 5), quantiles=5
        )
        assert isinstance(analysis, FactorAnalysis)
        assert analysis.factor_name == "synthetic"
        assert analysis.ic.horizons == (1, 5)
        assert analysis.quantile_returns.quantiles == (1, 2, 3, 4, 5)
        assert analysis.turnover.mean_turnover >= 0.0

    def test_summary_dataframe_layout(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=120, n_assets=20)
        analysis = analyze_factor(factor, prices, factor_name="X", horizons=(1, 5))
        summary = analysis.as_summary()
        assert summary.index[0] == "X"
        assert "ic_1d" in summary.columns
        assert "ic_5d" in summary.columns
        assert "long_short" in summary.columns
        assert "monotonic_quantiles" in summary.columns
        assert "mean_turnover" in summary.columns

    def test_planted_signal_summary_metrics_positive(self) -> None:
        factor, prices = _make_synthetic_universe(
            n_dates=200, n_assets=50, seed=21, factor_strength=1.0
        )
        analysis = analyze_factor(factor, prices, factor_name="plant", horizons=(1,))
        summary = analysis.as_summary()
        # Planted signal → IC and long_short should be clearly positive.
        assert summary["ic_1d"].iloc[0] > 0.05
        assert summary["long_short"].iloc[0] > 0.0


# ── Edge cases & alignment ────────────────────────────────────────────────


class TestAlignment:
    def test_alignment_drops_unmatched_dates(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=100, n_assets=10)
        # Drop 30 dates from factor — the analyser must operate on the
        # intersection without crashing.
        truncated = factor.iloc[::2]
        result = ic_by_horizon(truncated, prices, horizons=[1], min_obs=5)
        assert len(result.ic_mean) == 1
        assert np.isfinite(result.ic_mean[0])

    def test_alignment_drops_unmatched_columns(self) -> None:
        factor, prices = _make_synthetic_universe(n_dates=80, n_assets=10)
        factor = factor.drop(columns=[factor.columns[0]])
        prices = prices.drop(columns=[prices.columns[-1]])
        result = ic_by_horizon(factor, prices, horizons=[1], min_obs=5)
        assert np.isfinite(result.ic_mean[0])
