"""Tests for lorentzian causal fix — expanding-window normalization."""

from __future__ import annotations

import numpy as np
import polars as pl

from analytics.strategy.lorentzian import compute_features


def _make_df(close: list[float]) -> pl.DataFrame:
    """Build a minimal OHLCV Polars DataFrame."""
    n = len(close)
    return pl.DataFrame(
        {
            "close": close,
            "high": [c + 0.5 for c in close],
            "low": [c - 0.5 for c in close],
            "open": close,
            "volume": [1000.0] * n,
        }
    )


class TestCausalNormalization:
    """compute_features must not use future data for normalization."""

    def test_no_lookahead_single_feature(self) -> None:
        """Add a spike at the END: bars before it must NOT be affected."""
        # Baseline: gently rising series
        close_base = [100.0 + i * 0.1 for i in range(50)]
        df_base = _make_df(close_base)
        feat_base = compute_features(df_base, [("rsi", 14, 1)])

        # Same series + a huge spike appended at the end
        close_with_spike = [*close_base, 500.0]
        df_spike = _make_df(close_with_spike)
        feat_spike = compute_features(df_spike, [("rsi", 14, 1)])

        # The first 50 bars must produce IDENTICAL features
        # (within float tolerance — RSI is deterministic given past data).
        np.testing.assert_allclose(
            feat_base[:, 0],
            feat_spike[:50, 0],
            rtol=1e-9,
            atol=1e-12,
            err_msg="Look-ahead detected: trailing spike changed earlier features",
        )

    def test_expanding_bounds(self) -> None:
        """Features must lie in [0, 1] using only past data for bounds."""
        close = list(np.linspace(100, 200, 100))
        df = _make_df(close)
        feat = compute_features(df, [("rsi", 14, 1)])
        # All non-NaN values must be in [0, 1]
        valid = feat[~np.isnan(feat)]
        assert (valid >= 0).all() and (valid <= 1).all()

    def test_first_value_is_neutral_or_nan(self) -> None:
        """First bar has no history: feature is NaN (RSI needs warmup)."""
        close = [100.0 + i * 0.5 for i in range(30)]
        df = _make_df(close)
        feat = compute_features(df, [("rsi", 14, 1)])
        first = feat[0, 0]
        assert np.isnan(first)

    def test_constant_series_yields_neutral(self) -> None:
        """Constant input has zero range → feature is 0.5 everywhere defined."""
        close = [100.0] * 50
        df = _make_df(close)
        feat = compute_features(df, [("rsi", 14, 1)])
        valid = feat[~np.isnan(feat)]
        # All defined values are exactly 0.5 (neutral, range==0)
        np.testing.assert_allclose(valid, 0.5, rtol=0, atol=1e-12)

    def test_monotone_increasing_uses_only_past_extremes(self) -> None:
        """Expanding min/max uses only past extremes — values stay in [0,1]."""
        # Trend + noise so RSI varies (monotone close pins RSI=100 → range=0)
        rng = np.random.default_rng(7)
        close = list(np.linspace(100, 200, 100) + np.cumsum(rng.standard_normal(100)))
        df = _make_df(close)
        feat = compute_features(df, [("rsi", 5, 1)])
        tail = feat[-3:, 0]
        valid = tail[~np.isnan(tail)]
        assert len(valid) > 0
        assert ((valid >= 0) & (valid <= 1)).all()


class TestLorentzianKNNIntegration:
    """End-to-end: LorentzianKNN.compute must not produce look-ahead bias."""

    def test_trailing_spike_does_not_change_earlier_signals(self) -> None:
        """A spike at the END must not flip any earlier signal."""
        from analytics.strategy.lorentzian import LorentzianKNN

        rng = np.random.default_rng(0)
        n = 200
        close_base = list(100 + np.cumsum(rng.standard_normal(n) * 0.5))

        df_base = _make_df(close_base)
        knn = LorentzianKNN(k=4, lookahead=4, max_bars_back=100, feature_count=3)
        sig_base = knn.compute(df_base).to_numpy()

        close_spike = [*close_base, close_base[-1] * 3]  # +200% spike at the end
        df_spike = _make_df(close_spike)
        sig_spike = knn.compute(df_spike).to_numpy()

        # Earlier signals must be identical (KNN's KNN does not peek)
        np.testing.assert_array_equal(
            sig_base,
            sig_spike[:n],
            err_msg="Trailing spike changed earlier signals — look-ahead present",
        )
