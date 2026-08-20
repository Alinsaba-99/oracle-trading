"""BL-614 — Golden vectors through the Polars path + frequency-aware ppy.

Extends ``test_metrics_canonical.py`` (which pins the canonical numpy/list
API) to the Polars-facing surface:

1. ``MetricsCalculator`` must produce *exactly* the canonical golden
   values for Sortino and Calmar, not just sign/order sanity — the
   Polars layer is a pure delegation adapter (P1-A, ADR-021) and any
   drift would mean someone re-derived the formula locally.
2. Frequency-aware annualization: the canonical frequency table
   (``FREQ_TO_PERIODS_PER_YEAR``) covers 1h/15m/1m and the results
   scale with ``sqrt(periods_per_year)`` — the exact failure mode of
   the R5 31x Sharpe-inflation incident.

All golden numbers below are hand-computed from the MIXED series and
characterized 2026-08-20; they are frozen semantics: changing any of
them requires an ADR-021 amendment plus a conscious rewrite of the
canonical golden vectors.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl
import pytest

from analytics.backtest.metrics import (
    FREQ_TO_PERIODS_PER_YEAR,
    MetricsCalculator,
    periods_per_year_for_freq,
)
from analytics.metrics import sharpe_ratio, sortino_ratio

MIXED = [0.02, 0.01, -0.01, 0.005, 0.015, -0.005, 0.01, -0.02, 0.03, 0.0]

# Hand-computed golden constants for MIXED (characterized 2026-08-20):
# mean = 0.0055, downside std (ddof=1) = 0.012909944487358056,
# prod(1+r) = 1.0553502055714301, max drawdown = 0.02.
MIXED_SORTINO_BASE_252 = 11.431535329954588
MIXED_SORTINO_1H = 56.00285706997455
MIXED_SORTINO_15M = 112.0057141399491
MIXED_SORTINO_1M = 433.79626554409145
MIXED_CALMAR_252 = 144.34094088477806


class TestPolarsSortinoGoldenVectors:
    """MetricsCalculator.sortino_ratio must equal the canonical vectors."""

    def test_mixed_golden_value_252(self) -> None:
        returns = pl.Series("returns", MIXED)
        assert MetricsCalculator.sortino_ratio(returns) == pytest.approx(
            MIXED_SORTINO_BASE_252, rel=1e-12
        )

    def test_mixed_hourly_annualization_golden(self) -> None:
        returns = pl.Series("returns", MIXED)
        factor = FREQ_TO_PERIODS_PER_YEAR["1h"]
        assert MetricsCalculator.sortino_ratio(returns, factor) == pytest.approx(
            MIXED_SORTINO_1H, rel=1e-12
        )

    def test_no_negative_periods_is_plus_inf(self) -> None:
        returns = pl.Series("returns", [0.01, 0.01, 0.01])
        assert MetricsCalculator.sortino_ratio(returns) == math.inf

    def test_matches_canonical_for_every_factor(self) -> None:
        # The Polars adapter is pure delegation: it must agree with the
        # canonical module at every frequency, not just the golden points.
        returns = pl.Series("returns", MIXED)
        for factor in FREQ_TO_PERIODS_PER_YEAR.values():
            assert MetricsCalculator.sortino_ratio(returns, factor) == sortino_ratio(
                MIXED, periods_per_year=factor
            )


class TestPolarsCalmarGoldenVectors:
    """MetricsCalculator.calmar_ratio must equal the canonical vectors."""

    def test_mixed_golden_value_252(self) -> None:
        # growth = 1.0553502..., ann at ppy=252 over 10 bars, dd = 0.02.
        returns = pl.Series("returns", MIXED)
        assert MetricsCalculator.calmar_ratio(returns) == pytest.approx(MIXED_CALMAR_252, rel=1e-12)

    def test_mixed_golden_value_explicit_drawdown(self) -> None:
        returns = pl.Series("returns", MIXED)
        growth = float(np.prod(1.0 + np.asarray(MIXED)))
        expected = (growth ** (252 / len(MIXED)) - 1.0) / 0.25
        assert MetricsCalculator.calmar_ratio(returns, max_drawdown=0.25) == pytest.approx(
            expected, rel=1e-12
        )

    def test_hourly_series_golden_value(self) -> None:
        # 6048 hourly returns, rng seed 7: growth 0.98370165...,
        # dd 0.08487010..., calmar = -0.19203871171159306.
        rng = np.random.default_rng(7)
        series = rng.normal(1e-5, 1e-3, FREQ_TO_PERIODS_PER_YEAR["1h"])
        returns = pl.Series("returns", series)
        # MetricsCalculator.calmar_ratio currently takes no annualization
        # factor; the canonical module does.  Once the adapter delegates
        # it, this golden vector must hold exactly.
        assert MetricsCalculator.calmar_ratio(
            returns, annualization_factor=FREQ_TO_PERIODS_PER_YEAR["1h"]
        ) == pytest.approx(-0.19203871171159306, rel=1e-10)


class TestFrequencyTableGoldenVectors:
    """FREQ_TO_PERIODS_PER_YEAR is part of the frozen semantics."""

    def test_intraday_factors_present(self) -> None:
        # BL-614: 1h / 15m / 1m coverage is the acceptance criterion.
        assert FREQ_TO_PERIODS_PER_YEAR["1h"] == 252 * 24
        assert FREQ_TO_PERIODS_PER_YEAR["15m"] == 252 * 24 * 4
        assert FREQ_TO_PERIODS_PER_YEAR["1m"] == 252 * 24 * 60

    def test_lookup_helper(self) -> None:
        assert periods_per_year_for_freq("1h") == 6048
        assert periods_per_year_for_freq("15m") == 24192
        assert periods_per_year_for_freq("1m") == 362880

    def test_unknown_freq_raises_keyerror(self) -> None:
        with pytest.raises(KeyError):
            periods_per_year_for_freq("4h")


class TestFrequencyAwareScalingGoldenVectors:
    """Sharpe/Sortino scale with sqrt(ppy) across the frequency table."""

    def test_sharpe_ratios_across_frequencies(self) -> None:
        # From the canonical MIXED golden: base (ppy=252) = 5.897605365691202.
        base = sharpe_ratio(MIXED)
        for freq, ppy in FREQ_TO_PERIODS_PER_YEAR.items():
            expected = base * math.sqrt(ppy / 252)
            assert sharpe_ratio(MIXED, periods_per_year=ppy) == pytest.approx(
                expected, rel=1e-12
            ), freq

    def test_sortino_ratios_across_frequencies(self) -> None:
        base = sortino_ratio(MIXED)
        for freq, ppy in FREQ_TO_PERIODS_PER_YEAR.items():
            expected = base * math.sqrt(ppy / 252)
            assert sortino_ratio(MIXED, periods_per_year=ppy) == pytest.approx(
                expected, rel=1e-12
            ), freq

    def test_polars_and_numpy_paths_agree_on_hourly_factor(self) -> None:
        # Cross-layer golden vector: same series, ppy(1h) — the R5 class
        # of bug (wrong annualization) must be impossible to reintroduce
        # unnoticed on either path.
        returns = pl.Series("returns", MIXED)
        assert MetricsCalculator.sharpe_ratio(
            returns, FREQ_TO_PERIODS_PER_YEAR["1h"]
        ) == sharpe_ratio(MIXED, periods_per_year=FREQ_TO_PERIODS_PER_YEAR["1h"])
        assert MetricsCalculator.sortino_ratio(
            returns, FREQ_TO_PERIODS_PER_YEAR["1h"]
        ) == sortino_ratio(MIXED, periods_per_year=FREQ_TO_PERIODS_PER_YEAR["1h"])
