"""BL-706 — IC screen: golden behaviour su serie sintetiche a potatura nota."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.research.factory.ic_screen import ICResult, screen_factor


def _market(n: int, seed: int) -> tuple[pd.Series, pd.Series]:
    """Prices from seeded returns; forward return aligned as the screen sees it."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="h", name="ts")
    rets = rng.standard_normal(n) * 0.001
    prices = pd.Series(100.0 * np.cumprod(1.0 + rets), index=idx, name="price")
    # screen_factor correlates factor_t with fwd_t = prices[t+1]/prices[t]-1 = rets[t+1]
    next_ret = pd.Series(rets, index=idx, name="next_ret").shift(-1)
    return prices, next_ret


def _factor_with_ic(next_ret: pd.Series, strength: float, seed: int) -> pd.Series:
    """Factor = strength * (normalized return) + unit noise.

    Normalization matters: raw returns have std ~1e-3, so without it the
    planted signal would be drowned by the noise term (correlation ≈ 0).
    After normalization, corr(factor, return) ≈ strength/sqrt(strength²+1).
    """
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(next_ret))
    signal = next_ret / float(next_ret.std(ddof=0))
    return (strength * signal + noise).rename("factor")


def test_planted_signal_passes() -> None:
    prices, nxt = _market(2000, seed=3)
    res = screen_factor(_factor_with_ic(nxt, 0.35, seed=9), prices, horizon=1, window=100)
    assert res.n_windows >= 15
    assert res.ic_mean > 0.05
    assert res.passes is True


def test_pure_noise_fails() -> None:
    prices, nxt = _market(2000, seed=3)
    res = screen_factor(_factor_with_ic(nxt, 0.0, seed=9), prices, horizon=1, window=100)
    assert res.passes is False


def test_haircut_applied_to_icir() -> None:
    prices, nxt = _market(2000, seed=3)
    res = screen_factor(_factor_with_ic(nxt, 0.35, seed=9), prices, horizon=1, window=100)
    assert res.icir_haircut == pytest.approx(res.icir * 0.70)


def test_deterministic_given_seed() -> None:
    prices, nxt = _market(1500, seed=5)
    f = _factor_with_ic(nxt, 0.2, seed=4)
    a = screen_factor(f, prices, horizon=1, window=75)
    b = screen_factor(f, prices, horizon=1, window=75)
    assert a == b


def test_insufficient_data_fails_closed() -> None:
    prices, nxt = _market(200, seed=1)
    res = screen_factor(_factor_with_ic(nxt, 0.9, seed=2), prices, horizon=1, window=100)
    assert res.n_windows < 4
    assert res.passes is False


def test_negative_ic_fails_no_sign_flip() -> None:
    """Direzione fissata (long-factor): IC negativo = FAIL, mai sign-flip post-hoc."""
    prices, nxt = _market(2000, seed=3)
    res = screen_factor(_factor_with_ic(nxt, -0.35, seed=9), prices, horizon=1, window=100)
    assert res.ic_mean < 0
    assert res.passes is False


def test_golden_vectors() -> None:
    """Characterization: valori attesi congelati dal primo run verde (seed fissi)."""
    prices, nxt = _market(2000, seed=3)
    res = screen_factor(_factor_with_ic(nxt, 0.35, seed=9), prices, horizon=1, window=100)
    assert isinstance(res, ICResult)
    assert res.n_windows == 19
    assert res.ic_mean == pytest.approx(0.33819697759249606, abs=1e-12)
    assert res.ic_std == pytest.approx(0.06848573838284208, abs=1e-12)
    assert res.icir == pytest.approx(4.9382102840439766, abs=1e-12)
    assert res.t_block == pytest.approx(19.83224247696755, abs=1e-9)
    assert res.icir_haircut == pytest.approx(3.4567471988307834, abs=1e-12)
    assert res.passes is True
    assert res.icir_threshold == 0.05
    assert res.t_threshold == 2.5
    assert res.haircut_pct == 30.0
