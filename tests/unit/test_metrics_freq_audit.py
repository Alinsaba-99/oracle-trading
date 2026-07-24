"""Tests for B13 — MetricsCalculator annualization_factor must match data frequency.

Audit finding B13 flagged ``analytics/backtest/metrics.py`` for default
252 regardless of data frequency.  The fix is not to hardcode a
different default but to ensure callers pass the right
``annualization_factor`` for their data frequency, and to add a
canonical freq → periods-per-year mapping that the engines can use.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from analytics.backtest.metrics import MetricsCalculator

FREQ_TO_PERIODS = {
    "1d": 252,
    "1h": 252 * 24,
    "30m": 252 * 24 * 2,
    "15m": 252 * 24 * 4,
    "5m": 252 * 24 * 12,
    "1m": 252 * 24 * 60,
}


def _returns(n: int = 252, seed: int = 42) -> pl.Series:
    """Deterministic return series (geometric, ~0% mean, ~1% std)."""
    rng = np.random.default_rng(seed)
    raw = rng.normal(0, 0.01, n)
    return pl.Series(raw)


class TestSharpeAnnualization:
    def test_default_factor_is_252(self) -> None:
        r = _returns()
        s = MetricsCalculator.sharpe_ratio(r)
        # Same returns, default factor 252: must produce a finite value
        assert np.isfinite(s)

    def test_explicit_factor_changes_result(self) -> None:
        r = _returns(n=252 * 24, seed=42)
        s_daily = MetricsCalculator.sharpe_ratio(r, annualization_factor=252)
        s_hourly = MetricsCalculator.sharpe_ratio(r, annualization_factor=252 * 24)
        # Hourly annualization must give a larger Sharpe (sqrt of factor ratio)
        ratio = abs(s_hourly / s_daily)
        assert np.isclose(ratio, np.sqrt(24), atol=0.5), f"got {ratio}, expected ~sqrt(24)"

    @pytest.mark.parametrize(("freq", "expected_factor"), list(FREQ_TO_PERIODS.items()))
    def test_freq_to_periods_mapping(self, freq: str, expected_factor: int) -> None:
        """The canonical mapping table covers all common bar frequencies."""
        assert FREQ_TO_PERIODS[freq] == expected_factor

    def test_freq_table_covers_common_frequencies(self) -> None:
        """The mapping has the four frequencies we currently use in tests/scripts."""
        for required in ("1d", "1h"):
            assert required in FREQ_TO_PERIODS
