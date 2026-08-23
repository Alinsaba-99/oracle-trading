"""BL-707 — Haircut Sharpe Ratio tests (BL-KB-99, Bailey-López de Prado 2018)."""

from __future__ import annotations

import numpy as np
import pytest

from analytics.research.factory.haircut_sharpe import (
    haircut_sharpe_ratio,
    psr_confidence,
    sharpe_ratio,
)


def _normal_returns(n: int, sr_daily: float, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vol = 0.01
    return rng.standard_normal(n) * vol + sr_daily * vol


def test_sharpe_ratio_sign_and_scale() -> None:
    rets = _normal_returns(5000, sr_daily=0.05, seed=1)
    sr = sharpe_ratio(rets)
    assert sr == pytest.approx(0.05 * 252**0.5, abs=0.3)


def test_psr_confidence_grows_with_n() -> None:
    sr = 0.05  # per-period Sharpe
    lo = psr_confidence(sr, n_obs=100, skew=0.0, kurtosis=3.0)
    hi = psr_confidence(sr, n_obs=1000, skew=0.0, kurtosis=3.0)
    assert 0.5 < lo < hi <= 1.0
    assert hi < 1.0


def test_psr_confidence_fat_tails_lower() -> None:
    """Kurtosis > 3 (fat tails) erodes confidence at same SR/n."""
    normal = psr_confidence(0.05, n_obs=250, skew=0.0, kurtosis=3.0)
    fat = psr_confidence(0.05, n_obs=250, skew=0.0, kurtosis=10.0)
    assert fat < normal < 1.0


def test_haircut_never_exceeds_sample_sr() -> None:
    rets = _normal_returns(2000, sr_daily=0.05, seed=3)
    assert haircut_sharpe_ratio(rets) <= sharpe_ratio(rets)


def test_haircut_monotone_in_trials() -> None:
    """More strategies tested → deeper haircut (multiple testing)."""
    rets = _normal_returns(2000, sr_daily=0.05, seed=5)
    h1 = haircut_sharpe_ratio(rets, n_trials=1)
    h10 = haircut_sharpe_ratio(rets, n_trials=10)
    h100 = haircut_sharpe_ratio(rets, n_trials=100)
    assert h1 > h10 > h100


def test_haircut_monotone_in_kurtosis() -> None:
    """Fat tails → deeper haircut.  Deterministic: base draws + extreme
    tail draws replacing the last 150 values, rescaled to unit std."""
    rng = np.random.default_rng(11)
    n = 4000
    base = rng.standard_normal(n)
    extra = rng.standard_normal(150) * 6.0
    fat = np.concatenate([base[: n - 150], extra])
    base_s = base / base.std(ddof=1)
    fat_s = fat / fat.std(ddof=1)
    from scipy import stats as sps

    k_base = sps.kurtosis(base_s, fisher=False)
    k_fat = sps.kurtosis(fat_s, fisher=False)
    assert k_fat > k_base, f"construction failed: {k_fat} !> {k_base}"
    assert haircut_sharpe_ratio(fat_s) < haircut_sharpe_ratio(base_s)


def test_deterministic_and_finite() -> None:
    rets = _normal_returns(1000, sr_daily=0.03, seed=9)
    a = haircut_sharpe_ratio(rets)
    b = haircut_sharpe_ratio(rets)
    assert a == b
    assert np.isfinite(a)


def test_short_series_nan() -> None:
    assert np.isnan(haircut_sharpe_ratio(np.array([0.01])))
