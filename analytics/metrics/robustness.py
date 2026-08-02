"""Backtest robustness — PBO, Deflated Sharpe, Bootstrap Sharpe CI.

Inspired by Inalpha's robustness.py (which wraps backtester_mcp).
These functions detect multiple-testing bias and overfitting.

Three indicators:
  1. PBO — Probability of Backtest Overfitting (CSCV algorithm)
  2. Deflated Sharpe Ratio — corrects Sharpe for N trials
  3. Bootstrap Sharpe CI — confidence interval via resampling
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# Bootstrap Sharpe confidence interval
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BootstrapSharpeResult:
    sharpe: float
    ci_lower: float
    ci_upper: float
    ci_includes_zero: bool


def bootstrap_sharpe_ci(
    returns: Sequence[float], *, n_bootstrap: int = 10000, ci: float = 0.95, seed: int = 42
) -> BootstrapSharpeResult:
    """Compute Sharpe ratio with bootstrap confidence interval.

    Uses circular block bootstrap to preserve return autocorrelation.

    Args:
        returns: Sequence of per-period returns.
        n_bootstrap: Number of bootstrap resamples.
        ci: Confidence interval width (default 0.95 → 95% CI).
        seed: Random seed for reproducibility.

    Returns:
        BootstrapSharpeResult with point estimate and CI.
    """
    rng = np.random.default_rng(seed)
    arr = np.asarray(returns, dtype=float)
    if len(arr) < 3 or np.std(arr) == 0:
        return BootstrapSharpeResult(sharpe=0.0, ci_lower=0.0, ci_upper=0.0, ci_includes_zero=True)

    n = len(arr)
    sharpe = float(np.mean(arr) / np.std(arr, ddof=1) * np.sqrt(252))

    # Circular block bootstrap
    max(1, int(n**0.33))
    boot_sharpes = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        start = rng.integers(0, n)
        indices = [(start + j) % n for j in range(n)]
        boot_ret = arr[indices]
        if np.std(boot_ret, ddof=1) > 0:
            boot_sharpes[i] = float(np.mean(boot_ret) / np.std(boot_ret, ddof=1) * np.sqrt(252))

    alpha = 1.0 - ci
    lower = float(np.percentile(boot_sharpes, alpha / 2 * 100))
    upper = float(np.percentile(boot_sharpes, (1 - alpha / 2) * 100))
    includes_zero = lower <= 0 <= upper

    return BootstrapSharpeResult(
        sharpe=round(sharpe, 4),
        ci_lower=round(lower, 4),
        ci_upper=round(upper, 4),
        ci_includes_zero=includes_zero,
    )


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio (DSR)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeflatedSharpeResult:
    dsr: float
    p_value: float
    expected_max_sharpe: float


def deflated_sharpe(
    observed_sharpe: float,
    n_strategies: int,
    n_observations: int,
    *,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> DeflatedSharpeResult:
    """Compute Deflated Sharpe Ratio (Bailey & López de Prado 2014).

    Corrects the observed Sharpe for the number of trials (strategies
    tested).  The DSR answers: "if we ran N random strategies, what's
    the probability that the best one's Sharpe exceeds the observed?"

    Args:
        observed_sharpe: The best Sharpe ratio observed across all trials.
        n_strategies: Number of strategies/parameter sets tested.
        n_observations: Number of observations in each backtest.
        skewness: Return skewness (0 = normal).
        kurtosis: Return excess kurtosis (3 = normal).

    Returns:
        DeflatedSharpeResult with DSR statistic, p-value, and E[max].
    """
    if n_strategies < 1 or n_observations < 2:
        return DeflatedSharpeResult(dsr=0.0, p_value=1.0, expected_max_sharpe=0.0)

    from scipy.stats import norm

    # Variance of Sharpe ratio (Mertens 2002)
    var_sharpe = (
        1.0
        + 0.5 * observed_sharpe**2
        - skewness * observed_sharpe
        + (kurtosis - 3) / 4 * observed_sharpe**2
    ) / (n_observations - 1)

    if var_sharpe <= 0:
        return DeflatedSharpeResult(dsr=0.0, p_value=1.0, expected_max_sharpe=0.0)

    std_sharpe = math.sqrt(var_sharpe)
    euler_mascheroni = 0.5772156649

    # E[max] under null: approximate max of N normals
    n_eff = n_strategies
    e_max = std_sharpe * (
        (1 - euler_mascheroni) * norm.ppf(1 - 1.0 / n_eff)
        + euler_mascheroni * norm.ppf(1 - 1.0 / (n_eff * math.e))
    )

    # DSR = (observed - E[max]) / std(SR)
    dsr = (observed_sharpe - e_max) / std_sharpe if std_sharpe > 0 else 0.0
    p_value = 1.0 - norm.cdf(dsr)

    return DeflatedSharpeResult(
        dsr=round(dsr, 4), p_value=round(p_value, 4), expected_max_sharpe=round(e_max, 4)
    )


# ---------------------------------------------------------------------------
# Probability of Backtest Overfitting (PBO)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PBOResult:
    pbo: float
    n_combinations: int
    logit_mean: float


def probability_of_backtest_overfitting(
    returns_matrix: np.ndarray, n_splits: int = 10
) -> PBOResult:
    """Compute Probability of Backtest Overfitting (CSCV algorithm).

    Bailey & López de Prado 2014, "The Probability of Backtest Overfitting".

    Args:
        returns_matrix: (n_periods, n_strategies) array of returns.
        n_splits: Number of CSCV folds (default 10).

    Returns:
        PBOResult with PBO probability, number of combinations, and logit mean.
    """
    n_periods, n_strategies = returns_matrix.shape
    if n_periods < n_splits * 2 or n_strategies < 2:
        return PBOResult(pbo=0.5, n_combinations=0, logit_mean=0.0)

    fold_size = n_periods // n_splits
    from itertools import combinations

    # Logits store: for each pair of complementary fold sets, the logit ratio
    logits: list[float] = []

    # We use a subset of CSCV combinations for speed
    from math import comb as _comb

    total_combos = _comb(n_splits, n_splits // 2)
    max_combos = min(total_combos, 50)  # cap for performance

    combo_list = list(combinations(range(n_splits), n_splits // 2))
    if len(combo_list) > max_combos:
        combo_list = combo_list[:max_combos]

    for in_sample_folds in combo_list:
        out_folds = [f for f in range(n_splits) if f not in in_sample_folds]
        if not out_folds:
            continue

        # In-sample indices
        is_idx: list[int] = []
        for f in in_sample_folds:
            s = f * fold_size
            e = s + fold_size if f < n_splits - 1 else n_periods
            is_idx.extend(range(s, e))

        # Out-of-sample indices
        oos_idx: list[int] = []
        for f in out_folds:
            s = f * fold_size
            e = s + fold_size if f < n_splits - 1 else n_periods
            oos_idx.extend(range(s, e))

        if not is_idx or not oos_idx:
            continue

        # IS and OOS returns
        is_returns = returns_matrix[np.array(is_idx), :]
        oos_returns = returns_matrix[np.array(oos_idx), :]

        # Rank by IS Sharpe
        is_sharpes = np.mean(is_returns, axis=0) / (np.std(is_returns, axis=0, ddof=1) + 1e-9)
        is_rank = np.argsort(-is_sharpes)  # best first

        # OOS Sharpe for the best IS strategy
        best_strat = is_rank[0]
        oos_sharpe = np.mean(oos_returns[:, best_strat]) / (
            np.std(oos_returns[:, best_strat], ddof=1) + 1e-9
        )

        # OOS Sharpe for median IS strategy
        median_strat = is_rank[n_strategies // 2]
        (
            np.mean(oos_returns[:, median_strat])
            / (np.std(oos_returns[:, median_strat], ddof=1) + 1e-9)
        )

        # Rank logit: log(best_oos_rank / median_oos_rank)
        # Higher logit = best IS strategy also performs well OOS
        oos_sharpes = np.mean(oos_returns, axis=0) / (np.std(oos_returns, axis=0, ddof=1) + 1e-9)
        best_oos_rank = np.sum(oos_sharpes > oos_sharpe) + 1
        logit = math.log((best_oos_rank + 1) / (n_strategies - best_oos_rank + 1))
        logits.append(logit)

    if not logits:
        return PBOResult(pbo=0.5, n_combinations=0, logit_mean=0.0)

    logit_arr = np.array(logits)
    pbo = float(np.mean(logit_arr <= 0))
    logit_mean = float(np.mean(logit_arr))

    return PBOResult(
        pbo=round(float(pbo), 4), n_combinations=len(logits), logit_mean=round(float(logit_mean), 4)
    )


__all__ = [
    "BootstrapSharpeResult",
    "DeflatedSharpeResult",
    "PBOResult",
    "bootstrap_sharpe_ci",
    "deflated_sharpe",
    "probability_of_backtest_overfitting",
]
