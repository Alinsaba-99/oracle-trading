"""BL-707 — Haircut Sharpe Ratio (Bailey-López de Prado 2018).

Implements the probabilistic Sharpe-ratio haircut from "The Right Way to
Select Investments" (2018): the haircut derives from the PSR confidence
loss due to non-normality (skewness/kurtosis) and multiple testing
(n_trials raises the effective benchmark via the DSR expected-max, Bailey
& López de Prado 2014).  Used by the factory gauntlet as a pre-registered
validation tool (BL-KB-99).
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

from analytics.metrics.canonical import sharpe_ratio  # ADR-021 canonical


def psr_confidence(
    sr: float, n_obs: int, skew: float, kurtosis: float, sr_benchmark: float = 0.0
) -> float:
    """Probabilistic Sharpe Ratio: P(true SR > benchmark | sample).

    Bailey-López de Prado (2012): PSR = Φ( ((SR − SR*)·√(n−1)) /
    √(1 − γ3·SR + ((γ4 − 1)/4)·SR²) ) with γ3 skew, γ4 non-excess kurtosis.
    SR here is the PER-PERIOD Sharpe.
    """
    if n_obs < 2:
        return float("nan")
    denom_sq = 1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr**2
    if denom_sq <= 0.0:
        return float("nan")
    z = (sr - sr_benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom_sq)
    return float(stats.norm.cdf(z))


def _expected_max_normal(n_trials: int) -> float:
    """E[max of n iid standard normals] (Blom's approximation).

    n=1 → 0, and grows ~ sqrt(2 ln n): the expected best-of-N Sharpe under
    the null that all N trials are noise (Bailey-López de Prado 2014).
    """
    if n_trials < 1:
        return 0.0
    return float(stats.norm.ppf((n_trials - 0.375) / (n_trials + 0.25)))


def haircut_sharpe_ratio(
    returns: np.ndarray,
    n_trials: int = 1,
    sr_benchmark: float = 0.0,
    confidence: float = 0.95,
    periods_per_year: int = 252,
) -> float:
    """Sharpe after the probabilistic haircut (BL-707, BL-KB-99).

    All PSR math is per-period; the result is annualized.  The haircut SR
    is the highest per-period SR that, at the requested confidence, is
    still statistically distinguishable from the (multiple-testing-aware)
    benchmark — never above the sample SR, and monotonically deeper in
    n_trials (more strategies tested) and in kurtosis (fatter tails).
    """
    if len(returns) < 2 or n_trials < 1:
        return float("nan")
    sd = float(np.std(returns, ddof=1))
    if sd == 0.0:
        return 0.0
    sr_p = float(np.mean(returns)) / sd  # per-period Sharpe
    if not math.isfinite(sr_p):
        return float("nan")
    n = len(returns)
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns, fisher=False))  # γ4 non-excess
    denom_sq = 1.0 - skew * sr_p + ((kurt - 1.0) / 4.0) * sr_p**2
    if denom_sq <= 0.0:
        return float("nan")
    z_conf = float(stats.norm.ppf(confidence))
    se = math.sqrt(denom_sq / (n - 1))
    dsr_penalty = _expected_max_normal(n_trials) / math.sqrt(n - 1)
    benchmark_p = sr_benchmark / math.sqrt(periods_per_year)
    # Haircut SR = sample SR minus the confidence-scaled estimation error,
    # minus the DSR multiple-testing offset (expected best-of-N null SR).
    # Monotonically deeper in n_trials and in kurtosis; can be negative.
    sr_star_p = sr_p - z_conf * se - dsr_penalty - benchmark_p
    return float(sr_star_p * math.sqrt(periods_per_year))


__all__ = ["haircut_sharpe_ratio", "psr_confidence", "sharpe_ratio"]
