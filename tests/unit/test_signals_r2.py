"""Contract tests for the R2 long/short signal families."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from analytics.strategy import signals
from analytics.strategy.signals_r2 import R2_SIGNALS

R2_KEYS = sorted(R2_SIGNALS)


def synth_ohlcv(n: int = 800, seed: int = 7, drift: float = 0.0002) -> pl.DataFrame:
    """Geometric-random-walk OHLCV with timestamps and non-zero volume."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 0.01, n)
    close = 100.0 * np.exp(np.cumsum(steps))
    spread = np.abs(rng.normal(0.0, 0.004, n)) * close
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pl.DataFrame(
        {
            "timestamp": pl.datetime_range(
                start=pl.datetime(2020, 1, 1),
                end=pl.datetime(2020, 1, 1) + pl.duration(hours=n - 1),
                interval="1h",
                eager=True,
            ),
            "open": open_,
            "high": np.maximum(open_, close) + spread,
            "low": np.minimum(open_, close) - spread,
            "close": close,
            "volume": rng.uniform(1_000, 10_000, n),
        }
    )


def trending_ohlcv(n: int = 400, *, up: bool = True) -> pl.DataFrame:
    """Near-monotonic series — used to assert directional sanity."""
    drift = 0.004 if up else -0.004
    return synth_ohlcv(n, seed=3, drift=drift)


class TestContract:
    @pytest.mark.parametrize("key", R2_KEYS)
    def test_returns_int8_in_domain(self, key: str) -> None:
        data = synth_ohlcv()
        sig = R2_SIGNALS[key]().compute(data)
        assert sig.dtype == pl.Int8, f"{key} must return Int8"
        assert len(sig) == data.height, f"{key} length mismatch"
        assert set(np.unique(sig.to_numpy())).issubset({-1, 0, 1}), f"{key} out of domain"

    @pytest.mark.parametrize("key", R2_KEYS)
    def test_no_nulls(self, key: str) -> None:
        sig = R2_SIGNALS[key]().compute(synth_ohlcv())
        assert sig.null_count() == 0, f"{key} emitted nulls"

    @pytest.mark.parametrize("key", R2_KEYS)
    def test_zero_arg_constructible(self, key: str) -> None:
        # The GA and the LLM researcher both instantiate by name with no args.
        assert R2_SIGNALS[key]() is not None

    @pytest.mark.parametrize("key", R2_KEYS)
    def test_short_frame_is_flat_not_crash(self, key: str) -> None:
        # Warmup guards must hold: a frame shorter than any lookback is flat.
        sig = R2_SIGNALS[key]().compute(synth_ohlcv(5))
        assert len(sig) == 5
        assert set(np.unique(sig.to_numpy())).issubset({-1, 0, 1})

    @pytest.mark.parametrize("key", R2_KEYS)
    def test_capitalised_columns_accepted(self, key: str) -> None:
        data = synth_ohlcv(300).rename(
            {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        )
        sig = R2_SIGNALS[key]().compute(data)
        assert len(sig) == data.height

    @pytest.mark.parametrize("key", R2_KEYS)
    def test_deterministic(self, key: str) -> None:
        data = synth_ohlcv(400)
        first = R2_SIGNALS[key]().compute(data)
        second = R2_SIGNALS[key]().compute(data)
        assert first.to_list() == second.to_list(), f"{key} is not deterministic"


class TestNoLookAhead:
    @pytest.mark.parametrize("key", R2_KEYS)
    def test_truncation_stability(self, key: str) -> None:
        """A signal at bar i must not change when later bars are removed.

        This is the property that makes a backtest honest, so it is checked
        for every family rather than spot-checked.
        """
        data = synth_ohlcv(500)
        cut = 400
        full = R2_SIGNALS[key]().compute(data).to_list()
        partial = R2_SIGNALS[key]().compute(data.head(cut)).to_list()
        assert full[:cut] == partial, f"{key} depends on future bars"


class TestDirectionality:
    def test_shorts_are_emitted_somewhere(self) -> None:
        """The point of R2 is short capability — at least some family uses it."""
        data = trending_ohlcv(500, up=False)
        emitting = [
            key
            for key in R2_KEYS
            if -1 in set(np.unique(R2_SIGNALS[key]().compute(data).to_numpy()))
        ]
        assert emitting, "no R2 family emitted a short in a downtrend"

    def test_golden_cross_follows_trend(self) -> None:
        from analytics.strategy.signals_r2 import GoldenCross

        sig_up = GoldenCross(fast=10, slow=30).compute(trending_ohlcv(400, up=True))
        sig_down = GoldenCross(fast=10, slow=30).compute(trending_ohlcv(400, up=False))
        assert sig_up.to_numpy().sum() > 0, "no long bias in an uptrend"
        assert sig_down.to_numpy().sum() < 0, "no short bias in a downtrend"


class TestRegistration:
    @pytest.mark.parametrize("key", R2_KEYS)
    def test_in_default_strategies(self, key: str) -> None:
        assert key in signals.DEFAULT_STRATEGIES

    @pytest.mark.parametrize("key", R2_KEYS)
    def test_in_entry_types(self, key: str) -> None:
        from analytics.strategy.spec import ENTRY_TYPES

        assert key in ENTRY_TYPES, f"{key} not searchable by the GA"
