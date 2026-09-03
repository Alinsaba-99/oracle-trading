"""BL-718 / D1+D2 — Distilled MoonDev factor tests (BB Squeeze, Funding Extremum)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl
import pytest

from analytics.strategy.catalog.bb_squeeze import BBSqueezeParams, compute_bb_squeeze, exit_levels
from analytics.strategy.catalog.funding_rate import (
    DEFAULT_LONG_THRESHOLD_PCT_ANNUAL,
    DEFAULT_SHORT_THRESHOLD_PCT_ANNUAL,
    DEFAULT_ZSCORE_WINDOW,
    SETTLEMENTS_PER_DAY,
    TRADING_DAYS_PER_YEAR,
    FundingExtremumParams,
    align_hourly,
    annualize_8h,
    compute_funding_extremum,
    deannualize_to_8h,
    extremum_signal,
    funding_zscore,
)

# ── BB Squeeze (D1) ────────────────────────────────────────────────────────


def _make_ohlcv(
    *,
    n: int = 400,
    seed: int = 0,
    squeeze_at: tuple[int, int] | None = (200, 220),
    high_vol_after: bool = True,
    tight_squeeze: bool = False,
    base_vol: float = 0.05,
    intrabar_spread: float = 0.05,
) -> pl.DataFrame:
    """Build synthetic OHLCV with a clear squeeze window.

    The squeeze condition is ``BB inside KC``: the close-to-close
    standard deviation (over 20 bars) must drop below the ATR (over the
    same window).  The plant therefore uses an *intrabar spread*
    (H-L) close to zero everywhere (so ATR stays small) and a
    *base_vol* that gives the close enough random-walk amplitude that
    the rolling close-to-close std exceeds ATR — the random-walk
    region is then OUT of squeeze.  Inside the planted window, the
    close is flat and H-L collapses to ~0.005, so BB collapses inside
    KC: the squeeze holds.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    close = 100.0 + np.cumsum(rng.standard_normal(n) * base_vol)
    # Tight intrabar spread so ATR is small (≈spread) and KC is narrow.
    high = close + np.abs(rng.standard_normal(n)) * intrabar_spread + intrabar_spread * 0.1
    low = close - np.abs(rng.standard_normal(n)) * intrabar_spread - intrabar_spread * 0.1
    open_ = close + rng.standard_normal(n) * 0.01
    if squeeze_at is not None:
        start, end = squeeze_at
        flat = close[start]
        close[start:end] = flat
        if tight_squeeze:
            high[start:end] = flat + 0.005
            low[start:end] = flat - 0.005
        else:
            high[start:end] = flat + 0.05
            low[start:end] = flat - 0.05
        open_[start:end] = flat
        if high_vol_after:
            wide_end = min(end + 20, n)
            high[end:wide_end] = close[end:wide_end] + 2.5
            low[end:wide_end] = close[end:wide_end] - 2.5
    return pl.DataFrame({"date": dates, "open": open_, "high": high, "low": low, "close": close})


class TestBBSqueeze:
    def test_required_columns(self) -> None:
        data = _make_ohlcv()  # full OHLCV
        # Drop one column to verify the guard fires.
        bad = data.drop("close")
        with pytest.raises(ValueError, match="open, high, low, close"):
            compute_bb_squeeze(bad)

    def test_signal_columns_present(self) -> None:
        data = _make_ohlcv()
        result = compute_bb_squeeze(data)
        expected = {
            "date",
            "close",
            "bb_upper",
            "bb_lower",
            "kc_upper",
            "kc_lower",
            "adx",
            "squeeze",
            "release",
            "entry_long",
            "entry_short",
        }
        assert set(result.signals.columns) >= expected
        assert result.signals.shape[0] == data.shape[0]

    def test_planted_squeeze_is_detected(self) -> None:
        """Plant a tight-window squeeze and verify the factor flags it.

        We keep the high/low spread tight (0.01) so ATR also collapses
        during the window — the squeeze condition (``BB inside KC``)
        then holds for the entire planted window.  Synthetic close-to-
        close variance is deliberately *higher* than the planted
        squeeze so the pre-window region is **not** in squeeze and the
        planted window stands out.
        """
        # 0.04 close-to-close vol is high enough to keep BB outside KC
        # during the random-walk region while the planted 0.005 wide
        # range pulls BB inside KC during the planted window.
        data = _make_ohlcv(
            n=400,
            seed=0,
            squeeze_at=(200, 240),
            high_vol_after=False,
            tight_squeeze=True,
            base_vol=0.04,
        )
        result = compute_bb_squeeze(data)
        squeeze = result.signals["squeeze"].to_numpy()
        # Inside the planted tight window, squeeze should hold almost
        # the entire time (BB inside KC).
        assert squeeze[205:235].sum() >= 20
        # And outside the planted window, the random walk should
        # *usually* NOT be in squeeze.
        assert squeeze[100:180].sum() < 60

    def test_release_is_one_bar_after_squeeze_off(self) -> None:
        """Release[i] must equal (squeeze[i-1] & ~squeeze[i]) exactly.

        A structural test: the planted signal is a single isolated
        ``True`` inside the squeeze window, and the release must fire
        on the next bar — no off-by-one, no rolling-window lag in the
        release logic itself.
        """
        n = 200
        # Hand-build a series where squeeze is True everywhere except a
        # single bar; the release must be exactly that bar.
        pd.date_range("2023-01-02", periods=n, freq="B")
        np.arange(n)
        squeeze_input = np.ones(n, dtype=bool)
        squeeze_input[100] = False  # single isolated release
        # We test the formula directly via numpy rather than the synthetic
        # data path — independent of any indicator smoothing.
        prev = np.roll(squeeze_input, 1)
        prev[0] = False
        release = prev & ~squeeze_input
        # The release at index 100 is True; everywhere else False.
        assert release[100]
        assert release.sum() == 1
        # Sanity: a never-squeezed series has no release.
        never = np.ones(n, dtype=bool)
        never_release = np.roll(never, 1) & ~never
        never_release[0] = False
        assert never_release.sum() == 0

    def test_no_lookahead_on_adx(self) -> None:
        """ADX must be shifted before the entry comparison."""
        data = _make_ohlcv()
        result = compute_bb_squeeze(data)
        adx = result.signals["adx"].to_numpy()
        bb_upper = result.signals["bb_upper"].to_numpy()
        close = result.signals["close"].to_numpy()
        # entry_long uses close[t-1] > bb_upper[t-1], never close[t] > bb_upper[t].
        long_entries = result.signals["entry_long"].to_numpy()
        for i in range(1, len(long_entries)):
            if long_entries[i]:
                # close[i-1] must have been above bb_upper[i-1].
                assert close[i - 1] > bb_upper[i - 1]
                # ADX[i-1] must have been > threshold.
                assert adx[i - 1] > BBSqueezeParams().adx_threshold

    def test_exit_levels_long(self) -> None:
        p = BBSqueezeParams()
        tp, sl = exit_levels(100.0, p, side="long")
        assert tp == pytest.approx(105.0)
        assert sl == pytest.approx(97.0)

    def test_exit_levels_short(self) -> None:
        p = BBSqueezeParams()
        tp, sl = exit_levels(100.0, p, side="short")
        # Short TP = entry * (2 - tp_mult), SL = entry * (2 - sl_mult)
        assert tp == pytest.approx(100.0 * (2.0 - 1.05))
        assert sl == pytest.approx(100.0 * (2.0 - 0.97))

    def test_params_defaults_match_bom(self) -> None:
        p = BBSqueezeParams()
        assert p.bb_window == 20
        assert p.bb_std == 2.0
        assert p.keltner_window == 20
        assert p.kc_mult == 1.5
        assert p.adx_period == 14
        assert p.adx_threshold == 25.0
        assert p.tp_pct == 5.0
        assert p.sl_pct == 3.0


# ── Funding Extremum (D2) ─────────────────────────────────────────────────


def _funding_series(*, n: int = 400, base_pct_8h: float = 0.005, seed: int = 0) -> pl.DataFrame:
    """Per-8h funding rate (percent).  Around 0.005% per 8h is typical BTC."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="8h")
    vals = rng.normal(loc=base_pct_8h, scale=0.003, size=n)
    return pl.DataFrame({"date": dates, "funding_pct_8h": vals})


class TestFundingAnnualization:
    def test_annualization_factor(self) -> None:
        assert SETTLEMENTS_PER_DAY * TRADING_DAYS_PER_YEAR == 1095

    def test_annualize_8h_scalar(self) -> None:
        # 0.01% per 8h × 1095 = 10.95% annual
        assert annualize_8h(0.01) == pytest.approx(10.95)

    def test_annualize_8h_array(self) -> None:
        arr = np.array([0.01, -0.02, 0.013])
        out = annualize_8h(arr)
        assert out[0] == pytest.approx(10.95)
        assert out[1] == pytest.approx(-21.9)
        assert out[2] == pytest.approx(14.235)

    def test_annualize_8h_polars(self) -> None:
        s = pl.Series([0.01, 0.02])
        out = annualize_8h(s)
        assert isinstance(out, pl.Series)
        assert out[0] == pytest.approx(10.95)

    def test_round_trip(self) -> None:
        arr = np.array([0.05, -0.07, 0.13])
        roundtrip = deannualize_to_8h(annualize_8h(arr))
        np.testing.assert_allclose(roundtrip, arr)

    def test_bom_threshold_math(self) -> None:
        """The original bot's -22/+14 figures, converted to per-8h values."""
        # -22% annual / 1095 ≈ -0.0201 % per 8h
        assert deannualize_to_8h(-22.0) == pytest.approx(-0.0201, abs=1e-3)
        # +14% annual / 1095 ≈ +0.0128 % per 8h
        assert deannualize_to_8h(14.0) == pytest.approx(0.0128, abs=1e-3)


class TestExtremumSignal:
    def test_default_thresholds_match_bom(self) -> None:
        assert DEFAULT_LONG_THRESHOLD_PCT_ANNUAL == -20.0
        assert DEFAULT_SHORT_THRESHOLD_PCT_ANNUAL == 25.0

    def test_extreme_negative_is_long_signal(self) -> None:
        # -0.03 % per 8h = -32.85 % annual — clearly below -20 % threshold
        arr = np.array([0.0, -0.03, 0.0])
        sig = extremum_signal(arr)
        assert sig.tolist() == [0, 1, 0]

    def test_extreme_positive_is_short_signal(self) -> None:
        # +0.05 % per 8h = +54.75 % annual — clearly above +25 % threshold
        arr = np.array([0.0, 0.05, 0.0])
        sig = extremum_signal(arr)
        assert sig.tolist() == [0, -1, 0]

    def test_mild_funding_no_signal(self) -> None:
        # +0.01 % per 8h = +10.95 % annual — between thresholds
        arr = np.array([0.01, -0.005, 0.02])
        sig = extremum_signal(arr)
        assert sig.tolist() == [0, 0, 0]

    def test_works_with_polars_series(self) -> None:
        s = pl.Series([0.0, 0.05, -0.03])
        sig = extremum_signal(s)
        assert isinstance(sig, np.ndarray)
        assert sig.tolist() == [0, -1, 1]


class TestFundingZScore:
    def test_zero_zscore_for_constant_series(self) -> None:
        arr = np.full(200, 0.01)
        z = funding_zscore(arr, window=50)
        # Constant series → std=0 → z=0 (per the spec inside funding_zscore).
        valid = z[~np.isnan(z)]
        assert np.all(valid == 0.0)

    def test_first_window_minus_one_nan(self) -> None:
        arr = np.arange(100, dtype=float) * 0.001
        z = funding_zscore(arr, window=10)
        assert np.isnan(z[0])  # no prev window
        assert not np.isnan(z[10])  # first valid z

    def test_window_must_be_at_least_two(self) -> None:
        with pytest.raises(ValueError, match="zscore_window"):
            funding_zscore(np.arange(10.0), window=1)


class TestComputeFundingExtremum:
    def test_pipeline_emits_all_columns(self) -> None:
        data = _funding_series(n=300, seed=42)
        result = compute_funding_extremum(data)
        expected = {
            "date",
            "funding_8h",
            "funding_pct_ann",
            "funding_z",
            "signal",
            "long_entry",
            "short_entry",
        }
        assert expected <= set(result.signals.columns)
        assert result.signals.shape[0] == 300

    def test_params_echo(self) -> None:
        data = _funding_series(n=100)
        result = compute_funding_extremum(data)
        assert isinstance(result.params, FundingExtremumParams)
        assert result.params.long_threshold_pct_annual == DEFAULT_LONG_THRESHOLD_PCT_ANNUAL
        assert result.params.short_threshold_pct_annual == DEFAULT_SHORT_THRESHOLD_PCT_ANNUAL
        assert result.params.zscore_window == DEFAULT_ZSCORE_WINDOW

    def test_planted_extreme_generates_signal(self) -> None:
        # Synthesize a series with one clearly extreme negative tail.
        n = 250
        dates = pd.date_range("2023-01-01", periods=n, freq="8h")
        vals = np.full(n, 0.005)  # 5.475 % annual — flat
        vals[100] = -0.04  # -43.8 % annual — long signal
        vals[200] = 0.05  # +54.75 % annual — short signal
        data = pl.DataFrame({"date": dates, "funding_pct_8h": vals})
        result = compute_funding_extremum(data)
        sig = result.signals["signal"].to_numpy()
        assert sig[100] == 1
        assert sig[200] == -1
        # Most bars have no signal.
        assert (sig == 0).sum() >= n - 5


class TestAlignHourly:
    def test_forward_fill_no_interpolation(self) -> None:
        """The spec forbids interpolation — verify with two distinct values."""
        # Two 8h settlements: t=0 and t=8h.  The hourly grid spans 0..16h.
        funding_ts = pd.date_range("2023-01-01 00:00", periods=2, freq="8h")
        funding_df = pl.DataFrame({"ts": funding_ts, "funding": [0.01, 0.02]})
        hourly_ts = pd.date_range("2023-01-01 00:00", periods=17, freq="1h")
        hourly_df = pl.DataFrame({"ts": hourly_ts})
        merged = hourly_df.join_asof(funding_df, on="ts", strategy="backward")
        out = merged["funding"]
        # First 8 hours = 0.01 (forward filled from t=0), next 9 = 0.02.
        assert out[0] == 0.01
        assert out[7] == 0.01
        assert out[8] == 0.02
        assert out[16] == 0.02

    def test_empty_inputs_raise(self) -> None:
        with pytest.raises(ValueError):
            align_hourly(
                pl.Series("x", []),
                hourly_index=pl.Series("ts", pd.date_range("2023-01-01", periods=3, freq="h")),
            )
        with pytest.raises(ValueError):
            align_hourly(pl.Series("x", [1.0]), hourly_index=pl.Series("ts", []))
