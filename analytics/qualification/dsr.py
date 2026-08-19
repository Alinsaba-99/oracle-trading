"""Backtest overfitting validation via DSR + PBO + CPCV (BL-500).

Wraps the MIT-licensed ``purgedcv`` package (eslazarev/purged-cross-validation)
and Apache-2.0 ``mnemox-ai/deflated-sharpe`` package to provide the
López de Prado / Bailey AFML overfitting diagnostics required by ADR-017.

These metrics supersede ``bootstrap_luck_p_value`` (ADR-016) which is
deprecated for qualification gates but retained for backward compatibility.

References
----------
- Bailey & López de Prado (2014). "The Deflated Sharpe Ratio." JPM 40(5):94-107.
- Bailey, Borwein, López de Prado & Zhu (2017). "The Probability of
  Backtest Overfitting." PBO via CSCV.
- López de Prado (2018). *Advances in Financial Machine Learning*. Wiley.
  ch.7 (PurgedKFold), ch.8 (DSR), ch.11/12 (CPCV/PBO).
- ESLazarev (2026). ``purgedcv`` — scikit-learn-compatible time-series CV
  with purging, embargo, combinatorial purged CV, and deflated Sharpe ratios.
  https://github.com/eslazarev/purged-cross-validation
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

import numpy as np
from purgedcv import CombinatorialPurgedCV, PurgedKFold
from purgedcv import deflated_sharpe_ratio as _pcv_dsr
from purgedcv import probabilistic_sharpe_ratio as _pcv_psr
from purgedcv import probability_of_backtest_overfitting as _pcv_pbo

try:
    from deflated_sharpe import deflated_sharpe_ratio as _standalone_dsr  # noqa: F401

    _HAS_STANDALONE_DSR = True
except ImportError:  # pragma: no cover
    _HAS_STANDALONE_DSR = False


def deflated_sharpe_ratio(
    returns: np.ndarray, *, n_trials: int, periods_per_year: int = 252
) -> float | None:
    """Compute the Deflated Sharpe Ratio (Bailey & López de Prado 2014).

    The DSR adjusts the observed Sharpe ratio for the number of trials
    attempted, testing whether the 'true' Sharpe remains > 0 after
    multiple-testing correction. ``n_trials`` is the count of strategy
    variants evaluated during the discovery phase (e.g. number of
    parameter combinations in a sweep). When you test M strategies, the
    maximum Sharpe you expect from pure luck grows as
    ``O(sqrt(ln(M)))``; DSR subtracts this expected maximum from the
    observed Sharpe and normalizes by the standard error.

    Parameters
    ----------
    returns
        Periodic strategy returns (1D array of floats).
    n_trials
        Number of strategies tested in the discovery phase. The expected
        maximum Sharpe from pure luck grows as ``O(sqrt(ln(M)))`` over M
        trials; DSR subtracts this from the observed Sharpe.
    periods_per_year
        Annualization factor (252 for daily, 12 for monthly).

    Returns
    -------
    float or None
        The DSR value in [0, 1]; None if input is insufficient.
    """
    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size < 8 or n_trials < 1:
        return None
    var_sharpe = float(clean.var(ddof=1)) if clean.size > 1 else 0.0
    if var_sharpe <= 0:
        return None
    return float(
        _pcv_dsr(
            returns=clean,
            n_trials=int(n_trials),
            var_sharpe=var_sharpe,
            bars_per_year=periods_per_year,
        )
    )


def probabilistic_sharpe_ratio(
    returns: np.ndarray, *, benchmark_sharpe: float = 0.0
) -> float | None:
    """Compute the Probabilistic Sharpe Ratio (Bailey & López de Prado 2012).

    PSR gives the probability that the 'true' Sharpe exceeds a benchmark
    (default 0), accounting for sampling uncertainty, skew, and kurtosis.

    Parameters
    ----------
    returns
        Periodic strategy returns (1D array of floats).
    benchmark_sharpe
        Sharpe benchmark to beat (default 0.0).

    Returns
    -------
    float or None
        PSR in [0, 1]; None if input is insufficient.
    """
    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size < 8:
        return None
    return float(_pcv_psr(returns=clean, benchmark_skill=float(benchmark_sharpe)))


def probability_of_backtest_overfitting(
    returns_matrix: np.ndarray,
    *,
    n_splits: int = 16,
    purge_horizon: int | None = None,
    embargo: int | None = None,
) -> dict[str, float | int | np.ndarray | None]:
    """Estimate the Probability of Backtest Overfitting (PBO) via CSCV.

    Implements the Combinatorially Symmetric Cross-Validation (CSCV)
    method of Bailey, Borwein, López de Prado & Zhu (2017). A PBO near
    1.0 means the in-sample optimal strategy is likely mediocre
    out-of-sample; a PBO < 0.5 is the minimum bar for robustness.

    Parameters
    ----------
    returns_matrix
        2D array of shape (n_trials, n_periods) where each row is the
        return series of one strategy variant tested in the discovery
        phase. All rows must have equal length and no missing data.
    n_splits
        Number of CSCV sub-samples (default 16; must divide n_periods).
    purge_horizon
        Optional purge horizon (samples) to remove label overlap.
    embargo
        Optional embargo (samples) after each test block.

    Returns
    -------
    dict
        Contains ``pbo`` (float in [0,1]), ``slope`` (float),
        ``n_combos`` (int), ``logits`` (np.ndarray), and
        ``is_oos_performance`` (np.ndarray). Returns dict with ``pbo=None``
        if input is insufficient.
    """
    mat = np.asarray(returns_matrix, dtype=float)
    if mat.ndim != 2 or mat.shape[0] < 2 or mat.shape[1] < 8:
        return {
            "pbo": None,
            "slope": None,
            "n_combos": 0,
            "logits": None,
            "is_oos_performance": None,
        }
    if not np.all(np.isfinite(mat)):
        return {
            "pbo": None,
            "slope": None,
            "n_combos": 0,
            "logits": None,
            "is_oos_performance": None,
        }
    try:
        result = _pcv_pbo(
            returns=mat, n_splits=int(n_splits), purge_horizon=purge_horizon, embargo=embargo
        )
    except Exception:  # pragma: no cover
        return {
            "pbo": None,
            "slope": None,
            "n_combos": 0,
            "logits": None,
            "is_oos_performance": None,
        }
    return {
        "pbo": float(result.pbo),
        "slope": float(result.slope),
        "n_combos": int(result.n_combos),
        "logits": np.asarray(result.logits),
        "is_oos_performance": np.asarray(result.is_oos_performance),
    }


def combinatorial_purged_cv(
    prediction_times: Sequence[Any],
    evaluation_times: Sequence[Any],
    *,
    n_groups: int,
    n_test_groups: int,
    purge_horizon: int | None = None,
    embargo: int | None = None,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return (train_idx, test_idx) folds via CombinatorialPurgedCV.

    Implements AFML ch.12 CPCV: combinatorial fold selection with purge
    and embargo to prevent label-overlap information leakage. The number
    of paths reconstructed equals C(n_groups, n_test_groups).

    Parameters
    ----------
    prediction_times
        Timestamps (or integer indices) when each sample's prediction is
        made. Must have same length as the dataset.
    evaluation_times
        Timestamps (or integer indices) when each sample's label is
        evaluated. Must have same length as the dataset.
    n_groups
        Number of groups to split the data into (must be > n_test_groups).
    n_test_groups
        Number of groups held out as test in each fold.
    purge_horizon
        Optional purge horizon to remove label overlap.
    embargo
        Optional embargo after each test block.

    Returns
    -------
    list of (train_idx, test_idx) tuples
        Each fold as a pair of numpy index arrays. The number of folds
        equals C(n_groups, n_test_groups).
    """
    cv = CombinatorialPurgedCV(
        n_splits=int(n_groups),
        n_test_groups=int(n_test_groups),
        prediction_times=np.asarray(prediction_times),
        evaluation_times=np.asarray(evaluation_times),
        purge_horizon=purge_horizon,
        embargo=embargo,
    )
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for train_idx, test_idx in cv.split(np.arange(len(prediction_times))):
        folds.append((np.asarray(train_idx), np.asarray(test_idx)))
    return folds


def purged_k_fold(
    prediction_times: Sequence[Any],
    evaluation_times: Sequence[Any],
    *,
    n_splits: int = 5,
    purge_horizon: int | None = None,
    embargo: int | None = None,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return (train_idx, test_idx) folds via PurgedKFold.

    Implements AFML ch.7 PurgedKFold: contiguous test folds with purge +
    embargo to prevent label-overlap information leakage in walk-forward
    evaluation. Use this instead of standard KFold for any time-series
    cross-validation on strategy returns.

    Parameters
    ----------
    prediction_times
        Timestamps (or integer indices) when each sample's prediction is
        made. Must have same length as the dataset.
    evaluation_times
        Timestamps (or integer indices) when each sample's label is
        evaluated. Must have same length as the dataset.
    n_splits
        Number of folds (default 5).
    purge_horizon
        Optional purge horizon to remove label overlap.
    embargo
        Optional embargo after each test block.

    Returns
    -------
    list of (train_idx, test_idx) tuples
        Each fold as a pair of numpy index arrays.
    """
    cv = PurgedKFold(
        n_splits=int(n_splits),
        prediction_times=np.asarray(prediction_times),
        evaluation_times=np.asarray(evaluation_times),
        purge_horizon=purge_horizon,
        embargo=embargo,
    )
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for train_idx, test_idx in cv.split(np.arange(len(prediction_times))):
        folds.append((np.asarray(train_idx), np.asarray(test_idx)))
    return folds


def select_backtest_overfit_metrics(
    returns: Sequence[float],
    *,
    n_trials: int,
    periods_per_year: int = 252,
    benchmark_sharpe: float = 0.0,
) -> dict[str, float | None]:
    """Return a combined dict of DSR + PSR for one strategy's returns.

    Convenience wrapper to compute both metrics in one call. ``n_trials``
    should match the number of variants evaluated in the discovery sweep
    that produced this strategy (multi-test correction).

    Returns
    -------
    dict with keys ``"deflated_sharpe_ratio"`` and
    ``"probabilistic_sharpe_ratio"``.
    """
    arr = np.asarray(returns, dtype=float)
    return {
        "deflated_sharpe_ratio": deflated_sharpe_ratio(
            arr, n_trials=n_trials, periods_per_year=periods_per_year
        ),
        "probabilistic_sharpe_ratio": probabilistic_sharpe_ratio(
            arr, benchmark_sharpe=benchmark_sharpe
        ),
    }


def has_standalone_dsr() -> bool:
    """Return True if the mnemox-ai/deflated-sharpe fallback is importable."""
    return _HAS_STANDALONE_DSR


__all__: list[str] = [
    "combinatorial_purged_cv",
    "deflated_sharpe_ratio",
    "has_standalone_dsr",
    "probabilistic_sharpe_ratio",
    "probability_of_backtest_overfitting",
    "purged_k_fold",
    "select_backtest_overfit_metrics",
]


def __dir__() -> list[str]:
    return __all__


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    raise ImportError(f"purgedcv backend not available for {name!r}")


_ = asdict  # re-export for convenience consumers that want a dict view
