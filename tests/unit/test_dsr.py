"""Unit tests for analytics/qualification/dsr.py (BL-500).

These tests verify the wrapper around the MIT-licensed ``purgedcv``
package and Apache-2.0 ``mnemox-ai/deflated-sharpe`` package, providing
DSR + PBO + CPCV + PurgedKFold overfitting diagnostics required by
ADR-017 (supersedes ``bootstrap_luck_p_value`` from ADR-016).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from analytics.qualification.dsr import (
    combinatorial_purged_cv,
    deflated_sharpe_ratio,
    has_standalone_dsr,
    probabilistic_sharpe_ratio,
    probability_of_backtest_overfitting,
    purged_k_fold,
    select_backtest_overfit_metrics,
)


def _make_returns(
    seed: int = 42, n: int = 252, mu: float = 0.0005, sigma: float = 0.01
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mu, sigma, size=n)


def test_dsr_returns_float_in_zero_one_range() -> None:
    returns = _make_returns()
    dsr = deflated_sharpe_ratio(returns, n_trials=10)
    assert dsr is not None
    assert 0.0 <= dsr <= 1.0


def test_dsr_more_trials_lowers_dsr() -> None:
    """More trials => higher expected max Sharpe from luck => lower DSR."""
    rng = np.random.default_rng(7)
    returns = rng.normal(0.0008, 0.01, size=500)  # positive Sharpe
    dsr_few = deflated_sharpe_ratio(returns, n_trials=2)
    dsr_many = deflated_sharpe_ratio(returns, n_trials=200)
    assert dsr_few is not None and dsr_many is not None
    assert dsr_many < dsr_few, f"DSR should drop with more trials: {dsr_few=}, {dsr_many=}"


def test_dsr_returns_none_for_insufficient_data() -> None:
    assert deflated_sharpe_ratio(np.array([0.01, 0.02]), n_trials=10) is None
    assert deflated_sharpe_ratio(np.array([]), n_trials=10) is None
    assert deflated_sharpe_ratio(_make_returns(), n_trials=0) is None


def test_dsr_returns_none_for_zero_variance() -> None:
    returns = np.ones(50)  # zero variance
    assert deflated_sharpe_ratio(returns, n_trials=5) is None


def test_psr_returns_float_in_zero_one_range() -> None:
    returns = _make_returns()
    psr = probabilistic_sharpe_ratio(returns, benchmark_sharpe=0.0)
    assert psr is not None
    assert 0.0 <= psr <= 1.0


def test_psr_higher_benchmark_lowers_psr() -> None:
    rng = np.random.default_rng(11)
    returns = rng.normal(0.0008, 0.01, size=500)
    psr_low = probabilistic_sharpe_ratio(returns, benchmark_sharpe=0.0)
    psr_high = probabilistic_sharpe_ratio(returns, benchmark_sharpe=2.0)
    assert psr_low is not None and psr_high is not None
    assert psr_high < psr_low


def test_psr_returns_none_for_insufficient_data() -> None:
    assert probabilistic_sharpe_ratio(np.array([0.01, 0.02])) is None


def test_pbo_returns_dict_with_pbo_field_in_zero_one() -> None:
    rng = np.random.default_rng(13)
    # 10 strategies × 1000 periods — random returns => PBO should be ~0.5 (no real edge)
    mat = rng.normal(0, 0.01, size=(10, 1000))
    result = probability_of_backtest_overfitting(mat, n_splits=16)
    assert "pbo" in result
    pbo = result["pbo"]
    assert pbo is not None
    assert 0.0 <= pbo <= 1.0
    n_combos = result["n_combos"]
    assert n_combos is not None
    assert n_combos > 0


def test_pbo_returns_none_pbo_for_insufficient_data() -> None:
    assert probability_of_backtest_overfitting(np.array([[0.01]]))["pbo"] is None
    assert probability_of_backtest_overfitting(np.array([]).reshape(0, 0))["pbo"] is None


def test_pbo_returns_none_pbo_for_nan_data() -> None:
    mat = np.full((5, 100), np.nan)
    assert probability_of_backtest_overfitting(mat)["pbo"] is None


def test_purged_k_fold_returns_n_splits_pairs() -> None:
    n = 100
    prediction_times = pd.date_range("2020-01-01", periods=n, freq="D")
    evaluation_times = prediction_times + pd.Timedelta(days=1)
    folds = purged_k_fold(
        prediction_times=prediction_times, evaluation_times=evaluation_times, n_splits=5
    )
    assert len(folds) == 5
    for train_idx, test_idx in folds:
        assert len(train_idx) > 0
        assert len(test_idx) > 0
        assert len(set(train_idx.tolist()) & set(test_idx.tolist())) == 0, "train/test overlap"


def test_purged_k_fold_with_purge_removes_boundary_samples() -> None:
    n = 60
    prediction_times = pd.date_range("2020-01-01", periods=n, freq="D")
    evaluation_times = prediction_times + pd.Timedelta(days=1)
    folds_plain = purged_k_fold(prediction_times, evaluation_times, n_splits=3)
    folds_purged = purged_k_fold(
        prediction_times, evaluation_times, n_splits=3, purge_horizon=pd.Timedelta(days=2)
    )
    plain_train_size = sum(len(t) for t, _ in folds_plain)
    purged_train_size = sum(len(t) for t, _ in folds_purged)
    assert purged_train_size <= plain_train_size


def test_combinatorial_purged_cv_produces_c_n_k_folds() -> None:
    n = 100
    prediction_times = pd.date_range("2020-01-01", periods=n, freq="D")
    evaluation_times = prediction_times + pd.Timedelta(days=1)
    n_groups = 6
    n_test = 2
    expected_folds = math.comb(n_groups, n_test)
    folds = combinatorial_purged_cv(
        prediction_times=prediction_times,
        evaluation_times=evaluation_times,
        n_groups=n_groups,
        n_test_groups=n_test,
    )
    assert len(folds) == expected_folds
    for train_idx, test_idx in folds:
        assert len(train_idx) > 0
        assert len(test_idx) > 0
        assert len(set(train_idx.tolist()) & set(test_idx.tolist())) == 0


def test_select_backtest_overfit_metrics_returns_both_dsr_and_psr() -> None:
    returns = _make_returns()
    metrics = select_backtest_overfit_metrics(returns.tolist(), n_trials=20)
    assert "deflated_sharpe_ratio" in metrics
    assert "probabilistic_sharpe_ratio" in metrics
    assert metrics["deflated_sharpe_ratio"] is not None
    assert metrics["probabilistic_sharpe_ratio"] is not None


def test_has_standalone_dsr_returns_bool() -> None:
    assert isinstance(has_standalone_dsr(), bool)
