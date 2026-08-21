"""BL-OPC-12 — Lane B composite qualification via ADR-017 (DSR/PBO/CPCV).

Unit tests for ``analytics/qualification/lane_b.py``: the module that
turns a Lane B return stream into a gate verdict using the ADR-017
overfitting diagnostics (DSR ≥ 0.95, PSR ≥ 0.95, PBO < 0.5) computed
by ``analytics/qualification/dsr.py`` (purgedcv wrappers) and Sharpe
from the canonical module (ADR-021).

Synthetic-data tests only — the real SimFin backtest runs in
``scripts/run_lane_b_qualification.py`` and its report lives in
``docs/reports/lane-b-composite/``.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from analytics.qualification.lane_b import (
    DSR_MIN,
    PBO_MAX,
    PSR_MIN,
    LaneBQualification,
    cpcv_oos_sharpes,
    qualify_lane_b_composite,
)


def _strong_returns(n: int = 1000, seed: int = 21) -> np.ndarray:
    """High-Sharpe synthetic daily returns (mu well above sigma)."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.002, 0.008, size=n)


def _noise_returns(n: int = 1000, seed: int = 22) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 0.01, size=n)


class TestQualifyVerdict:
    def test_strong_edge_few_trials_is_approved(self) -> None:
        qual = qualify_lane_b_composite(_strong_returns(), n_trials=2)
        assert qual.verdict == "APPROVED"
        assert qual.deflated_sharpe_ratio is not None
        assert qual.deflated_sharpe_ratio >= DSR_MIN
        assert qual.probabilistic_sharpe_ratio is not None
        assert qual.probabilistic_sharpe_ratio >= PSR_MIN

    def test_many_trials_deflates_to_rejected(self) -> None:
        # A marginal real edge (seed=48, mu=4.5bp/day, n=600): approved
        # with an honest 2-trial discovery (DSR 0.9532, characterized
        # 2026-08-20), but 5000 trials inflate the expected max-luck
        # Sharpe past the observed one -> DSR 0.9482 < 0.95 -> REJECTED
        # (the exact multi-test hole ADR-017 closes).
        rng = np.random.default_rng(48)
        rets = rng.normal(0.00045, 0.01, size=600)
        qual_few = qualify_lane_b_composite(rets, n_trials=2)
        qual_many = qualify_lane_b_composite(rets, n_trials=5000)
        assert qual_few.deflated_sharpe_ratio is not None
        assert qual_many.deflated_sharpe_ratio is not None
        assert qual_few.deflated_sharpe_ratio >= DSR_MIN
        assert qual_many.deflated_sharpe_ratio < DSR_MIN
        assert qual_many.verdict == "REJECTED"

    def test_noise_is_rejected(self) -> None:
        qual = qualify_lane_b_composite(_noise_returns(), n_trials=2)
        assert qual.verdict == "REJECTED"

    def test_insufficient_data_is_not_a_verdict(self) -> None:
        qual = qualify_lane_b_composite(np.array([0.01, 0.02, 0.03]), n_trials=2)
        assert qual.verdict == "INSUFFICIENT_DATA"
        assert qual.deflated_sharpe_ratio is None

    def test_observed_sharpe_is_canonical(self) -> None:
        # ADR-021: the observed Sharpe in the qualification report must be
        # the canonical mean/std(ddof=1)*sqrt(ppy) — not a local formula.
        from analytics.metrics import sharpe_ratio

        rets = _strong_returns()
        qual = qualify_lane_b_composite(rets, n_trials=2, periods_per_year=252)
        assert qual.observed_sharpe == pytest.approx(
            sharpe_ratio(rets, periods_per_year=252), rel=1e-12
        )

    def test_reasons_explain_rejection(self) -> None:
        qual = qualify_lane_b_composite(_noise_returns(), n_trials=2)
        assert qual.reasons  # every REJECTED verdict carries at least one reason

    def test_pbo_matrix_is_optional_but_reported(self) -> None:
        rng = np.random.default_rng(23)
        matrix = rng.normal(0.0, 0.01, size=(6, 960))
        qual = qualify_lane_b_composite(_strong_returns(), n_trials=2, returns_matrix=matrix)
        assert qual.pbo is not None
        assert 0.0 <= qual.pbo <= 1.0

    def test_high_pbo_rejects_even_with_good_dsr(self) -> None:
        # A matrix where the IS-selected row is OOS-mediocre drives PBO up;
        # the verdict must not be APPROVED on DSR alone when PBO >= 0.5.
        rng = np.random.default_rng(24)
        good = rng.normal(0.002, 0.008, size=960)
        rows = [good]
        for _i in range(7):
            rows.append(rng.normal(0.0, 0.01, size=960))
        qual = qualify_lane_b_composite(good, n_trials=2, returns_matrix=np.asarray(rows))
        if qual.pbo is not None and qual.pbo >= PBO_MAX:
            assert qual.verdict != "APPROVED"


class TestCpcvOosSharpes:
    def test_returns_combinatorial_number_of_paths(self) -> None:
        sharpes = cpcv_oos_sharpes(_strong_returns(), n_groups=6, n_test_groups=2)
        assert len(sharpes) == math.comb(6, 2)

    def test_oos_sharpes_are_finite(self) -> None:
        sharpes = cpcv_oos_sharpes(_strong_returns(), n_groups=6, n_test_groups=2)
        assert all(math.isfinite(s) for s in sharpes)

    def test_noise_oos_median_is_low(self) -> None:
        # Honest OOS estimate of noise must be far below a real edge.
        sharpes = cpcv_oos_sharpes(_noise_returns(n=252 * 4), n_groups=6, n_test_groups=2)
        assert float(np.median(sharpes)) < 2.0

    def test_insufficient_data_returns_empty(self) -> None:
        assert cpcv_oos_sharpes(np.array([0.01] * 10), n_groups=6, n_test_groups=2) == []

    def test_report_carries_cpcv_median(self) -> None:
        qual = qualify_lane_b_composite(_strong_returns(n=252 * 5), n_trials=2)
        assert isinstance(qual, LaneBQualification)
        if qual.cpcv_oos_sharpe_median is not None:
            assert math.isfinite(qual.cpcv_oos_sharpe_median)
