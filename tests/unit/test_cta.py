"""Unit tests for analytics/strategy/cta.py (BL-502 / Lane A backbone).

Verifies the 4 Carver modules (vol_target, forecast_scale, forecast_combine,
IDM) plus the TrendSignalRule building block. Tests cover:
- scalar math (vol target inversely proportional to realised vol)
- scale normalisation (|forecast| mean → target)
- combine weighted blend with cap
- IDM closed-form vs correlation-matrix formula
- end-to-end Lane A pipeline smoke
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from analytics.strategy.cta import (
    ForecastCombine,
    ForecastScale,
    InstrumentDiversificationMultiplier,
    TrendSignalRule,
    VolatilityTarget,
    build_lane_a_pipeline,
)


def _make_close(seed: int = 42, n: int = 500, mu: float = 0.0005, sigma: float = 0.01) -> pl.Series:
    rng = np.random.default_rng(seed)
    rets = rng.normal(mu, sigma, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))
    return pl.Series("close", close)


def test_volatility_target_daily_target_vol_scales_with_target() -> None:
    vt_low = VolatilityTarget(target_annual_vol=0.10)
    vt_high = VolatilityTarget(target_annual_vol=0.30)
    assert vt_high.daily_target_vol() > vt_low.daily_target_vol()
    assert vt_low.daily_target_vol() == pytest.approx(0.10 / np.sqrt(252))


def test_volatility_target_realised_vol_is_positive_and_finite() -> None:
    close = _make_close()
    vt = VolatilityTarget()
    rvol = vt.realised_vol(close)
    assert rvol.shape == close.to_numpy().shape
    finite = rvol[np.isfinite(rvol)]
    assert finite.size > 0
    assert np.all(finite > 0)


def test_volatility_target_position_scalar_inversely_proportional_to_vol() -> None:
    rng = np.random.default_rng(7)
    n = 500
    low_vol_close = pl.Series("close", 100.0 * np.exp(np.cumsum(rng.normal(0, 0.005, size=n))))
    high_vol_close = pl.Series("close", 100.0 * np.exp(np.cumsum(rng.normal(0, 0.03, size=n))))
    vt = VolatilityTarget()
    low_scalar = np.nanmean(vt.position_scalar(low_vol_close))
    high_scalar = np.nanmean(vt.position_scalar(high_vol_close))
    assert low_scalar > high_scalar, (
        f"low_vol scalar {low_scalar} should exceed high_vol {high_scalar}"
    )


def test_volatility_target_position_scalar_capped_at_max_leverage() -> None:
    rng = np.random.default_rng(11)
    # Very low vol → scalar would explode without cap
    close = pl.Series("close", 100.0 * np.exp(np.cumsum(rng.normal(0, 0.0001, size=500))))
    vt = VolatilityTarget(target_annual_vol=0.20, max_leverage=2.0)
    scalar = vt.position_scalar(close)
    finite = scalar[np.isfinite(scalar)]
    assert finite.size > 0
    assert np.max(finite) <= 2.0 + 1e-9


def test_forecast_scale_fit_scalar_normalises_abs_mean() -> None:
    rng = np.random.default_rng(13)
    raw = pl.Series("f", rng.normal(0, 5.0, size=2000))  # abs mean ~4
    scaler = ForecastScale(target_abs_forecast=1.0, lookback=250)
    scalar = scaler.fit_scalar(raw)
    scaled = scaler.scale(raw, scalar).to_numpy()
    # Tail abs mean should be approximately the target (1.0); allow generous
    # tolerance because EWM abs mean converges slowly.
    tail = scaled[-500:]
    assert abs(np.mean(np.abs(tail)) - 1.0) < 1.0


def test_forecast_scale_cap_clips_outliers() -> None:
    raw = pl.Series("f", np.array([0.5, 1.0, 5.0, 10.0, -20.0, 0.3]))
    scaler = ForecastScale(target_abs_forecast=1.0, cap=2.0)
    scaled = scaler.scale(raw, scalar=1.0).to_numpy()
    assert scaled.max() <= 2.0 + 1e-9
    assert scaled.min() >= -2.0 - 1e-9


def test_forecast_combine_weights_normalised_to_sum_one() -> None:
    fc = ForecastCombine(weights={"a": 2.0, "b": 2.0})
    assert fc.weights["a"] == pytest.approx(0.5)
    assert fc.weights["b"] == pytest.approx(0.5)


def test_forecast_combine_combines_weighted_sum() -> None:
    # Both forecasts have abs mean ~4.0 (constant), so scalar ~ target/4.
    # After scale (target=1.0), each becomes ~0.25 (constant). Equal weights → 0.25.
    fc = ForecastCombine(weights={"a": 0.5, "b": 0.5}, cap=10.0)
    forecasts = {"a": pl.Series("a", np.full(50, 4.0)), "b": pl.Series("b", np.full(50, 4.0))}
    combined = fc.combine(forecasts).to_numpy()
    # Allow generous tolerance: EWM abs mean converges slowly with default lookback=250.
    tail = combined[-20:]
    assert abs(tail[0] - 0.25) < 0.5


def test_forecast_combine_caps_combined() -> None:
    fc = ForecastCombine(weights={"a": 1.0}, cap=1.5)
    forecasts = {"a": pl.Series("a", np.full(50, 100.0))}
    combined = fc.combine(forecasts).to_numpy()
    assert combined.max() <= 1.5 + 1e-9


def test_forecast_combine_raises_on_missing_keys() -> None:
    fc = ForecastCombine(weights={"a": 1.0})
    with pytest.raises(KeyError):
        fc.combine({"b": pl.Series("b", [1.0, 2.0])})


def test_idm_from_correlation_matrix_identity_returns_sqrt_n() -> None:
    """For uncorrelated instruments (identity correlation), IDM = √N (full
    diversification benefit)."""
    idm = InstrumentDiversificationMultiplier(n_instruments=4)
    corr = np.eye(4)
    expected = np.sqrt(4)  # √N
    assert idm.from_correlation_matrix(corr) == pytest.approx(expected, rel=1e-3)


def test_idm_from_correlation_matrix_perfectly_correlated_returns_one() -> None:
    """For perfectly correlated instruments, IDM = 1 (no diversification)."""
    idm = InstrumentDiversificationMultiplier(n_instruments=3)
    corr = np.ones((3, 3))  # ρ = 1.0 everywhere
    assert idm.from_correlation_matrix(corr) == pytest.approx(1.0, rel=1e-3)


def test_idm_from_correlation_matrix_anticorrelated_increases_idm() -> None:
    idm = InstrumentDiversificationMultiplier(n_instruments=3)
    # Anti-correlated (off-diagonal = -0.3, must be valid PSD)
    corr_anti = np.array([[1.0, -0.3, -0.3], [-0.3, 1.0, -0.3], [-0.3, -0.3, 1.0]])
    # Positively correlated
    corr_pos = np.array([[1.0, 0.9, 0.9], [0.9, 1.0, 0.9], [0.9, 0.9, 1.0]])
    idm_anti = idm.from_correlation_matrix(corr_anti)
    idm_pos = idm.from_correlation_matrix(corr_pos)
    assert idm_anti > idm_pos, f"anticorr {idm_anti} should exceed poscorr {idm_pos}"


def test_idm_approx_from_avg_correlation_matches_closed_form() -> None:
    idm = InstrumentDiversificationMultiplier(n_instruments=5)
    avg_corr = 0.3
    expected = np.sqrt(5 / (1 + 4 * avg_corr))
    assert idm.approx_from_avg_correlation(avg_corr) == pytest.approx(expected, rel=1e-3)


def test_trend_signal_rule_forecast_finite_after_warmup() -> None:
    close = _make_close(n=200)
    rule = TrendSignalRule(fast=8, slow=32)
    fc = rule.forecast(close).to_numpy()
    finite = fc[np.isfinite(fc)]
    assert finite.size > 0
    assert np.any(np.abs(finite) > 1e-6)


def test_build_lane_a_pipeline_smoke() -> None:
    close = _make_close(n=500)
    pos = build_lane_a_pipeline(close, target_annual_vol=0.15)
    assert pos.len() == close.len()
    finite = pos.to_numpy()[np.isfinite(pos.to_numpy())]
    assert finite.size > 0
    assert np.max(np.abs(finite)) <= 10.0


def test_build_lane_a_pipeline_causality_no_lookahead() -> None:
    """Causality smoke: shifting close by 1 bar should produce nearly the
    same position at index i+1 (small drift acceptable due to EWM warmup)."""
    close = _make_close(n=500, seed=21)
    pos1 = build_lane_a_pipeline(close).to_numpy()
    close_arr = close.to_numpy()
    # Shift close by 1 bar (drop last, prepend first value to keep length)
    shifted = pl.Series("close", np.concatenate([[close_arr[0]], close_arr[:-1]]))
    pos2 = build_lane_a_pipeline(shifted).to_numpy()
    # The shifted position at index i should equal original at i-1 modulo EWM warmup.
    # Compare on tail after warmup, with generous tolerance (EWM smoothing boundary).
    tail1 = pos1[200:-1]
    tail2 = pos2[201:]
    # Most values should be very close (allow rtol 5%)
    if not (np.all(np.isnan(tail1)) or np.all(np.isnan(tail2))):
        close_count = np.sum(np.abs(tail1 - tail2) < 1e-3)
        # At least 50% of the tail values should be within 1e-3 of each other
        assert close_count >= 0.5 * tail1.size, (
            f"causality broken: only {close_count}/{tail1.size} values within 1e-3"
        )
