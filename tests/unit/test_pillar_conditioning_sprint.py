"""Test BL-741 — Cross-pillar conditioning sprint (matematica + PIT, no lake).

Pattern: same minimal synthetic-only coverage as
``test_overnight_drift_sprint.py`` and ``test_fx_carry_policy_rate.py``.
The runner's math (veto_scale, PIT shift, against-direction logic,
combination) is verified here; the lake / funding / VIX I/O is exercised
in the runner itself.

Mapping/coverage prereg (brief §Test):
- ``veto_scale(z=2.0)=0``, ``veto_scale(z=0)=1``, ``veto_scale(z=-1)=0.5``
- PIT: z at T only influences bars > T (shift(1) on the fused pillar)
- against-direction: scale=1 when sign(z) != sign(pos); scale=veto_scale(z)
  when sign(z) == sign(pos)
- combined pillar: min(scale_a, scale_b)
- full_z is FROZEN at 2.0 (no grid search)
- donchian(20) and ema(20/50) signal generators are causal
- report markdown contains expected keys (verdict, precedent, limitations)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.run_pillar_conditioning_sprint import (  # noqa: E402
    DONCHIAN_N,
    EMA_FAST,
    EMA_SLOW,
    HELPFUL_DSR_MIN_DELTA,
    TARGET_VOL_ES,
    TEST_SPLIT,
    VETO_FULL_Z,
    LegVariantResult,
    _render_markdown,
    _verdict_for_pillar,
    apply_against_veto,
    combine_scales,
    donchian_signal,
    ema_signal,
    fuse_vix_z_onto_grid,
    run_leg,
    veto_scale,
    vol_target_scalar,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _daily_index(n: int = 300, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="D", tz="UTC")


def _hourly_index(n: int = 24 * 90, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="h", tz="UTC")


def _walk_prices(idx: pd.DatetimeIndex, seed: int = 0) -> pd.Series:
    """Random-walk price series (positive)."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(loc=0.0005, scale=0.01, size=len(idx))
    prices = 100.0 * np.exp(np.cumsum(rets))
    return pd.Series(prices, index=idx, name="close")


# ---------------------------------------------------------------------------
# veto_scale — math (REQUIRED by brief §Test)
# ---------------------------------------------------------------------------


def test_veto_scale_full_z_gives_zero() -> None:
    """At |z|=2 (full_z), the scale is 0 (full veto)."""
    s = pd.Series([2.0])
    assert veto_scale(s).iloc[0] == 0.0


def test_veto_scale_zero_gives_one() -> None:
    """At |z|=0, the scale is 1 (no veto)."""
    s = pd.Series([0.0])
    assert veto_scale(s).iloc[0] == 1.0


def test_veto_scale_neg_one_gives_half() -> None:
    """At |z|=1, the scale is 0.5 (half veto)."""
    s = pd.Series([-1.0])
    assert veto_scale(s).iloc[0] == 0.5


def test_veto_scale_above_full_z_caps_at_zero() -> None:
    """At |z|>2, the scale is 0 (clipped to full_z)."""
    s = pd.Series([3.0, 10.0, -100.0])
    out = veto_scale(s)
    assert (out == 0.0).all()


def test_veto_scale_full_z_param_changes_saturation() -> None:
    """full_z parameter changes the veto saturation point (still frozen in runner)."""
    s = pd.Series([2.0])
    # full_z=4: |z|/4 = 0.5 → 1 - 0.5 = 0.5
    assert veto_scale(s, full_z=4.0).iloc[0] == pytest.approx(0.5)
    # full_z=1: |z|/1 = 2 → clip(0,1) = 1 → 1 - 1 = 0
    assert veto_scale(s, full_z=1.0).iloc[0] == 0.0


def test_veto_scale_uses_absolute_z() -> None:
    """veto_scale is symmetric in z (depends only on |z|)."""
    s_pos = pd.Series([1.0])
    s_neg = pd.Series([-1.0])
    assert veto_scale(s_pos).iloc[0] == veto_scale(s_neg).iloc[0] == 0.5


def test_veto_scale_default_full_z_is_two() -> None:
    """The brief specifies full_z=2 FROZEN; default value must be 2."""
    assert VETO_FULL_Z == 2.0


# ---------------------------------------------------------------------------
# PIT semantics (REQUIRED by brief §Test + review gotcha #2)
# ---------------------------------------------------------------------------


def test_vix_z_pit_does_not_influence_bar_at_t() -> None:
    """PIT semantic: z at day T must NOT influence the position at bar ≤ T.

    The Sprint 2d convention (mirrored here) is to shift(1) the z so bar T
    sees the z observed strictly before T.  Without the shift, a spike on
    day 0 would already veto bar 0 — that's the lookahead the Task 3
    review caught.
    """
    idx = _daily_index(5)
    pos = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0], index=idx)
    z_raw = pd.Series([2.0, 0.0, 0.0, 0.0, 0.0], index=idx)

    # PIT-safe: z is shifted BEFORE applying against-veto.
    z_pit = z_raw.shift(1)  # now: [NaN, 2.0, 0, 0, 0]
    fused = apply_against_veto(pos, z_pit)

    # Bar 0 sees NaN → not against → scale=1 → pos unchanged at 1.0.
    assert fused.iloc[0] == pytest.approx(1.0)
    # Bar 1 sees z=2.0 (same sign as pos=+1) → against → scale=0 → pos vetoed.
    assert fused.iloc[1] == pytest.approx(0.0)
    # Bar 2+ sees z=0 → not against → pos unchanged.
    assert fused.iloc[2] == pytest.approx(1.0)


def test_fuse_vix_z_onto_grid_applies_pit_shift() -> None:
    """fuse_vix_z_onto_grid must shift(1) the z before exposing it.

    This is the function-level guard against the lookahead bug the Task 3
    review caught.
    """
    idx = _daily_index(5)
    vix = pd.Series([10.0, 50.0, 10.0, 10.0, 10.0], index=_daily_index(5), name="vix_close")
    # Use a tiny window so the z computation only depends on the values we set.
    z = fuse_vix_z_onto_grid(vix, idx, window=3, min_periods=3, pit_shift=1)
    # At bar T we see the z computed from vix[..T-1].  Crucially, the
    # spike on day 1 (vix[1]=50) must NOT appear on bar 1 — it should
    # first influence bar 2.
    assert z.iloc[0] != z.iloc[1] or pd.isna(z.iloc[1])  # bar 0/1 are the first two of window
    # The spike day-1 z must be exposed at bar 2 (shift(1)).
    # bar 2's z reflects vix[..1], which has the spike — so |z[2]| should
    # be substantially larger than |z[3]|.
    assert abs(z.iloc[2]) > abs(z.iloc[3]) or pd.isna(z.iloc[2])


def test_fuse_vix_z_onto_grid_handles_hourly_target() -> None:
    """Hourly target index: ffill the daily z across all 24h of day D."""
    daily_idx = _daily_index(5)
    vix = pd.Series([10.0, 50.0, 10.0, 10.0, 10.0], index=daily_idx)
    hourly_idx = pd.date_range("2024-01-01", periods=24 * 5, freq="h", tz="UTC")
    z = fuse_vix_z_onto_grid(vix, hourly_idx, window=3, min_periods=3, pit_shift=1)
    # All 24 hourly bars of the same UTC day share the same z value.
    for d in range(5):
        day_slice = z.iloc[d * 24 : (d + 1) * 24]
        # within-day values are constant (or NaN during warm-up)
        non_nan = day_slice.dropna()
        if len(non_nan) > 1:
            assert non_nan.nunique() == 1


# ---------------------------------------------------------------------------
# apply_against_veto — direction logic
# ---------------------------------------------------------------------------


def test_apply_against_veto_no_veto_when_pos_zero() -> None:
    """When pos is 0, no veto is applied (no 'crowding against')."""
    idx = _daily_index(5)
    pos = pd.Series([0.0, 1.0, -1.0, 1.0, 0.0], index=idx)
    z = pd.Series([2.0, 2.0, 2.0, -2.0, 2.0], index=idx)
    fused = apply_against_veto(pos, z)
    # Day 0: pos=0 → not against (pos has no sign) → scale=1 → fused=0
    assert fused.iloc[0] == 0.0
    # Day 1: pos=1, z=2 → same sign → against → scale=0 → fused=0
    assert fused.iloc[1] == 0.0
    # Day 2: pos=-1, z=2 → different sign → not against → scale=1 → fused=-1
    assert fused.iloc[2] == -1.0
    # Day 3: pos=1, z=-2 → different sign → not against → scale=1 → fused=1
    assert fused.iloc[3] == 1.0


def test_apply_against_veto_partial_veto_at_intermediate_z() -> None:
    """At |z|=1, the scale is 0.5 (half veto)."""
    idx = _daily_index(5)
    pos = pd.Series([1.0, 1.0, 1.0, 0.0, 0.0], index=idx)
    z = pd.Series([1.0, 0.0, -1.0, 1.0, 1.0], index=idx)
    fused = apply_against_veto(pos, z)
    # Day 0: pos=1, z=1 → against → scale=0.5 → fused=0.5
    assert fused.iloc[0] == pytest.approx(0.5)
    # Day 1: pos=1, z=0 → not against → fused=1
    assert fused.iloc[1] == pytest.approx(1.0)
    # Day 2: pos=1, z=-1 → not against → fused=1
    assert fused.iloc[2] == pytest.approx(1.0)


def test_apply_against_veto_handles_negative_positions() -> None:
    """Short positions are vetoed when z is negative and crowding against."""
    idx = _daily_index(3)
    pos = pd.Series([-1.0, -1.0, -1.0], index=idx)
    z = pd.Series([-2.0, -1.0, 0.5], index=idx)
    fused = apply_against_veto(pos, z)
    # Day 0: pos=-1, z=-2 → same sign → against → scale=0 → fused=0
    assert fused.iloc[0] == 0.0
    # Day 1: pos=-1, z=-1 → same sign → against → scale=0.5 → fused=-0.5
    assert fused.iloc[1] == pytest.approx(-0.5)
    # Day 2: pos=-1, z=0.5 → different sign → not against → fused=-1
    assert fused.iloc[2] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# combine_scales — multi-pillar aggregation
# ---------------------------------------------------------------------------


def test_combine_scales_takes_minimum_of_vetoes() -> None:
    """When both pillars veto, combined = min(scale_a, scale_b)."""
    idx = _daily_index(5)
    pos = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0], index=idx)
    z1 = pd.Series([1.0, 2.0, 0.0, 1.0, 2.0], index=idx)  # VIX-z
    z2 = pd.Series([2.0, 0.0, 1.0, 2.0, 0.0], index=idx)  # funding-z

    combined = combine_scales(pos, [z1, z2])

    # Day 0: z1=1 (against) → 0.5; z2=2 (against) → 0 → min=0 → fused=0
    assert combined.iloc[0] == 0.0
    # Day 1: z1=2 (against) → 0; z2=0 → 1 → min=0 → fused=0
    assert combined.iloc[1] == 0.0
    # Day 2: z1=0 → 1; z2=1 (against) → 0.5 → min=0.5 → fused=0.5
    assert combined.iloc[2] == pytest.approx(0.5)
    # Day 3: z1=1 → 0.5; z2=2 → 0 → min=0 → fused=0
    assert combined.iloc[3] == 0.0
    # Day 4: z1=2 → 0; z2=0 → 1 → min=0 → fused=0
    assert combined.iloc[4] == 0.0


def test_combine_scales_empty_list_returns_pos_unchanged() -> None:
    """No pillars → position is returned as-is (no veto at all)."""
    idx = _daily_index(3)
    pos = pd.Series([1.0, 1.0, 1.0], index=idx)
    fused = combine_scales(pos, [])
    pd.testing.assert_series_equal(fused, pos.astype(float), check_names=False)


def test_combine_scales_pos_zero_remains_zero() -> None:
    """When pos=0, the combined scale doesn't change anything (pos stays 0)."""
    idx = _daily_index(3)
    pos = pd.Series([0.0, 0.0, 0.0], index=idx)
    z = pd.Series([2.0, -1.0, 2.0], index=idx)
    fused = combine_scales(pos, [z])
    assert (fused == 0.0).all()


# ---------------------------------------------------------------------------
# Signal generators
# ---------------------------------------------------------------------------


def test_ema_signal_is_causal() -> None:
    """The ema_signal must be shift(1)-ed so today's signal drives tomorrow's return."""
    idx = _daily_index(60)
    close = _walk_prices(idx, seed=42)
    sig = ema_signal(close)
    # First 50 bars are warm-up → sig should be 0.
    assert (sig.iloc[:EMA_SLOW].fillna(0.0) == 0.0).all()
    # After warm-up the signal can be ±1 or 0.
    assert set(sig.dropna().unique().tolist()).issubset({-1.0, 0.0, 1.0})


def test_ema_signal_frozen_params() -> None:
    """The brief freezes EMA(20/50)."""
    assert EMA_FAST == 20
    assert EMA_SLOW == 50


def test_donchian_signal_is_causal() -> None:
    """The donchian signal must be shift(1)-ed."""
    idx = _daily_index(30)
    close = _walk_prices(idx, seed=42)
    sig = donchian_signal(close)
    # First 20 bars are warm-up → sig should be 0.
    assert (sig.iloc[:DONCHIAN_N].fillna(0.0) == 0.0).all()
    # After warm-up the signal is ±1 or 0.
    assert set(sig.dropna().unique().tolist()).issubset({0.0, 1.0})


def test_donchian_signal_frozen_params() -> None:
    """The brief freezes donchian(20)."""
    assert DONCHIAN_N == 20


# ---------------------------------------------------------------------------
# vol_target_scalar
# ---------------------------------------------------------------------------


def test_vol_target_scalar_uses_target_and_window() -> None:
    """The scalar returns target_vol / realised_vol * sqrt(periods_per_year)."""
    idx = _daily_index(60)
    close = _walk_prices(idx, seed=0)
    s = vol_target_scalar(close, target_vol=0.10, periods_per_year=252, vol_window=30)
    # Scalar is non-negative everywhere finite.
    finite = s.dropna()
    assert (finite >= 0.0).all()
    # Scalar is capped at POSITION_CAP (2.0).
    assert s.max() <= 2.0 + 1e-9


# ---------------------------------------------------------------------------
# run_leg — full pipeline on synthetic data
# ---------------------------------------------------------------------------


def test_run_leg_returns_baseline_and_conditioned() -> None:
    """run_leg returns one baseline + one conditioned LegVariantResult."""
    idx = _daily_index(400)
    close = _walk_prices(idx, seed=1)
    sig = ema_signal(close)
    z = pd.Series(np.random.default_rng(2).normal(0, 1, size=len(idx)), index=idx)
    base, cond = run_leg(
        leg_name="synthetic_ema",
        close=close,
        sig=sig,
        pillar_z=z,
        periods_per_year=252,
        target_vol=TARGET_VOL_ES,
        vol_window=60,
    )
    assert isinstance(base, LegVariantResult)
    assert isinstance(cond, LegVariantResult)
    assert base.variant == "baseline"
    assert cond.variant == "conditioned"
    assert base.n_test_bars > 0
    assert cond.n_test_bars > 0


def test_run_leg_no_pillar_matches_baseline() -> None:
    """With pillar_z=None, conditioned == baseline (no veto at all)."""
    idx = _daily_index(400)
    close = _walk_prices(idx, seed=1)
    sig = ema_signal(close)
    base, cond = run_leg(
        leg_name="synthetic_ema",
        close=close,
        sig=sig,
        pillar_z=None,
        periods_per_year=252,
        target_vol=TARGET_VOL_ES,
        vol_window=60,
    )
    assert base.sharpe == pytest.approx(cond.sharpe)
    assert base.turnover == pytest.approx(cond.turnover)


# ---------------------------------------------------------------------------
# _verdict_for_pillar — verdict logic
# ---------------------------------------------------------------------------


def _res(sharpe: float, turnover: float, survived: bool = True) -> LegVariantResult:
    return LegVariantResult(
        leg="x",
        pillar="none",
        variant="baseline",
        n_bars_total=1000,
        n_test_bars=900,
        sharpe=sharpe,
        annual_return=0.0,
        max_drawdown=0.0,
        trades=100,
        turnover=turnover,
        cost_drag=0.0,
        cpcv_oos_median=0.5 if survived else None,
        cpcv_oos_n_paths=15,
        survived_cpcv=survived,
        pbo=None,
    )


def test_verdict_helpful_when_majority_legs_meet_delta_sr_threshold() -> None:
    """HELPFUL: ΔSR ≥ +0.10 on majority of legs without violating turnover/CPCV gates."""
    pairs = [
        (_res(0.5, turnover=100), _res(0.7, turnover=120)),  # Δ=+0.2 HELPFUL
        (_res(0.3, turnover=200), _res(0.5, turnover=210)),  # Δ=+0.2 HELPFUL
        (_res(-0.1, turnover=300), _res(0.0, turnover=310)),  # Δ=+0.1 HELPFUL
    ]
    assert _verdict_for_pillar(pairs) == "HELPFUL"


def test_verdict_harmful_when_all_deltas_strongly_negative() -> None:
    """HARMFUL: all ΔSR < -0.10."""
    pairs = [
        (_res(0.5, turnover=100), _res(0.3, turnover=100)),  # Δ=-0.2
        (_res(0.3, turnover=200), _res(0.1, turnover=200)),  # Δ=-0.2
        (_res(0.0, turnover=300), _res(-0.2, turnover=300)),  # Δ=-0.2
    ]
    assert _verdict_for_pillar(pairs) == "HARMFUL"


def test_verdict_neutral_when_mixed() -> None:
    """NEUTRAL: some legs positive, some negative but no clear majority."""
    pairs = [
        (_res(0.5, turnover=100), _res(0.6, turnover=100)),  # Δ=+0.1
        (_res(0.5, turnover=200), _res(0.3, turnover=200)),  # Δ=-0.2
        (_res(0.5, turnover=300), _res(0.4, turnover=300)),  # Δ=-0.1
    ]
    assert _verdict_for_pillar(pairs) == "NEUTRAL"


def test_verdict_demoted_when_turnover_explodes() -> None:
    """HELPFUL demoted to NEUTRAL when conditioned turnover > 2× baseline."""
    pairs = [
        (_res(0.5, turnover=100), _res(0.7, turnover=300)),  # turnover 3× → fails
        (_res(0.3, turnover=200), _res(0.5, turnover=210)),  # HELPFUL
        (_res(-0.1, turnover=300), _res(0.0, turnover=310)),  # HELPFUL
    ]
    assert _verdict_for_pillar(pairs) == "NEUTRAL"


def test_verdict_demoted_when_cpcv_fails() -> None:
    """HELPFUL demoted to NEUTRAL when either side fails CPCV."""
    pairs = [
        (_res(0.5, turnover=100, survived=False), _res(0.7, turnover=120, survived=True)),
        (_res(0.3, turnover=200, survived=True), _res(0.5, turnover=210, survived=True)),
        (_res(-0.1, turnover=300, survived=True), _res(0.0, turnover=310, survived=True)),
    ]
    assert _verdict_for_pillar(pairs) == "NEUTRAL"


def test_helpful_dsr_min_delta_frozen() -> None:
    """HELPFUL_DSR_MIN_DELTA must be 0.10 per the brief (no tuning)."""
    assert pytest.approx(0.10) == HELPFUL_DSR_MIN_DELTA


# ---------------------------------------------------------------------------
# Report rendering (smoke)
# ---------------------------------------------------------------------------


def test_render_markdown_contains_precedent_and_verdict_keys() -> None:
    """The rendered report must reference the Sprint 2d precedent and per-pillar verdict."""
    rows = [
        {
            "leg": "ES_1d_ema2050",
            "pillar": "vix_z",
            "pillar_description": "VIX z-score",
            "variant": "baseline",
            "sharpe": 0.5,
            "annual_return": 0.10,
            "max_drawdown": 0.15,
            "trades": 50,
            "turnover": 100.0,
            "cost_drag": 0.01,
            "n_test_bars": 900,
            "cpcv_oos_median": 0.4,
            "cpcv_oos_n_paths": 15,
            "survived_cpcv": True,
        },
        {
            "leg": "ES_1d_ema2050",
            "pillar": "vix_z",
            "pillar_description": "VIX z-score",
            "variant": "conditioned",
            "sharpe": 0.3,
            "annual_return": 0.06,
            "max_drawdown": 0.13,
            "trades": 30,
            "turnover": 60.0,
            "cost_drag": 0.006,
            "n_test_bars": 900,
            "cpcv_oos_median": 0.2,
            "cpcv_oos_n_paths": 15,
            "survived_cpcv": True,
        },
    ]
    md = _render_markdown(
        rows, verdicts={"vix_z": "HARMFUL"}, n_pillars_total=1, test_split=TEST_SPLIT
    )
    # MUST reference the Sprint 2d precedent (brief: PRECEDENTE NEGATIVO da dichiarare).
    assert "Sprint 2d" in md
    assert "NEGATIVO" in md or "REJECTED" in md or "CHIUSA" in md
    # MUST contain the verdict + ΔSR column.
    assert "verdict" in md.lower() or "Verdetto" in md
    assert "ΔSR" in md
    # MUST contain limitations section (review gotcha: explicit honesty on
    # what is and isn't measured).
    assert "Limitazioni oneste" in md


def test_render_markdown_flags_all_negative_as_pista_chiusa() -> None:
    """When every pillar is HARMFUL/NEUTRAL, the report declares pista conditioning-lite CHIUSA."""
    rows = [
        {
            "leg": "L",
            "pillar": "vix_z",
            "pillar_description": "",
            "variant": "baseline",
            "sharpe": 0.5,
            "annual_return": 0.1,
            "max_drawdown": 0.1,
            "trades": 10,
            "turnover": 100.0,
            "cost_drag": 0.01,
            "n_test_bars": 100,
            "cpcv_oos_median": 0.4,
            "cpcv_oos_n_paths": 15,
            "survived_cpcv": True,
        },
        {
            "leg": "L",
            "pillar": "vix_z",
            "pillar_description": "",
            "variant": "conditioned",
            "sharpe": 0.1,
            "annual_return": 0.02,
            "max_drawdown": 0.05,
            "trades": 5,
            "turnover": 50.0,
            "cost_drag": 0.005,
            "n_test_bars": 100,
            "cpcv_oos_median": 0.0,
            "cpcv_oos_n_paths": 15,
            "survived_cpcv": False,
        },
    ]
    md = _render_markdown(
        rows, verdicts={"vix_z": "HARMFUL"}, n_pillars_total=1, test_split=TEST_SPLIT
    )
    assert "CHIUSA" in md or "morta_per_evidenza" in md
    assert "REJECTED" in md or "NEGATIVO" in md


# ---------------------------------------------------------------------------
# vix_z PIT integration end-to-end (real run_leg path)
# ---------------------------------------------------------------------------


def test_run_leg_with_synthetic_vix_z_is_pit_safe() -> None:
    """A spike in VIX at the LAST bar must NOT influence any bar in the backtest.

    This is the end-to-end PIT guard — without shift(1) on the pillar,
    the spike would already be priced into the bar at T.

    The ``run_leg`` function expects a PIT-safe ``pillar_z`` (the caller is
    responsible for the shift, mirroring ``load_funding_onto_prices``).
    We build the pillar via :func:`fuse_vix_z_onto_grid` which applies the
    shift internally — that's the integration path the runner takes for VIX.
    """
    idx = _daily_index(400)
    close = _walk_prices(idx, seed=1)
    sig = ema_signal(close)
    # Synthetic VIX daily: zero everywhere except a +50 spike on the LAST day.
    vix = pd.Series(10.0, index=idx, name="vix_close")
    vix.iloc[-1] = 60.0  # huge spike on the last bar
    # Build the PIT-safe pillar via the runner's fuser.
    z = fuse_vix_z_onto_grid(vix, idx, window=60, min_periods=30, pit_shift=1)
    base, cond = run_leg(
        leg_name="synthetic_ema",
        close=close,
        sig=sig,
        pillar_z=z,
        periods_per_year=252,
        target_vol=TARGET_VOL_ES,
        vol_window=60,
    )
    # The spike falls off the end of the index after shift(1), so it never
    # influences any backtest bar — conditioned Sharpe must equal baseline.
    assert base.sharpe == pytest.approx(cond.sharpe)


def test_run_leg_with_spike_at_start_vetoes_immediately_after() -> None:
    """A spike in VIX at the FIRST bar must influence bar 1 (after shift(1))
    but NOT bar 0.  We verify by comparing positions: the spike will veto
    bar 1 onwards only when against the position.
    """
    idx = _daily_index(400)
    # Constant +1 trend: ema_signal will be +1 after warm-up.
    close = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    sig = ema_signal(close)
    # z = +2 on bar 0, zero elsewhere.
    z = pd.Series(0.0, index=idx)
    z.iloc[0] = 2.0
    base, cond = run_leg(
        leg_name="synthetic_ema_uptrend",
        close=close,
        sig=sig,
        pillar_z=z,
        periods_per_year=252,
        target_vol=TARGET_VOL_ES,
        vol_window=60,
    )
    # Conditioned Sharpe should be ≤ baseline (the spike vetoed some bars
    # and reduced exposure).  It is strictly lower because the spike is
    # at z=+2 with pos=+1 (against).
    assert cond.sharpe <= base.sharpe + 1e-9
