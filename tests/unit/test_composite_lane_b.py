"""Tests for BL-505g Composite Lane B score (Step 1 Opzione C 2026-08-16).

CompositeLaneBScore replaces the hard-AND TurnaroundScreen with a weighted
blend of Piotroski + Greenblatt + Lakonishok signals normalised to [0,1].

Coverage:
- Construction + validation (weights must sum to 1.0)
- Score normalisation (F-Score 0..9 → 0..1, magic_rank invert, return_band clamp)
- Screen threshold filtering
- Default config (since 2026-08-17, Step 3 Opzione C) uses composite=True (legacy AND is opt-in)
- Backward compat: LaneBBacktester with use_composite=False == legacy AND screen
- Forward: use_composite=True uses composite_rank for top-N selection
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import polars as pl
import pytest

from analytics.strategy.catalog.value import CompositeLaneBScore
from analytics.strategy.lane_b_backtester import LaneBBacktestConfig, LaneBBacktester

# ---------------------------------------------------------------------------
# Fixtures — synthetic cross-section with known signals
# ---------------------------------------------------------------------------


def _make_cross_section() -> pl.DataFrame:
    """Five synthetic names with known (f_score, magic_rank, return_12m).

    Layout:
      SimFinId 1: F=9, rank=1,  ret=+0.20  → perfect name (composite ≈ 0.910)
      SimFinId 2: F=6, rank=5,  ret=+0.15  → would fail AND (F<7) but composite ≈ 0.747 OK
      SimFinId 3: F=8, rank=80, ret=+0.05  → strong Piotroski, weak Greenblatt (≈ 0.507)
      SimFinId 4: F=7, rank=20, ret=-0.25  → falling knife (out of band, ≈ 0.631)
      SimFinId 5: F=5, rank=100, ret=+0.60 → hyped (out of band, ≈ 0.422)
    """
    return pl.DataFrame(
        {
            "SimFinId": [1, 2, 3, 4, 5],
            "publish_date": [datetime(2024, 1, 1)] * 5,
            "f_score": [9, 6, 8, 7, 5],
            "magic_formula_rank": [1, 5, 80, 20, 100],
            "return_12m": [0.20, 0.15, 0.05, -0.25, 0.60],
        }
    )


@pytest.fixture
def cross_section() -> pl.DataFrame:
    return _make_cross_section()


def _score_map(result: pl.DataFrame) -> dict[int, float]:
    """Return {SimFinId: composite_score} from a scored DataFrame."""
    out: dict[int, float] = {}
    for row in result.select(["SimFinId", "composite_score"]).iter_rows(named=True):
        v = row["composite_score"]
        out[row["SimFinId"]] = float(v) if v is not None else 0.0
    return out


# ---------------------------------------------------------------------------
# Construction + validation
# ---------------------------------------------------------------------------


class TestCompositeConstruction:
    def test_default_weights_sum_to_one(self) -> None:
        s = CompositeLaneBScore()
        assert abs(s.w_f_score + s.w_magic_rank + s.w_return_12m - 1.0) < 1e-6

    def test_custom_weights_sum_to_one(self) -> None:
        s = CompositeLaneBScore(w_f_score=0.5, w_magic_rank=0.3, w_return_12m=0.2)
        assert s.w_f_score == 0.5

    def test_invalid_weights_raise(self) -> None:
        with pytest.raises(ValueError, match="weights must sum to 1.0"):
            CompositeLaneBScore(w_f_score=0.5, w_magic_rank=0.5, w_return_12m=0.5)

    def test_default_threshold_0_65(self) -> None:
        assert CompositeLaneBScore().min_composite_threshold == 0.65

    def test_default_return_band(self) -> None:
        s = CompositeLaneBScore()
        assert s.return_band_min == -0.20
        assert s.return_band_max == 0.50


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------


class TestCompositeScore:
    def test_adds_composite_columns(self, cross_section: pl.DataFrame) -> None:
        result = CompositeLaneBScore().score(cross_section)
        assert "composite_score" in result.columns
        assert "composite_rank" in result.columns

    def test_perfect_name_scores_highest(self, cross_section: pl.DataFrame) -> None:
        # SimFinId 1: F=9 (best), rank=1 (best), ret=+0.20 in band → highest
        result = CompositeLaneBScore().score(cross_section)
        scores = _score_map(result)
        assert scores[1] > scores[2]
        assert scores[1] > scores[3]
        assert scores[1] > scores[4]
        assert scores[1] > scores[5]

    def test_f_score_normalisation_0_to_1(self, cross_section: pl.DataFrame) -> None:
        # SimFinId 1: F=9 → 0.4*1.0 = 0.4; rank=1 of max=100 → 0.4*(1-1/100) = 0.396;
        # ret=+0.20 in [-0.20, 0.50] → 0.2*((0.20-(-0.20))/(0.50-(-0.20))) = 0.114
        # composite ≈ 0.910
        result = CompositeLaneBScore().score(cross_section)
        scores = _score_map(result)
        assert scores[1] == pytest.approx(0.910, abs=0.01)

    def test_falling_knife_penalised(self, cross_section: pl.DataFrame) -> None:
        # SimFinId 4: ret=-0.25 (below band -0.20) → clamped to 0.0
        # F=7 → 0.4*(7/9) = 0.311; rank=20 of max=100 → 0.4*(1-20/100) = 0.32
        # composite = 0.311 + 0.32 + 0 = 0.631
        result = CompositeLaneBScore().score(cross_section)
        scores = _score_map(result)
        assert scores[4] == pytest.approx(0.631, abs=0.01)

    def test_hyped_name_penalised(self, cross_section: pl.DataFrame) -> None:
        # SimFinId 5: ret=+0.60 (above band 0.50) → clamped to 1.0
        # F=5 → 0.4*(5/9) = 0.222; rank=100 → 0.4*(1-100/100) = 0
        # composite = 0.222 + 0 + 0.2*1.0 = 0.422
        result = CompositeLaneBScore().score(cross_section)
        scores = _score_map(result)
        assert scores[5] == pytest.approx(0.422, abs=0.01)

    def test_composite_rank_lower_is_better(self, cross_section: pl.DataFrame) -> None:
        result = CompositeLaneBScore().score(cross_section)
        # Best name (SimFinId 1) should have composite_rank = 1
        best = result.filter(pl.col("SimFinId") == 1)
        assert best["composite_rank"].item() == 1

    def test_null_f_score_treated_as_zero(self, cross_section: pl.DataFrame) -> None:
        df = cross_section.with_columns(
            pl.when(pl.col("SimFinId") == 2)
            .then(None)
            .otherwise(pl.col("f_score"))
            .alias("f_score")
        )
        result = CompositeLaneBScore().score(df)
        scores = _score_map(result)
        # SimFinId 2 had F=6 (0.267 contribution); null → 0 contribution
        # Without F: 0 + 0.4*(1-5/100) + 0.2*norm_ret(0.15) = 0.398 + 0.10 = 0.498
        assert scores[2] < 0.55


# ---------------------------------------------------------------------------
# Screen filtering
# ---------------------------------------------------------------------------


class TestCompositeScreen:
    def test_threshold_filters_low_scores(self, cross_section: pl.DataFrame) -> None:
        # Default threshold 0.65: SimFinId 1 (0.910) and 2 (0.747) pass;
        # 3 (0.507), 4 (0.631), 5 (0.422) fail
        scorer = CompositeLaneBScore()
        screened = scorer.screen(cross_section)
        ids = set(screened["SimFinId"].to_list())
        assert 1 in ids
        assert 2 in ids
        assert 3 not in ids
        assert 4 not in ids
        assert 5 not in ids

    def test_screen_idempotent_when_already_scored(self, cross_section: pl.DataFrame) -> None:
        scorer = CompositeLaneBScore()
        scored = scorer.score(cross_section)
        # screen() should not re-score if composite_score already present
        screened1 = scorer.screen(scored)
        screened2 = scorer.screen(screened1)
        assert screened1.shape == screened2.shape

    def test_missing_columns_returns_no_score(self) -> None:
        df = pl.DataFrame({"SimFinId": [1], "publish_date": [datetime(2024, 1, 1)]})
        result = CompositeLaneBScore().score(df)
        # Should not raise; composite_score is null
        assert "composite_score" in result.columns
        assert result["composite_score"].item() is None


# ---------------------------------------------------------------------------
# LaneBBacktester integration — backward compat + composite path
# ---------------------------------------------------------------------------


def _make_backtester(use_composite: bool) -> LaneBBacktester:
    config = LaneBBacktestConfig(use_composite=use_composite)
    # Loader is a MagicMock — _load_all is never called by _screen_at_date
    loader: Any = MagicMock(
        spec=["income_statements", "balance_sheets", "cash_flows", "daily_prices", "companies"]
    )
    return LaneBBacktester(loader=loader, config=config)


class TestLaneBBacktesterCompositeConfig:
    def test_default_uses_composite_screen(self) -> None:
        config = LaneBBacktestConfig()
        assert config.use_composite is True

    def test_composite_config_flags(self) -> None:
        config = LaneBBacktestConfig(
            use_composite=True,
            composite_weights=(0.5, 0.3, 0.2),
            composite_threshold=0.70,
            composite_return_band=(-0.15, 0.45),
        )
        assert config.use_composite is True
        assert config.composite_weights == (0.5, 0.3, 0.2)
        assert config.composite_threshold == 0.70
        assert config.composite_return_band == (-0.15, 0.45)


class TestLaneBBacktesterScreenPath:
    """Verify _screen_at_date dispatches between composite and legacy paths."""

    def test_legacy_screen_uses_turnaround(self, cross_section: pl.DataFrame) -> None:
        bt = _make_backtester(use_composite=False)
        # Legacy screen: F>=7 AND rank<=50 AND ret in [-0.20, 0.50]
        # SimFinId 1: F=9, rank=1, ret=+0.20  → passes
        # SimFinId 3: F=8, rank=80 (>50)     → fails (rank)
        # SimFinId 4: F=7, rank=20, ret=-0.25 → fails (ret out of band)
        # SimFinId 5: F=5 (<7)               → fails (F)
        # SimFinId 2: F=6 (<7)               → fails (F)
        screened = bt._screen_at_date(cross_section, datetime(2024, 1, 1))
        assert screened.height == 1
        assert screened["SimFinId"].to_list() == [1]

    def test_composite_screen_wider_universe(self, cross_section: pl.DataFrame) -> None:
        bt = _make_backtester(use_composite=True)
        # Composite: SimFinId 1 (0.910) + 2 (0.747) pass threshold 0.65
        # SimFinId 3 (0.507), 4 (0.631), 5 (0.422) below threshold
        screened = bt._screen_at_date(cross_section, datetime(2024, 1, 1))
        ids = set(screened["SimFinId"].to_list())
        assert 1 in ids
        assert 2 in ids  # would have failed legacy screen (F<7)
        assert 5 not in ids
        assert 3 not in ids

    def test_composite_adds_score_and_rank_columns(self, cross_section: pl.DataFrame) -> None:
        bt = _make_backtester(use_composite=True)
        screened = bt._screen_at_date(cross_section, datetime(2024, 1, 1))
        assert "composite_score" in screened.columns
        assert "composite_rank" in screened.columns

    def test_legacy_does_not_add_composite_columns(self, cross_section: pl.DataFrame) -> None:
        bt = _make_backtester(use_composite=False)
        screened = bt._screen_at_date(cross_section, datetime(2024, 1, 1))
        assert "composite_score" not in screened.columns
