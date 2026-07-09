"""Tests for genome encoding, decoding, validation, and signal adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import polars as pl
import pytest

from genetics.genome.parameters import (
    CategoricalParameter,
    ContinuousParameter,
    GenomeParameter,
    IntParameter,
)
from genetics.genome.signal import (
    Genome,
    GenomeConfig,
    GenomeToSignal,
    decode,
    encode,
    validate_genome,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def simple_defs() -> list[GenomeParameter]:
    return [
        ContinuousParameter("weight_momentum", low=-2.0, high=2.0),
        ContinuousParameter("weight_vol", low=0.0, high=1.0),
        IntParameter("lookback", low=5, high=50),
        CategoricalParameter("direction", categories=["long", "short"]),
    ]


@pytest.fixture
def single_defs() -> list[ContinuousParameter]:
    return [ContinuousParameter("single", low=0.0, high=10.0)]


@pytest.fixture
def categorical_only_defs() -> list[CategoricalParameter]:
    return [
        CategoricalParameter("mode", categories=["fast", "slow"]),
        CategoricalParameter("side", categories=["long", "short", "neutral"]),
    ]


# ── encode / decode roundtrip ───────────────────────────────────────


class TestEncodeDecode:
    def test_continuous_roundtrip(self) -> None:
        param_defs = [ContinuousParameter("alpha", low=0.0, high=1.0)]
        raw = {"alpha": 0.75}
        genome = encode(raw, param_defs)
        assert genome.normalized_params == pytest.approx([0.75])
        decoded = decode(genome)
        assert decoded["alpha"] == pytest.approx(0.75)

    def test_int_roundtrip(self) -> None:
        param_defs = [IntParameter("period", low=10, high=20)]
        raw = {"period": 15}
        genome = encode(raw, param_defs)
        decoded = decode(genome)
        assert decoded["period"] == 15

    def test_categorical_roundtrip(self) -> None:
        param_defs = [CategoricalParameter("trend", categories=["up", "down", "side"])]
        raw = {"trend": "down"}
        genome = encode(raw, param_defs)
        decoded = decode(genome)
        assert decoded["trend"] == "down"

    def test_mixed_roundtrip(self, simple_defs: list[GenomeParameter]) -> None:
        raw: dict[str, float | int | str] = {
            "weight_momentum": 1.5,
            "weight_vol": 0.3,
            "lookback": 30,
            "direction": "long",
        }
        genome = encode(raw, simple_defs)
        decoded = decode(genome)
        assert decoded["weight_momentum"] == pytest.approx(1.5, abs=1e-10)
        assert decoded["weight_vol"] == pytest.approx(0.3, abs=1e-10)
        assert decoded["lookback"] == 30
        assert decoded["direction"] == "long"

    def test_encode_missing_key_raises(self) -> None:
        param_defs = [ContinuousParameter("a", low=0.0, high=1.0)]
        with pytest.raises(ValueError, match="Missing"):
            encode({"b": 0.5}, param_defs)

    def test_encode_invalid_category_raises(self) -> None:
        param_defs = [CategoricalParameter("x", categories=["a", "b"])]
        with pytest.raises(ValueError, match="Invalid category"):
            encode({"x": "c"}, param_defs)


# ── bounds clamping ─────────────────────────────────────────────────


class TestBoundsClamping:
    def test_denormalize_out_of_range(self, single_defs: list[ContinuousParameter]) -> None:
        """denormalize is a pure reverse mapping — out-of-range in, out-of-range out."""
        bad_arr: NDArray[np.float64] = np.array([2.5], dtype=np.float64)
        genome = Genome(normalized_params=bad_arr, param_defs=single_defs)
        decoded = decode(genome)
        val = decoded["single"]
        assert isinstance(val, float)
        # 2.5 * 10 = 25.0 — no clamping in denormalize
        assert val == 25.0

    def test_clamp_corrects_denormalized(self, single_defs: list[ContinuousParameter]) -> None:
        """Clamp after denormalize caps to valid range."""
        from genetics.genome.codec import clamp, denormalize

        p = single_defs[0]
        raw = denormalize(2.5, p)
        assert raw == 25.0
        clamped = clamp(raw, p)
        assert clamped == 10.0

        raw_low = denormalize(-0.5, p)
        assert raw_low == -5.0
        clamped_low = clamp(raw_low, p)
        assert clamped_low == 0.0


# ── GenomeToSignal ──────────────────────────────────────────────────


class TestGenomeToSignal:
    def test_returns_valid_signal(self) -> None:
        """GenomeToSignal produces a Series with values in [-1, 0, 1]."""
        param_defs = [
            ContinuousParameter("w1", low=-1.0, high=1.0),
            ContinuousParameter("w2", low=-1.0, high=1.0),
        ]
        raw = {"w1": 0.5, "w2": 0.2}
        genome = encode(raw, param_defs)
        adapter = GenomeToSignal(genome, param_defs)

        # Create test market data
        n = 50
        data = pl.DataFrame({
            "close": pl.Series(
                np.sin(np.linspace(0, 4 * np.pi, n)) + 100.0,
                dtype=pl.Float64,
            ),
        })
        signal = adapter.compute(data)
        assert isinstance(signal, pl.Series)
        assert signal.dtype == pl.Int8
        assert len(signal) == n
        # All values should be -1, 0, or 1
        unique_vals = set(signal.to_list())
        assert unique_vals.issubset({-1, 0, 1})

    def test_categorical_only_signal(self) -> None:
        """With no numeric weights, signal should be all zeros."""
        param_defs = [
            CategoricalParameter("mode", categories=["a", "b"]),
        ]
        raw = {"mode": "a"}
        genome = encode(raw, param_defs)
        adapter = GenomeToSignal(genome, param_defs)

        data = pl.DataFrame({"close": [100.0, 101.0, 102.0]})
        signal = adapter.compute(data)
        assert all(v == 0 for v in signal.to_list())

    def test_single_parameter_signal(self) -> None:
        """Single continuous parameter should still produce valid signal."""
        param_defs = [
            ContinuousParameter("weight", low=-1.0, high=1.0),
        ]
        raw = {"weight": 0.8}
        genome = encode(raw, param_defs)
        adapter = GenomeToSignal(genome, param_defs)

        data = pl.DataFrame({
            "close": pl.Series([100.0, 101.0, 102.0, 101.0, 100.0], dtype=pl.Float64),
        })
        signal = adapter.compute(data)
        assert set(signal.to_list()).issubset({-1, 0, 1})

# ── validate_genome ─────────────────────────────────────────────────


class TestValidateGenome:
    def test_valid_genome(self, simple_defs: list[GenomeParameter]) -> None:
        raw: dict[str, float | int | str] = {
            "weight_momentum": 0.0,
            "weight_vol": 0.5,
            "lookback": 20,
            "direction": "long",
        }
        genome = encode(raw, simple_defs)
        assert validate_genome(genome)

    def test_rejects_wrong_length(self, simple_defs: list[GenomeParameter]) -> None:
        arr: NDArray[np.float64] = np.array([0.5], dtype=np.float64)
        genome = Genome(normalized_params=arr, param_defs=simple_defs)
        assert not validate_genome(genome)

    def test_rejects_nan(self) -> None:
        p = [ContinuousParameter("x", low=0.0, high=1.0)]
        arr: NDArray[np.float64] = np.array([np.nan], dtype=np.float64)
        genome = Genome(normalized_params=arr, param_defs=p)
        assert not validate_genome(genome)

    def test_rejects_inf(self) -> None:
        p = [ContinuousParameter("x", low=0.0, high=1.0)]
        arr: NDArray[np.float64] = np.array([np.inf], dtype=np.float64)
        genome = Genome(normalized_params=arr, param_defs=p)
        assert not validate_genome(genome)

    def test_rejects_out_of_bounds(self) -> None:
        p = [ContinuousParameter("x", low=0.0, high=1.0)]
        arr: NDArray[np.float64] = np.array([1.5], dtype=np.float64)
        genome = Genome(normalized_params=arr, param_defs=p)
        assert not validate_genome(genome)

    def test_empty_config(self) -> None:
        """An empty config with no params is a valid edge case."""
        genome = Genome(
            normalized_params=np.array([], dtype=np.float64),
            param_defs=[],
        )
        assert validate_genome(genome)

    def test_single_parameter_genome_valid(self) -> None:
        p = [ContinuousParameter("x", low=0.0, high=1.0)]
        genome = encode({"x": 0.5}, p)
        assert validate_genome(genome)


# ── GenomeConfig ────────────────────────────────────────────────────


class TestGenomeConfig:
    def test_config_holds_defs(self, simple_defs: list[GenomeParameter]) -> None:
        config = GenomeConfig(n_params=len(simple_defs), param_defs=simple_defs)
        assert config.n_params == 4
        assert config.param_defs == simple_defs
