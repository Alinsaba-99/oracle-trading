"""Golden vectors for the canonical metrics module (P1-A, ADR-021).

These tests freeze the ONE metric semantics the whole repository commits
to.  After the R5 31x Sharpe-inflation incident and the 2026-08-19 audit
(F-01: five divergent Sharpe implementations), any change here is a
decision, not an accident — it requires an ADR amendment AND a conscious
update of every golden vector below.

Characterized 2026-08-20 before unification:

    case               statistics   execution   walkforward  MetricsCalculator
    empty              nan          0.0         0.0          0.0
    single             nan          0.0         0.0          0.0
    zero_var_positive  +inf         0.0         0.0          +inf
    zero_var_negative  0.0          0.0         0.0          -inf
    zero_var_zero      0.0          0.0         0.0          0.0
    mixed              5.897605365691202 (all four agree at ppy=252)

Adopted semantics: n<2 -> 0.0; zero-variance -> sign of mean (+inf/-inf/0).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from analytics.metrics import (
    DEFAULT_PERIODS_PER_YEAR,
    calmar_ratio,
    max_drawdown_from_returns,
    sharpe_ratio,
    sortino_ratio,
)

EMPTY: list[float] = []
SINGLE = [0.01]
ZERO_VAR_POS = [0.01, 0.01, 0.01]
ZERO_VAR_NEG = [-0.01, -0.01, -0.01]
ZERO_VAR_ZERO = [0.0, 0.0, 0.0]
MIXED = [0.02, 0.01, -0.01, 0.005, 0.015, -0.005, 0.01, -0.02, 0.03, 0.0]

# Golden value: characterized on 2026-08-20 across all legacy implementations
# at ppy=252 (statistics/execution/walkforward/MetricsCalculator agree).
MIXED_SHARPE_252 = 5.897605365691202


class TestSharpeGoldenVectors:
    def test_empty_is_zero(self) -> None:
        assert sharpe_ratio(EMPTY) == 0.0

    def test_single_observation_is_zero(self) -> None:
        assert sharpe_ratio(SINGLE) == 0.0

    def test_zero_variance_positive_is_plus_inf(self) -> None:
        assert sharpe_ratio(ZERO_VAR_POS) == math.inf

    def test_zero_variance_negative_is_minus_inf(self) -> None:
        assert sharpe_ratio(ZERO_VAR_NEG) == -math.inf

    def test_zero_variance_zero_is_zero(self) -> None:
        assert sharpe_ratio(ZERO_VAR_ZERO) == 0.0

    def test_mixed_golden_value_252(self) -> None:
        assert sharpe_ratio(MIXED) == pytest.approx(MIXED_SHARPE_252, rel=1e-12)

    def test_mixed_annualization_scales_with_sqrt_ppy(self) -> None:
        # Golden vector: ppy=12 (monthly) and ppy=1560 (hourly, 252*6.25).
        assert sharpe_ratio(MIXED, periods_per_year=12) == pytest.approx(1.286963, rel=1e-5)
        assert sharpe_ratio(MIXED, periods_per_year=1560) == pytest.approx(14.673636, rel=1e-5)

    def test_numpy_and_list_inputs_agree(self) -> None:
        arr = np.asarray(MIXED, dtype=np.float64)
        assert sharpe_ratio(arr) == sharpe_ratio(MIXED)

    def test_non_finite_entries_are_cleaned(self) -> None:
        with_nan = [*MIXED, float("nan"), float("inf")]
        assert sharpe_ratio(with_nan) == pytest.approx(MIXED_SHARPE_252, rel=1e-12)

    def test_default_ppy_is_252(self) -> None:
        assert DEFAULT_PERIODS_PER_YEAR == 252


class TestSortinoGoldenVectors:
    def test_no_negative_periods_positive_mean_is_plus_inf(self) -> None:
        assert sortino_ratio(ZERO_VAR_POS) == math.inf

    def test_mixed_uses_downside_deviation(self) -> None:
        # mean(MIXED)=0.0105, downside values: -0.01,-0.005,-0.02
        arr = np.asarray(MIXED)
        downside = arr[arr < 0]
        expected = float(np.mean(arr)) / float(np.std(downside, ddof=1)) * math.sqrt(252)
        assert sortino_ratio(MIXED) == pytest.approx(expected, rel=1e-12)

    def test_single_is_zero(self) -> None:
        assert sortino_ratio(SINGLE) == 0.0

    def test_single_downside_positive_mean_is_plus_inf(self) -> None:
        # Downside deviation is undefined with one observation; the
        # zero-variance rule applies (golden vector, ADR-021).
        assert sortino_ratio([0.01, 0.02, -0.01]) == math.inf


class TestCalmarGoldenVectors:
    def test_mixed_calmar_golden(self) -> None:
        value = calmar_ratio(MIXED)
        # Growth over the 10 bars: prod(1+r) = 1.04572...
        growth = float(np.prod(1.0 + np.asarray(MIXED)))
        ann = growth ** (252 / len(MIXED)) - 1.0
        dd = max_drawdown_from_returns(MIXED)
        assert value == pytest.approx(ann / dd, rel=1e-12)

    def test_explicit_drawdown_used(self) -> None:
        value = calmar_ratio(MIXED, max_drawdown=0.5)
        growth = float(np.prod(1.0 + np.asarray(MIXED)))
        ann = growth ** (252 / len(MIXED)) - 1.0
        assert value == pytest.approx(ann / 0.5, rel=1e-12)

    def test_zero_drawdown_is_zero(self) -> None:
        assert calmar_ratio(ZERO_VAR_POS, max_drawdown=0.0) == 0.0

    def test_short_series_is_zero(self) -> None:
        assert calmar_ratio(SINGLE) == 0.0


class TestMaxDrawdownGoldenVectors:
    def test_no_drawdown_is_zero(self) -> None:
        assert max_drawdown_from_returns(ZERO_VAR_POS) == 0.0

    def test_simple_drawdown(self) -> None:
        # +10% then -20%: equity 1.1 -> 0.88, drawdown = 0.2
        dd = max_drawdown_from_returns([0.10, -0.20])
        assert dd == pytest.approx(0.2, rel=1e-12)

    def test_empty_is_zero(self) -> None:
        assert max_drawdown_from_returns([]) == 0.0
