"""Tests per tutti gli operatori alpha in genetics/alpha/operators.py."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from genetics.alpha.operators import (
    OPERATORS_MAP,
    abs_,
    add,
    correlation,
    covariance,
    delta,
    div,
    ema,
    leaf_close,
    leaf_high,
    leaf_low,
    leaf_open,
    leaf_returns,
    leaf_volume,
    leaf_vwap,
    log_,
    mul,
    neg,
    rank,
    scale,
    sign,
    sma,
    sqrt_,
    sub,
    ts_argmax,
    ts_argmin,
    ts_max,
    ts_mean,
    ts_min,
    ts_prod,
    ts_std,
    ts_sum,
    zscore,
)

# ============================================================
#  Helpers
# ============================================================

RTOL = 1e-9
ATOL = 1e-12

# ============================================================
#  Time-series operators
# ============================================================


class TestTSMean:
    def test_basic(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = ts_mean(x, 3)
        assert len(result) == 5
        assert np.isclose(result[2], 2.0)  # mean([1,2,3])
        assert np.isclose(result[4], 4.0)  # mean([3,4,5])

    def test_head_filled_with_x_d_mean(self):
        x = np.array([10.0, 20.0, 30.0, 40.0])
        result = ts_mean(x, 3)
        # head = mean(x[:3]) = mean([10,20,30]) = 20
        assert np.isclose(result[0], 20.0)
        assert np.isclose(result[1], 20.0)

    def test_short_series_zeros(self):
        x = np.array([1.0, 2.0])
        result = ts_mean(x, 5)
        assert np.allclose(result, [0.0, 0.0])

    def test_single_element(self):
        x = np.array([42.0])
        result = ts_mean(x, 3)
        assert result == [0.0]

    def test_nan_input(self):
        x = np.array([1.0, np.nan, 3.0, 4.0, 5.0])
        result = ts_mean(x, 3)
        assert not np.any(np.isnan(result))


class TestTSStd:
    def test_basic(self):
        x = np.array([1.0, 1.0, 1.0, 5.0, 5.0])
        result = ts_std(x, 3)
        assert np.isclose(result[2], 0.0)  # std([1,1,1])
        assert np.isclose(result[3], np.std([1, 1, 5]), rtol=RTOL, atol=ATOL)

    def test_head_is_one(self):
        x = np.array([10.0, 20.0, 30.0])
        result = ts_std(x, 3)
        assert np.isclose(result[0], 1.0)
        assert np.isclose(result[1], 1.0)

    def test_short_series_zeros(self):
        assert np.allclose(ts_std(np.ones(2), 5), [0.0, 0.0])

    def test_constant_series(self):
        x = np.ones(5)
        result = ts_std(x, 3)
        assert np.allclose(result[2:], 0.0, atol=ATOL)


class TestTSSum:
    def test_basic(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = ts_sum(x, 3)
        assert np.isclose(result[0], 1.0)  # sum([1])
        assert np.isclose(result[1], 3.0)  # sum([1,2])
        assert np.isclose(result[2], 6.0)  # sum([1,2,3])
        assert np.isclose(result[3], 9.0)  # sum([2,3,4])
        assert np.isclose(result[4], 12.0)  # sum([3,4,5])

    def test_short_series(self):
        assert np.allclose(ts_sum(np.ones(2), 5), [0, 0])


class TestTSProd:
    def test_basic(self):
        x = np.array([2.0, 3.0, 4.0, 5.0])
        result = ts_prod(x, 3)
        assert np.isclose(result[0], 2.0)  # prod([2])
        assert np.isclose(result[1], 6.0)  # prod([2,3])
        assert np.isclose(result[2], 24.0)  # prod([2,3,4])
        assert np.isclose(result[3], 60.0)  # prod([3,4,5])

    def test_short_series(self):
        assert np.allclose(ts_prod(np.ones(2), 5), [0, 0])


class TestTSMin:
    def test_basic(self):
        x = np.array([3.0, 1.0, 4.0, 1.0, 5.0])
        result = ts_min(x, 3)
        assert np.isclose(result[0], 3.0)  # min([3])
        assert np.isclose(result[1], 1.0)  # min([3,1])
        assert np.isclose(result[2], 1.0)  # min([3,1,4])
        assert np.isclose(result[3], 1.0)  # min([1,4,1])
        assert np.isclose(result[4], 1.0)  # min([4,1,5])


class TestTSMax:
    def test_basic(self):
        x = np.array([1.0, 5.0, 3.0, 2.0, 4.0])
        result = ts_max(x, 3)
        assert np.isclose(result[0], 1.0)  # max([1])
        assert np.isclose(result[1], 5.0)  # max([1,5])
        assert np.isclose(result[2], 5.0)  # max([1,5,3])
        assert np.isclose(result[3], 5.0)  # max([5,3,2])
        assert np.isclose(result[4], 4.0)  # max([3,2,4])


class TestTSArgMax:
    def test_basic(self):
        x = np.array([1.0, 5.0, 3.0, 4.0, 2.0])
        result = ts_argmax(x, 3)
        # window [0:3]=[1,5,3] argmax=1 → days_since = 3-1-1 = 1
        assert np.isclose(result[2], 1.0)
        # window [1:4]=[5,3,4] argmax=0 → days_since = 3-1-0 = 2
        assert np.isclose(result[3], 2.0)

    def test_max_at_rightmost(self):
        x = np.array([1.0, 2.0, 3.0])
        result = ts_argmax(x, 3)
        assert np.isclose(result[2], 0.0)  # max at last pos

    def test_max_at_leftmost(self):
        x = np.array([3.0, 2.0, 1.0])
        result = ts_argmax(x, 3)
        assert np.isclose(result[2], 2.0)  # max 2 days ago

    def test_head_prefix(self):
        x = np.array([10.0, 5.0, 3.0])
        result = ts_argmax(x, 3)
        # i=0: prefix [10], argmax=0, k-1-0 = 0
        assert np.isclose(result[0], 0.0)
        # i=1: prefix [10,5], argmax=0, k-1-0 = 2-1-0 = 1
        assert np.isclose(result[1], 1.0)


class TestTSArgMin:
    def test_basic(self):
        x = np.array([5.0, 1.0, 3.0, 2.0, 4.0])
        result = ts_argmin(x, 3)
        # window [0:3]=[5,1,3] argmin=1 → days_since = 3-1-1 = 1
        assert np.isclose(result[2], 1.0)

    def test_min_at_rightmost(self):
        x = np.array([3.0, 2.0, 1.0])
        result = ts_argmin(x, 3)
        assert np.isclose(result[2], 0.0)

    def test_head_prefix(self):
        x = np.array([5.0, 10.0, 3.0])
        result = ts_argmin(x, 3)
        # i=0: prefix [5], argmin=0, k-1-0 = 0
        assert np.isclose(result[0], 0.0)
        # i=1: prefix [5,10], argmin=0, k-1-0 = 1
        assert np.isclose(result[1], 1.0)


# ============================================================
#  Cross-sectional operators
# ============================================================


class TestRank:
    def test_basic(self):
        x = np.array([3.0, 1.0, 2.0])
        result = rank(x)
        assert np.isclose(result[0], 1.0)  # highest → rank 1
        assert np.isclose(result[1], 0.0)  # lowest → rank 0
        assert np.isclose(result[2], 0.5)  # middle → rank 0.5

    def test_single_element(self):
        assert np.allclose(rank(np.array([5.0])), [0.0])

    def test_two_elements(self):
        r = rank(np.array([10.0, 20.0]))
        assert np.isclose(r[0], 0.0)
        assert np.isclose(r[1], 1.0)

    def test_all_equal(self):
        r = rank(np.ones(4))
        # All get same rank (0/3, 1/3, 2/3, 3/3 with ties broken by position)
        # argsort of equal values uses stable order: 0,1,2,3 → ranks / 3
        assert np.allclose(r, [0.0, 1.0 / 3, 2.0 / 3, 1.0])

    def test_with_nan(self):
        x = np.array([1.0, np.nan, 3.0, np.nan])
        r = rank(x)
        assert not np.any(np.isnan(r))
        assert r.min() >= 0.0 and r.max() <= 1.0


class TestScale:
    def test_sum_abs_one(self):
        x = np.array([2.0, -1.0, 3.0])
        result = scale(x)
        assert np.isclose(np.sum(np.abs(result)), 1.0)
        # sum(abs)=6 → values: 2/6, -1/6, 3/6
        assert np.allclose(result, [2.0 / 6, -1.0 / 6, 3.0 / 6])

    def test_all_zeros(self):
        assert np.allclose(scale(np.zeros(3)), [0, 0, 0])

    def test_single_element(self):
        assert np.isclose(scale(np.array([5.0])), 1.0)

    def test_negative_only(self):
        x = np.array([-2.0, -4.0])
        result = scale(x)
        assert np.isclose(np.sum(np.abs(result)), 1.0)
        assert np.isclose(result[0], -1.0 / 3)
        assert np.isclose(result[1], -2.0 / 3)


class TestZScore:
    def test_basic(self):
        x = np.array([1.0, 2.0, 3.0])
        result = zscore(x)
        # mean=2, std≈0.816 → (-1.225, 0, 1.225)
        assert np.isclose(np.mean(result), 0.0, atol=ATOL)
        assert np.isclose(np.std(result), 1.0, atol=1e-6)

    def test_constant_zeros(self):
        assert np.allclose(zscore(np.ones(5)), [0, 0, 0, 0, 0])

    def test_single_element(self):
        assert np.allclose(zscore(np.array([42.0])), [0.0])

    def test_nan_input(self):
        x = np.array([np.nan, 1.0, np.nan, 3.0])
        r = zscore(x)
        assert not np.any(np.isnan(r))


# ============================================================
#  Math operators
# ============================================================


class TestMath:
    def test_neg(self):
        assert np.allclose(neg(np.array([1, -2, 0])), [-1, 2, 0])

    def test_add(self):
        assert np.allclose(add(np.array([1, 2]), np.array([3, 4])), [4, 6])

    def test_sub(self):
        assert np.allclose(sub(np.array([5, 3]), np.array([2, 1])), [3, 2])

    def test_mul(self):
        assert np.allclose(mul(np.array([2, 3]), np.array([4, 5])), [8, 15])

    def test_div_safe(self):
        result = div(np.array([1.0, 2.0, 3.0]), np.array([2.0, 0.0, -0.0]))
        assert np.isclose(result[0], 0.5)
        assert result[1] <= 2e10  # 2.0/1e-10 = 2e10

    def test_div_by_epsilon(self):
        result = div(np.array([5.0]), np.array([0.0]))
        assert result[0] <= 5e10  # 5/1e-10 = 5e10
        assert np.isfinite(result[0])

    def test_abs(self):
        assert np.allclose(abs_(np.array([-3, 0, 3])), [3, 0, 3])

    def test_sign(self):
        assert np.allclose(sign(np.array([-5, 0, 8])), [-1, 0, 1])

    def test_log(self):
        x = np.array([1.0, np.e, np.e**2])
        result = log_(x)
        assert np.isclose(result[0], 0.0, atol=1e-9)
        assert np.isclose(result[1], 1.0, atol=1e-6)
        assert np.isclose(result[2], 2.0, atol=1e-6)

    def test_log_zero(self):
        result = log_(np.array([0.0]))
        assert np.isfinite(result[0])

    def test_log_negative(self):
        result = log_(np.array([-1.0]))
        assert np.isfinite(result[0])

    def test_sqrt(self):
        assert np.allclose(sqrt_(np.array([4.0, 9.0, 0.0])), [2.0, 3.0, 0.0])

    def test_sqrt_negative(self):
        result = sqrt_(np.array([-4.0]))
        assert np.isclose(result[0], 2.0)


# ============================================================
#  Financial operators
# ============================================================


class TestCorrelation:
    def test_perfect_positive(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = x * 2
        result = correlation(x, y, 3)
        # Full windows → corr = 1
        assert np.isclose(result[2], 1.0, atol=ATOL)
        assert np.isclose(result[4], 1.0, atol=ATOL)

    def test_perfect_negative(self):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([3.0, 2.0, 1.0])
        result = correlation(x, y, 3)
        assert np.isclose(result[2], -1.0, atol=1e-10)

    def test_short_series(self):
        assert np.allclose(correlation(np.ones(2), np.ones(2), 5), [0, 0])

    def test_constant_input_no_nan(self):
        x = np.ones(5)
        result = correlation(x, x, 3)
        assert not np.any(np.isnan(result))


class TestCovariance:
    def test_basic(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = covariance(x, x, 3)
        # cov(x,x) = var(x)
        assert np.isclose(result[2], np.var([1, 2, 3], ddof=1), rtol=RTOL, atol=ATOL)
        assert np.isclose(result[4], np.var([3, 4, 5], ddof=1), rtol=RTOL, atol=ATOL)

    def test_short_series(self):
        assert np.allclose(covariance(np.ones(2), np.ones(2), 5), [0, 0])


class TestDelta:
    def test_basic(self):
        x = np.array([10.0, 20.0, 15.0, 25.0])
        result = delta(x, 2)
        assert np.isclose(result[0], 0.0)
        assert np.isclose(result[1], 0.0)
        assert np.isclose(result[2], 5.0)  # 15 - 10
        assert np.isclose(result[3], 5.0)  # 25 - 20

    def test_shift_one(self):
        x = np.array([1.0, 3.0, 6.0, 10.0])
        result = delta(x, 1)
        assert np.isclose(result[0], 0.0)
        assert np.isclose(result[1], 2.0)  # 3-1
        assert np.isclose(result[2], 3.0)  # 6-3
        assert np.isclose(result[3], 4.0)  # 10-6

    def test_short_series(self):
        assert np.allclose(delta(np.array([1.0, 2.0]), 5), [0, 0])


class TestSMA:
    def test_alias_of_ts_mean(self):
        assert sma is ts_mean

    def test_basic(self):
        x = np.array([1.0, 2.0, 3.0, 4.0])
        result = sma(x, 3)
        assert np.isclose(result[2], 2.0)
        assert np.isclose(result[3], 3.0)


class TestEMA:
    def test_basic(self):
        x = np.array([1.0, 2.0, 3.0])
        result = ema(x, 3)
        expected = np.array([1.0, 0.5 * 2 + 0.5 * 1, 0.5 * 3 + 0.5 * 1.5])
        assert np.allclose(result, expected, rtol=RTOL, atol=ATOL)

    def test_short_series(self):
        assert np.allclose(ema(np.array([1.0, 2.0]), 5), [0, 0])

    def test_constant(self):
        x = np.ones(5) * 5.0
        result = ema(x, 3)
        assert np.allclose(result, [5.0, 5.0, 5.0, 5.0, 5.0])

    def test_increasing(self):
        x = np.array([1.0, 2.0, 4.0, 8.0])
        result = ema(x, 3)
        # alpha = 0.5
        # i=0: 1.0
        # i=1: 0.5*2 + 0.5*1 = 1.5
        # i=2: 0.5*4 + 0.5*1.5 = 2.75
        # i=3: 0.5*8 + 0.5*2.75 = 5.375
        expected = np.array([1.0, 1.5, 2.75, 5.375])
        assert np.allclose(result, expected, rtol=RTOL, atol=ATOL)


# ============================================================
#  Leaf nodes
# ============================================================


class TestLeafNodes:
    @pytest.fixture
    def df(self):
        return pl.DataFrame(
            {
                "close": [100.0, 101.0, 102.0],
                "open": [99.0, 100.5, 101.5],
                "high": [102.0, 103.0, 104.0],
                "low": [98.0, 99.0, 100.0],
                "volume": [1000, 1500, 1200],
            }
        )

    def test_close(self, df):
        assert np.allclose(leaf_close(df), [100.0, 101.0, 102.0])

    def test_open(self, df):
        assert np.allclose(leaf_open(df), [99.0, 100.5, 101.5])

    def test_high(self, df):
        assert np.allclose(leaf_high(df), [102.0, 103.0, 104.0])

    def test_low(self, df):
        assert np.allclose(leaf_low(df), [98.0, 99.0, 100.0])

    def test_volume(self, df):
        assert np.allclose(leaf_volume(df), [1000, 1500, 1200])

    def test_returns(self, df):
        r = leaf_returns(df)
        assert np.isclose(r[0], 0.0)
        assert np.isclose(r[1], 101.0 / 100.0 - 1.0)
        assert np.isclose(r[2], 102.0 / 101.0 - 1.0)

    def test_vwap(self, df):
        v = leaf_vwap(df)
        assert np.isclose(v[0], (100 + 102 + 98) / 3)
        assert np.isclose(v[1], (101 + 103 + 99) / 3)
        assert np.isclose(v[2], (102 + 104 + 100) / 3)


# ============================================================
#  OPERATORS_MAP
# ============================================================


class TestOperatorsMap:
    def test_all_operators_present(self):
        """Il dizionario contiene tutte le 32 funzioni."""
        expected = {
            # time-series
            "ts_mean",
            "ts_std",
            "ts_sum",
            "ts_prod",
            "ts_min",
            "ts_max",
            "ts_argmax",
            "ts_argmin",
            # cross-sectional
            "rank",
            "scale",
            "zscore",
            # math
            "neg",
            "add",
            "sub",
            "mul",
            "div",
            "abs",
            "sign",
            "log",
            "sqrt",
            # financial
            "correlation",
            "covariance",
            "delta",
            "sma",
            "ema",
            # leaf
            "leaf_close",
            "leaf_open",
            "leaf_high",
            "leaf_low",
            "leaf_volume",
            "leaf_returns",
            "leaf_vwap",
        }
        assert set(OPERATORS_MAP.keys()) == expected

    def test_entries_are_callable(self):
        for name, fn in OPERATORS_MAP.items():
            assert callable(fn), f"{name} non e` callable"

    def test_sma_points_to_ts_mean(self):
        assert OPERATORS_MAP["sma"] is ts_mean

    def test_abs_points_to_abs_(self):
        assert OPERATORS_MAP["abs"] is abs_
