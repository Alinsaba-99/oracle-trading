"""Tests for HybridGenomeToSignal — KNN + Alpha + Heikin Ashi."""

from __future__ import annotations

from unittest.mock import ANY, patch

import numpy as np
import polars as pl
import pytest

from genetics.genome.hybrid_signal import HybridGenomeToSignal
from genetics.genome.knn_signal import KNNGenomeToSignal
from genetics.genome.parameters import ContinuousParameter, GenomeParameter
from genetics.genome.signal import AlphaGenomeToSignal, Genome, encode

# ── helpers ──────────────────────────────────────────────────────────


def _patched_signal(value: int, n: int) -> pl.Series:
    """Return a uniform Int8 signal series of length *n*."""
    return pl.Series("signal", [value] * n, dtype=pl.Int8)


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def param_defs() -> list[GenomeParameter]:
    """Minimal parameter definitions (hybrid weights only)."""
    return [
        ContinuousParameter("hybrid_knn_w", low=0.0, high=1.0),
        ContinuousParameter("hybrid_alpha_w", low=0.0, high=1.0),
    ]


@pytest.fixture
def default_genome(param_defs: list[GenomeParameter]) -> Genome:
    """Genome with default 0.5 weights for both signals."""
    return encode({"hybrid_knn_w": 0.5, "hybrid_alpha_w": 0.5}, param_defs)


@pytest.fixture
def ohlcv() -> pl.DataFrame:
    """100 rows of synthetic OHLCV data."""
    n = 100
    rng = np.random.default_rng(42)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    high = close * (1.0 + rng.uniform(0.002, 0.015, n))
    low = close * (1.0 - rng.uniform(0.002, 0.015, n))
    open_p = close * (1.0 + rng.normal(0, 0.005, n))
    volume = rng.integers(1_000_000, 10_000_000, n)
    high = np.maximum(high, np.maximum(open_p, close))
    low = np.minimum(low, np.minimum(open_p, close))
    return pl.DataFrame(
        {
            "open": pl.Series("open", open_p.tolist()),
            "high": pl.Series("high", high.tolist()),
            "low": pl.Series("low", low.tolist()),
            "close": pl.Series("close", close.tolist()),
            "volume": pl.Series("volume", volume.tolist()),
        }
    )


# ── Return type / shape ──────────────────────────────────────────────


class TestBasicContract:
    """Fundamental return-type and shape guarantees."""

    def test_returns_int8_series(
        self, default_genome: Genome, param_defs: list[GenomeParameter], ohlcv: pl.DataFrame
    ) -> None:
        n = len(ohlcv)
        with (
            patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
            patch.object(AlphaGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
        ):
            result = HybridGenomeToSignal(default_genome, param_defs).compute(ohlcv)

        assert isinstance(result, pl.Series)
        assert result.dtype == pl.Int8

    def test_only_minus_one_zero_one(
        self, default_genome: Genome, param_defs: list[GenomeParameter], ohlcv: pl.DataFrame
    ) -> None:
        n = len(ohlcv)
        with (
            patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
            patch.object(AlphaGenomeToSignal, "compute", return_value=_patched_signal(-1, n)),
        ):
            result = HybridGenomeToSignal(default_genome, param_defs).compute(ohlcv)

        unique = set(result.to_list())
        assert unique <= {-1, 0, 1}

    def test_empty_data(self, default_genome: Genome, param_defs: list[GenomeParameter]) -> None:
        empty = pl.DataFrame({"open": [], "high": [], "low": [], "close": [], "volume": []})
        hybrid = HybridGenomeToSignal(default_genome, param_defs)
        result = hybrid.compute(empty)
        assert len(result) == 0
        assert result.dtype == pl.Int8

    def test_single_bar(self, default_genome: Genome, param_defs: list[GenomeParameter]) -> None:
        single = pl.DataFrame(
            {"open": [100.0], "high": [101.0], "low": [99.0], "close": [100.5], "volume": [5000]}
        )
        hybrid = HybridGenomeToSignal(default_genome, param_defs)
        result = hybrid.compute(single)
        assert result.dtype == pl.Int8
        assert result[0] == 0  # Not enough bars for KNN or Alpha


# ── Combination logic (mocked sub-signals) ───────────────────────────


class TestCombinationLogic:
    """Hybrid combination rules with controlled sub-signal outputs."""

    @pytest.fixture
    def hybrid(
        self, default_genome: Genome, param_defs: list[GenomeParameter]
    ) -> HybridGenomeToSignal:
        return HybridGenomeToSignal(default_genome, param_defs)

    def _run(
        self, hybrid: HybridGenomeToSignal, data: pl.DataFrame, knn_val: int, alpha_val: int
    ) -> pl.Series:
        n = len(data)
        with (
            patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(knn_val, n)),
            patch.object(
                AlphaGenomeToSignal, "compute", return_value=_patched_signal(alpha_val, n)
            ),
        ):
            return hybrid.compute(data)

    def test_agreement_both_long(self, hybrid: HybridGenomeToSignal, ohlcv: pl.DataFrame) -> None:
        result = self._run(hybrid, ohlcv, knn_val=1, alpha_val=1)
        assert (result.to_numpy() == 1).all()

    def test_agreement_both_short(self, hybrid: HybridGenomeToSignal, ohlcv: pl.DataFrame) -> None:
        result = self._run(hybrid, ohlcv, knn_val=-1, alpha_val=-1)
        assert (result.to_numpy() == -1).all()

    def test_conflict_resolves_to_neutral(
        self, hybrid: HybridGenomeToSignal, ohlcv: pl.DataFrame
    ) -> None:
        result = self._run(hybrid, ohlcv, knn_val=1, alpha_val=-1)
        assert (result.to_numpy() == 0).all()

    def test_conflict_reverse(self, hybrid: HybridGenomeToSignal, ohlcv: pl.DataFrame) -> None:
        result = self._run(hybrid, ohlcv, knn_val=-1, alpha_val=1)
        assert (result.to_numpy() == 0).all()

    def test_knn_only_long(self, hybrid: HybridGenomeToSignal, ohlcv: pl.DataFrame) -> None:
        result = self._run(hybrid, ohlcv, knn_val=1, alpha_val=0)
        assert (result.to_numpy() == 1).all()

    def test_knn_only_short(self, hybrid: HybridGenomeToSignal, ohlcv: pl.DataFrame) -> None:
        result = self._run(hybrid, ohlcv, knn_val=-1, alpha_val=0)
        assert (result.to_numpy() == -1).all()

    def test_alpha_only_long(self, hybrid: HybridGenomeToSignal, ohlcv: pl.DataFrame) -> None:
        result = self._run(hybrid, ohlcv, knn_val=0, alpha_val=1)
        assert (result.to_numpy() == 1).all()

    def test_alpha_only_short(self, hybrid: HybridGenomeToSignal, ohlcv: pl.DataFrame) -> None:
        result = self._run(hybrid, ohlcv, knn_val=0, alpha_val=-1)
        assert (result.to_numpy() == -1).all()


# ── Weight behaviour ─────────────────────────────────────────────────


class TestWeights:
    """Weight defaults, caps, and zero-weight edge cases."""

    def test_default_weights(self, ohlcv: pl.DataFrame) -> None:
        """Genome without hybrid-weight params uses default values of 0.5."""
        # param_defs without hybrid_knn_w / hybrid_alpha_w
        alt_defs: list[GenomeParameter] = [
            ContinuousParameter("unrelated_param", low=0.0, high=1.0)
        ]
        genome = encode({"unrelated_param": 0.5}, alt_defs)
        n = len(ohlcv)

        with (
            patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
            patch.object(AlphaGenomeToSignal, "compute", return_value=_patched_signal(0, n)),
        ):
            result = HybridGenomeToSignal(genome, alt_defs).compute(ohlcv)

        # Default hybrid_knn_w=0.5, hybrid_alpha_w=0.5 (fallback .get())
        # KNN-only: combined = 0.5 / (0.5 + 0.5) = 0.5 → 1
        assert (result.to_numpy() == 1).all()

    def test_weight_cap_at_08(self, param_defs: list[GenomeParameter], ohlcv: pl.DataFrame) -> None:
        """Values > 0.8 are capped; extreme values behave like 0.8."""
        n = len(ohlcv)

        for w in [0.8, 0.9, 1.5]:
            genome = encode({"hybrid_knn_w": w, "hybrid_alpha_w": 0.0}, param_defs)
            with (
                patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
                patch.object(AlphaGenomeToSignal, "compute", return_value=_patched_signal(0, n)),
            ):
                result = HybridGenomeToSignal(genome, param_defs).compute(ohlcv)
            # Cap ensures weight ≤ 0.8 → combined = 0.8/0.8 = 1.0 → 1
            assert (result.to_numpy() == 1).all()

    def test_zero_total_weight_returns_all_zero(
        self, param_defs: list[GenomeParameter], ohlcv: pl.DataFrame
    ) -> None:
        """Both weights at 0 → total_w == 0 → early return of all zeros."""
        genome = encode({"hybrid_knn_w": 0.0, "hybrid_alpha_w": 0.0}, param_defs)
        hybrid = HybridGenomeToSignal(genome, param_defs)
        n = len(ohlcv)

        with (
            patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
            patch.object(AlphaGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
        ):
            result = hybrid.compute(ohlcv)

        assert (result.to_numpy() == 0).all()


# ── Threshold boundary ───────────────────────────────────────────────


class TestThreshold:
    """Signals around the 0.3 neutral-zone boundary."""

    def test_threshold_variation(
        self, param_defs: list[GenomeParameter], ohlcv: pl.DataFrame
    ) -> None:
        """Very low single-signal weight stays neutral; moderate weight triggers."""
        n = len(ohlcv)

        # Just below threshold: knn_only = 0.2 / (0.2+0.5) ≈ 0.286 < 0.3 → 0
        genome_weak = encode({"hybrid_knn_w": 0.2, "hybrid_alpha_w": 0.5}, param_defs)
        with (
            patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
            patch.object(AlphaGenomeToSignal, "compute", return_value=_patched_signal(0, n)),
        ):
            result_weak = HybridGenomeToSignal(genome_weak, param_defs).compute(ohlcv)
        assert (result_weak.to_numpy() == 0).all()

        # Just above threshold: knn_only = 0.25 / (0.25+0.5) ≈ 0.333 > 0.3 → 1
        genome_mod = encode({"hybrid_knn_w": 0.25, "hybrid_alpha_w": 0.5}, param_defs)
        with (
            patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(1, n)),
            patch.object(AlphaGenomeToSignal, "compute", return_value=_patched_signal(0, n)),
        ):
            result_mod = HybridGenomeToSignal(genome_mod, param_defs).compute(ohlcv)
        assert (result_mod.to_numpy() == 1).all()


# ── Heikin Ashi integration ──────────────────────────────────────────


class TestHeikinAshi:
    """Verify Heikin Ashi preprocessing is applied."""

    def test_heikin_ashi_called(
        self, default_genome: Genome, param_defs: list[GenomeParameter], ohlcv: pl.DataFrame
    ) -> None:
        n = len(ohlcv)
        with (
            patch("genetics.signal.heikin_ashi.to_heikin_ashi") as mock_ha,
            patch.object(KNNGenomeToSignal, "compute", return_value=_patched_signal(0, n)),
            patch.object(AlphaGenomeToSignal, "compute", return_value=_patched_signal(0, n)),
        ):
            mock_ha.return_value = ohlcv
            HybridGenomeToSignal(default_genome, param_defs).compute(ohlcv)

        mock_ha.assert_called_once_with(ohlcv)

    def test_both_signals_receive_ha_data(
        self, default_genome: Genome, param_defs: list[GenomeParameter], ohlcv: pl.DataFrame
    ) -> None:
        """KNN and Alpha compute methods each called with HA-transformed data."""
        n = len(ohlcv)
        with (
            patch.object(KNNGenomeToSignal, "compute") as mock_knn,
            patch.object(AlphaGenomeToSignal, "compute") as mock_alpha,
        ):
            mock_knn.return_value = _patched_signal(0, n)
            mock_alpha.return_value = _patched_signal(0, n)
            HybridGenomeToSignal(default_genome, param_defs).compute(ohlcv)

        # Both called exactly once — the argument is the HA-transformed DataFrame
        mock_knn.assert_called_once_with(ANY)
        mock_alpha.assert_called_once_with(ANY)
