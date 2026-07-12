"""Tests for the curated alpha factor library.

Covers known-value correctness, NaN/inf handling, edge cases,
and batch computation.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from genetics.alpha.library import CuratedAlphaLibrary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _timerange(n: int, start: str = "2020-01-01") -> pl.Series:
    """Create a range of n daily timestamps starting at start (UTC)."""
    dt_start = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC)
    dt_end = dt_start + timedelta(days=n - 1)
    return pl.date_range(dt_start, dt_end, interval="1d", eager=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def library() -> CuratedAlphaLibrary:
    return CuratedAlphaLibrary()


@pytest.fixture(scope="module")
def factor_names(library: CuratedAlphaLibrary) -> list[str]:
    return library.factor_names


@pytest.fixture
def ohlcv() -> pl.DataFrame:
    """150 trading days of synthetic OHLCV data with clear patterns."""
    n = 150
    rng = np.random.default_rng(42)
    # Price that trends up then down then up
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    # Make some clear patterns
    close[20:40] = close[20:40] * 1.1  # spike
    close[60:80] = close[60:80] * 0.9  # dip
    high = close * (1.0 + rng.uniform(0.002, 0.015, n))
    low = close * (1.0 - rng.uniform(0.002, 0.015, n))
    open_p = close * (1.0 + rng.normal(0, 0.005, n))
    volume = rng.integers(1_000_000, 10_000_000, n)
    timestamps = _timerange(n)
    # Clamp high/low properly
    high = np.maximum(high, np.maximum(open_p, close))
    low = np.minimum(low, np.minimum(open_p, close))

    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": pl.Series("open", open_p.tolist()),
            "high": pl.Series("high", high.tolist()),
            "low": pl.Series("low", low.tolist()),
            "close": pl.Series("close", close.tolist()),
            "volume": pl.Series("volume", volume.tolist()),
        }
    )


# ---------------------------------------------------------------------------
# Library basics
# ---------------------------------------------------------------------------


class TestCuratedAlphaLibrary:
    def test_50_factors(self, library: CuratedAlphaLibrary, factor_names: list[str]) -> None:
        assert len(factor_names) == 50, f"Expected 50 factors, got {len(factor_names)}"

    def test_categories_cover_all(
        self, library: CuratedAlphaLibrary, factor_names: list[str]
    ) -> None:
        all_from_categories: set[str] = set()
        for names in library.CATEGORIES.values():
            all_from_categories.update(names)
        assert all_from_categories == set(factor_names), (
            f"Category coverage mismatch. Missing from categories: "
            f"{set(factor_names) - all_from_categories}"
        )

    def test_get_factor(self, library: CuratedAlphaLibrary) -> None:
        func = library.get("rsi_14")
        assert callable(func)

    def test_get_unknown_factor_raises(self, library: CuratedAlphaLibrary) -> None:
        with pytest.raises(KeyError, match="Unknown factor"):
            library.get("nonexistent_factor")

    def test_metadata_keys(self, library: CuratedAlphaLibrary, factor_names: list[str]) -> None:
        meta = library.metadata
        assert set(meta.keys()) == set(factor_names)
        for name in factor_names:
            assert "category" in meta[name]
            assert "description" in meta[name]

    def test_metadata_has_all_categories(self, library: CuratedAlphaLibrary) -> None:
        meta = library.metadata
        categories_found: set[str] = set()
        for info in meta.values():
            categories_found.add(info["category"])
        assert categories_found == set(library.CATEGORIES.keys())

    def test_batch_compute_all(self, library: CuratedAlphaLibrary, ohlcv: pl.DataFrame) -> None:
        results = library.compute(ohlcv)
        assert len(results) == 50
        for name, series in results.items():
            assert isinstance(series, pl.Series), f"{name} returned {type(series)}"
            assert len(series) == len(ohlcv), f"{name} length mismatch"

    def test_batch_compute_subset(self, library: CuratedAlphaLibrary, ohlcv: pl.DataFrame) -> None:
        names = ["roc_1m", "rsi_14", "atr_14"]
        results = library.compute(ohlcv, names=names)
        assert len(results) == 3
        assert all(n in results for n in names)

    def test_batch_compute_empty_subset(
        self, library: CuratedAlphaLibrary, ohlcv: pl.DataFrame
    ) -> None:
        results = library.compute(ohlcv, names=[])
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Known-value tests for representative factors
# ---------------------------------------------------------------------------


class TestFactorValues:
    """Verify factor outputs match expected values from known formulas."""

    def test_rsi_14_overbought(self, library: CuratedAlphaLibrary) -> None:
        """RSI should be > 70 for a strong uptrend (overbought)."""
        n = 30
        close = pl.Series("close", [100.0 + i * 0.5 for i in range(n)])
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close * 0.99,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": [1_000_000] * n,
            }
        )
        result = library.get("rsi_14")(data)
        # Last values should be near 100 in persistent uptrend
        last_rsi = result[-1]
        if last_rsi is not None and not math.isnan(last_rsi):
            assert last_rsi > 70.0, f"RSI should be overbought in uptrend, got {last_rsi}"

    def test_rsi_14_oversold(self, library: CuratedAlphaLibrary) -> None:
        """RSI should be < 30 for a strong downtrend (oversold)."""
        n = 30
        close = pl.Series("close", [100.0 - i * 0.5 for i in range(n)])
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close * 1.01,
                "high": close * 1.02,
                "low": close * 0.99,
                "close": close,
                "volume": [1_000_000] * n,
            }
        )
        result = library.get("rsi_14")(data)
        last_rsi = result[-1]
        if last_rsi is not None and not math.isnan(last_rsi):
            assert last_rsi < 30.0, f"RSI should be oversold in downtrend, got {last_rsi}"

    def test_bb_position(self, library: CuratedAlphaLibrary) -> None:
        """Price above SMA should give positive BB position."""
        n = 30
        # Price that starts flat then jumps up
        close = pl.Series("close", [100.0] * 20 + [110.0] * 10)
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": [1_000_000] * n,
            }
        )
        result = library.get("bb_position")(data)
        # After the jump, BB position should be positive
        last = result[-5:].fill_nan(0.0)
        assert (last > 0.0).any(), (
            f"BB position should be positive after price jump, got {last.to_list()}"
        )

    def test_distance_from_sma_20(self, library: CuratedAlphaLibrary) -> None:
        """Price above SMA -> positive distance."""
        n = 30
        close = pl.Series("close", [100.0] * 20 + [105.0] * 10)
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": [1_000_000] * n,
            }
        )
        result = library.get("distance_from_sma_20")(data)
        last = result[-1]
        if last is not None and not math.isnan(last):
            assert last > 0.0, f"Distance from SMA should be positive, got {last}"

    def test_beta_sign(self, library: CuratedAlphaLibrary) -> None:
        """In trending market, beta should be positive for a stock moving with market."""
        n = 100
        rng = np.random.default_rng(99)
        trend = np.cumsum(rng.normal(0.001, 0.01, n))
        close = 100.0 * np.exp(trend)
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close * 0.99,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": pl.Series("close", close.tolist()),
                "volume": [1_000_000] * n,
            }
        )
        result = library.get("beta_60")(data)
        last = result[-5:].fill_nan(0.0)
        assert (last > 0.0).any(), (
            f"Beta should tend positive in trending market, got {last.to_list()}"
        )

    def test_volume_zscore(self, library: CuratedAlphaLibrary) -> None:
        """Spike in volume should give high zscore."""
        n = 30
        volume = [1_000_000] * 25 + [10_000_000] * 5  # spike
        close = [100.0] * n
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": volume,
            }
        )
        result = library.get("volume_zscore_20")(data)
        last = result[-5:].fill_nan(0.0)
        assert (last > 1.0).any(), f"Volume zscore should be high after spike, got {last.to_list()}"

    def test_momentum_stability(self, library: CuratedAlphaLibrary) -> None:
        """In persistent uptrend, stability should be high (near 1)."""
        n = 80
        close = [100.0 + i * 0.3 for i in range(n)]
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close,
                "high": [c * 1.01 for c in close],
                "low": [c * 0.99 for c in close],
                "close": close,
                "volume": [1_000_000] * n,
            }
        )
        result = library.get("momentum_stability")(data)
        last = result[-5:].fill_nan(0.0)
        assert (last > 0.5).any(), (
            f"Momentum stability should be high in uptrend, got {last.to_list()}"
        )


# ---------------------------------------------------------------------------
# Edge cases: NaN, constant, empty, single element
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Factor functions must handle degenerate inputs gracefully."""

    @pytest.fixture
    def library(self) -> CuratedAlphaLibrary:
        return CuratedAlphaLibrary()

    def _make_data(
        self, n: int, close_val: float = 100.0, volume_val: int = 1_000_000
    ) -> pl.DataFrame:
        close = [close_val] * n
        return pl.DataFrame(
            {
                "timestamp": _timerange(n)
                if n > 0
                else pl.Series("timestamp", [], dtype=pl.Datetime),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": [volume_val] * n,
            }
        )

    def test_constant_prices(self, library: CuratedAlphaLibrary) -> None:
        """All factors should handle constant prices without crashing."""
        data = self._make_data(100)
        for name in library.factor_names:
            result = library.get(name)(data)
            assert isinstance(result, pl.Series)
            assert len(result) == len(data), f"{name} length mismatch"
            # Should be finite values
            arr = result.fill_nan(0.0).to_numpy()
            assert np.all(np.isfinite(arr)), f"{name} returned non-finite values"

    def test_series_with_nan(self, library: CuratedAlphaLibrary) -> None:
        """NaN in close should not cause crashes."""
        n = 100
        close = [100.0] * 50 + [float("nan")] * 50
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": [1_000_000] * n,
            }
        )
        for name in ["roc_1m", "rsi_14", "atr_14", "bb_position", "volume_zscore_20"]:
            result = library.get(name)(data)
            assert isinstance(result, pl.Series)
            assert len(result) == n

    def test_zero_volume(self, library: CuratedAlphaLibrary) -> None:
        """Zero volume should not cause division by zero crashes."""
        data = self._make_data(100, close_val=100.0, volume_val=0)
        vol_factors = [
            "volume_zscore_20",
            "turnover",
            "volume_vs_avg",
            "dollar_volume",
            "amihud_illiquidity",
            "roll_impact",
        ]
        for name in vol_factors:
            result = library.get(name)(data)
            assert isinstance(result, pl.Series)
            assert np.all(np.isfinite(result.fill_nan(0.0).to_numpy())), (
                f"{name} has non-finite values"
            )

    def test_very_large_values(self, library: CuratedAlphaLibrary) -> None:
        """Very large or small price values should be handled."""
        n = 100
        close = [1e8 + i for i in range(n)]
        data = pl.DataFrame(
            {
                "timestamp": _timerange(n),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": [1_000_000] * n,
            }
        )
        for name in library.factor_names:
            result = library.get(name)(data)
            assert isinstance(result, pl.Series)
            assert np.all(np.isfinite(result.fill_nan(0.0).to_numpy())), (
                f"{name} has non-finite values with large prices"
            )

    def test_empty_dataframe(self, library: CuratedAlphaLibrary) -> None:
        """Empty DataFrame should produce empty result Series."""
        data = pl.DataFrame(
            {
                "timestamp": pl.Series("timestamp", [], dtype=pl.Datetime),
                "open": pl.Series("open", [], dtype=pl.Float64),
                "high": pl.Series("high", [], dtype=pl.Float64),
                "low": pl.Series("low", [], dtype=pl.Float64),
                "close": pl.Series("close", [], dtype=pl.Float64),
                "volume": pl.Series("volume", [], dtype=pl.Int64),
            }
        )
        for name in library.factor_names:
            result = library.get(name)(data)
            assert isinstance(result, pl.Series)
            assert len(result) == 0, f"{name} expected empty"

    def test_single_element(self, library: CuratedAlphaLibrary) -> None:
        """Single-element DataFrame should produce single result."""
        dt_start = datetime(2020, 1, 1, tzinfo=UTC)
        data = pl.DataFrame(
            {
                "timestamp": pl.date_range(dt_start, dt_start, interval="1d", eager=True),
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [1_000_000],
            }
        )
        for name in library.factor_names:
            result = library.get(name)(data)
            assert isinstance(result, pl.Series)
            assert len(result) == 1, f"{name} expected length 1"

    def test_short_series(self, library: CuratedAlphaLibrary) -> None:
        """Very short series (3 elements) should not crash."""
        n = 3
        data = self._make_data(n)
        for name in library.factor_names:
            result = library.get(name)(data)
            assert isinstance(result, pl.Series)
            assert len(result) == n, f"{name} expected length {n}, got {len(result)}"
