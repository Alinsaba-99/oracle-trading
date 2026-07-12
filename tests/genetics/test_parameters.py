"""Tests for the genome parameter definitions and codec."""

from __future__ import annotations

import math

import numpy as np
import pytest

from genetics.genome.codec import clamp, denormalize, normalize, random_value, round_int, validate
from genetics.genome.parameters import CategoricalParameter, ContinuousParameter, IntParameter

# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(42)


# ── ContinuousParameter ─────────────────────────────────────────────


class TestContinuousParameter:
    def test_bounds_scale(self) -> None:
        """Linear scaling maps [low, high] to [0, 1]."""
        p = ContinuousParameter("test", low=0.0, high=100.0)
        assert normalize(0.0, p) == 0.0
        assert normalize(50.0, p) == 0.5
        assert normalize(100.0, p) == 1.0

    def test_clamp_clips_to_bounds(self) -> None:
        p = ContinuousParameter("test", low=0.0, high=100.0)
        assert clamp(-10.0, p) == 0.0
        assert clamp(50.0, p) == 50.0
        assert clamp(150.0, p) == 100.0

    def test_denormalize_roundtrip(self) -> None:
        p = ContinuousParameter("test", low=-1.0, high=1.0)
        raw = 0.5
        norm = normalize(raw, p)
        assert norm == 0.75
        assert denormalize(norm, p) == pytest.approx(raw)

    def test_log_scale(self) -> None:
        p = ContinuousParameter("test", low=1.0, high=100.0, scaling="log")
        # log(1)=0, log(100)=log(100)
        assert normalize(1.0, p) == 0.0
        assert normalize(100.0, p) == 1.0
        # 10 should map to log(10)/log(100) = 1/2 in log-space
        expected = math.log(10) / math.log(100)
        assert normalize(10.0, p) == pytest.approx(expected)

    def test_log_roundtrip(self) -> None:
        p = ContinuousParameter("test", low=1.0, high=100.0, scaling="log")
        for raw in [1.0, 5.0, 10.0, 50.0, 100.0]:
            norm = normalize(raw, p)
            back = denormalize(norm, p)
            assert back == pytest.approx(raw, rel=1e-10)

    def test_validation(self) -> None:
        p = ContinuousParameter("test", low=0.0, high=100.0)
        assert validate(50.0, p)
        assert validate(0.0, p)
        assert validate(100.0, p)
        assert not validate(-1.0, p)
        assert not validate(101.0, p)
        assert not validate("abc", p)

    def test_random_value_in_bounds(self, rng: np.random.Generator) -> None:
        p = ContinuousParameter("test", low=-50.0, high=50.0, init_range=(0.0, 1.0))
        for _ in range(100):
            val = random_value(p, rng)
            assert isinstance(val, float)
            assert -50.0 <= val <= 50.0

    def test_zero_range_raises(self) -> None:
        with pytest.raises(ValueError, match="must be < high"):
            ContinuousParameter("bad", low=5.0, high=5.0)

    def test_log_requires_positive_low(self) -> None:
        with pytest.raises(ValueError, match="requires low > 0"):
            ContinuousParameter("bad", low=0.0, high=10.0, scaling="log")


# ── IntParameter ────────────────────────────────────────────────────


class TestIntParameter:
    def test_bounds_scale(self) -> None:
        p = IntParameter("test", low=10, high=20)
        assert normalize(10.0, p) == 0.0
        assert normalize(15.0, p) == 0.5
        assert normalize(20.0, p) == 1.0

    def test_rounding_consistency(self) -> None:
        """round_int uses round-half-to-even."""
        assert round_int(37.6) == 38
        assert round_int(37.4) == 37
        assert round_int(37.5) == 38  # half-to-even -> 38

    def test_clamp_returns_int(self) -> None:
        p = IntParameter("test", low=0, high=10)
        result = clamp(-5.0, p)
        assert isinstance(result, int)
        assert result == 0

        result = clamp(15.0, p)
        assert isinstance(result, int)
        assert result == 10

    def test_denormalize_returns_int(self) -> None:
        p = IntParameter("test", low=0, high=10)
        back = denormalize(0.5, p)
        assert isinstance(back, int)
        assert back == 5

    def test_log_scale(self) -> None:
        p = IntParameter("test", low=1, high=100, scaling="log")
        norm = normalize(1.0, p)
        assert norm == 0.0
        back = denormalize(norm, p)
        assert isinstance(back, int)
        assert back >= 1

    def test_validation(self) -> None:
        p = IntParameter("test", low=0, high=10)
        assert validate(5, p)
        assert validate(5.0, p)
        assert validate(0, p)
        assert validate(10, p)
        assert not validate(11, p)
        assert not validate("abc", p)

    def test_random_value_returns_int(self, rng: np.random.Generator) -> None:
        p = IntParameter("test", low=0, high=100)
        for _ in range(100):
            val = random_value(p, rng)
            assert isinstance(val, int)
            assert 0 <= val <= 100

    def test_zero_range_raises(self) -> None:
        with pytest.raises(ValueError, match="must be < high"):
            IntParameter("bad", low=5, high=5)


# ── CategoricalParameter ────────────────────────────────────────────


class TestCategoricalParameter:
    def test_validation(self) -> None:
        p = CategoricalParameter("mode", categories=["long", "short", "neutral"])
        assert validate("long", p)
        assert validate("short", p)
        assert not validate("flat", p)
        assert not validate(123, p)

    def test_normalize_and_denormalize(self) -> None:
        p = CategoricalParameter("mode", categories=["a", "b", "c"])
        # Normalize is done by encode; denormalize directly handles cats
        result_a = denormalize(0.0, p)
        assert result_a == "a"
        result_c = denormalize(1.0, p)
        assert result_c == "c"
        result_b = denormalize(0.5, p)
        assert result_b in ("a", "b", "c")  # could be either; depends on rounding

    def test_single_category(self) -> None:
        p = CategoricalParameter("fixed", categories=["only"])
        assert validate("only", p)
        assert not validate("other", p)
        assert denormalize(0.0, p) == "only"
        assert denormalize(0.999, p) == "only"

    def test_clamp_snaps_to_first_category(self) -> None:
        p = CategoricalParameter("mode", categories=["a", "b"])
        assert clamp("b", p) == "b"
        assert clamp("invalid", p) == "a"
        assert clamp(42, p) == "a"

    def test_random_value(self, rng: np.random.Generator) -> None:
        p = CategoricalParameter("mode", categories=["a", "b", "c"])
        seen: set[str] = set()
        for _ in range(200):
            val = random_value(p, rng)
            assert isinstance(val, str)
            assert val in p.categories
            seen.add(val)
        assert len(seen) >= 2  # at least two different categories

    def test_empty_categories_raises(self) -> None:
        with pytest.raises(ValueError, match="must be non-empty"):
            CategoricalParameter("bad", categories=[])

    def test_weights_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="must match categories"):
            CategoricalParameter("bad", categories=["a", "b"], weights=[0.5])
