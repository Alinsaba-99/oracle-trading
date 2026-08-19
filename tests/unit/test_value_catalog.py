"""Unit tests for analytics/strategy/catalog/value.py (BL-505 / Lane B).

Verifies:
- Piotroski F-Score: 9-point binary, monotone in inputs, edge cases (None data)
- Lakonishok value-momentum: percentile rank filtering
- Greenblatt Magic Formula: composite rank + top-N selection
- TurnaroundScreen: composite filter
"""

from __future__ import annotations

import polars as pl

from analytics.strategy.catalog.value import (
    GreenblattMagicFormula,
    LakonishokValueMomentum,
    PiotroskiFScore,
    TurnaroundScreen,
)

# =========================================================================
# Piotroski F-Score
# =========================================================================


def test_piotroski_f_score_all_positive_returns_9() -> None:
    """All-positive financials → F-Score = 9."""
    s = PiotroskiFScore.compute(
        roa=0.15,  # > 0 ✓
        cfo=0.20,  # > 0 ✓, > ROA ✓ (accruals)
        roa_prev=0.10,  # roa > roa_prev ✓
        accruals=0.0,  # not directly used; cfo > roa check handles it
        leverage_prev=0.5,
        leverage_curr=0.4,  # leverage down ✓
        current_ratio_prev=1.5,
        current_ratio_curr=2.0,  # CR up ✓
        equity_issued=False,  # no issuance ✓
        gross_margin_prev=0.30,
        gross_margin_curr=0.35,  # GM up ✓
        asset_turnover_prev=0.5,
        asset_turnover_curr=0.7,  # AT up ✓
    )
    assert s == 9


def test_piotroski_f_score_all_negative_returns_0() -> None:
    """All-negative financials → F-Score = 0."""
    s = PiotroskiFScore.compute(
        roa=-0.05,
        cfo=-0.10,
        roa_prev=0.05,  # roa < roa_prev
        accruals=0.0,
        leverage_prev=0.4,
        leverage_curr=0.5,  # leverage up
        current_ratio_prev=2.0,
        current_ratio_curr=1.5,  # CR down
        equity_issued=True,  # issued equity
        gross_margin_prev=0.35,
        gross_margin_curr=0.30,  # GM down
        asset_turnover_prev=0.7,
        asset_turnover_curr=0.5,  # AT down
    )
    assert s == 0


def test_piotroski_f_score_handles_none_data() -> None:
    """None values for inputs contribute 0 to the score (graceful degradation)."""
    s = PiotroskiFScore.compute(
        roa=None,
        cfo=0.20,  # > 0 ✓
        roa_prev=None,
        accruals=None,
        leverage_prev=None,
        leverage_curr=None,
        current_ratio_prev=None,
        current_ratio_curr=None,
        equity_issued=None,
        gross_margin_prev=None,
        gross_margin_curr=None,
        asset_turnover_prev=None,
        asset_turnover_curr=None,
    )
    # Only CFO > 0 contributes
    assert s == 1


def test_piotroski_f_score_accruals_check_uses_cfo_vs_roa() -> None:
    """The accruals component: +1 if CFO > ROA (earnings quality)."""
    # roa=0.05, cfo=0.20 → cfo > roa → +1 accruals
    # ALSO: roa=0.05 > 0 → +1 profitability
    # ALSO: cfo=0.20 > 0 → +1 profitability (CFO > 0)
    # No ΔROA (roa_prev=None) so no point there.
    # Total: 3 (roa > 0, cfo > 0, cfo > roa)
    s_good_accruals = PiotroskiFScore.compute(
        roa=0.05,
        cfo=0.20,
        roa_prev=None,
        accruals=None,
        leverage_prev=None,
        leverage_curr=None,
        current_ratio_prev=None,
        current_ratio_curr=None,
        equity_issued=None,
        gross_margin_prev=None,
        gross_margin_curr=None,
        asset_turnover_prev=None,
        asset_turnover_curr=None,
    )
    # roa=0.20, cfo=0.05 → cfo < roa → NO accruals point
    # roa > 0 → +1; cfo > 0 → +1; cfo > roa? No → 0
    # Total: 2
    s_bad_accruals = PiotroskiFScore.compute(
        roa=0.20,
        cfo=0.05,
        roa_prev=None,
        accruals=None,
        leverage_prev=None,
        leverage_curr=None,
        current_ratio_prev=None,
        current_ratio_curr=None,
        equity_issued=None,
        gross_margin_prev=None,
        gross_margin_curr=None,
        asset_turnover_prev=None,
        asset_turnover_curr=None,
    )
    assert s_good_accruals == 3, f"got {s_good_accruals}"
    assert s_bad_accruals == 2, f"got {s_bad_accruals}"


# =========================================================================
# Lakonishok Value-Momentum
# =========================================================================


def test_lakonishok_filters_cheap_and_positive_momentum() -> None:
    """Long universe: bottom-30% P/B + bottom-30% P/E + positive past return."""
    rng_data = [
        {"ticker": "A", "pb": 1.0, "pe": 5.0, "return_12m": 0.05},
        {"ticker": "B", "pb": 1.5, "pe": 7.0, "return_12m": 0.10},
        {"ticker": "C", "pb": 5.0, "pe": 25.0, "return_12m": 0.40},  # expensive
        {"ticker": "D", "pb": 2.0, "pe": 10.0, "return_12m": -0.20},  # cheap but neg momentum
    ]
    df = pl.DataFrame(rng_data)
    lvm = LakonishokValueMomentum()
    result = lvm.filter(df)
    tickers = set(result["ticker"].to_list())
    # With 4 rows, bottom-30% threshold = max(1, int(0.30*4)) = 1
    # So pb_rank <= 1 means only the cheapest P/B (A: pb=1.0, rank=1)
    # And pe_rank <= 1 means only the cheapest P/E (A: pe=5.0, rank=1)
    # Plus positive momentum. Only A passes all three.
    # B has pb=1.5 (rank=2, > 1) → filtered out
    # C too expensive → filtered out
    # D has neg momentum → filtered out
    assert "A" in tickers, f"expected A in {tickers}"
    assert "B" not in tickers
    assert "C" not in tickers
    assert "D" not in tickers


def test_lakonishok_larger_universe_more_permissive() -> None:
    """With 10 stocks, bottom-30% = 3, so 3 cheapest pass the value filter."""
    rng_data = [
        {"ticker": f"T{i}", "pb": float(i + 1), "pe": float(i + 1), "return_12m": 0.05}
        for i in range(10)
    ]
    df = pl.DataFrame(rng_data)
    lvm = LakonishokValueMomentum()
    result = lvm.filter(df)
    # bottom-30% threshold = max(1, int(0.30 * 10)) = 3
    # Both pb_rank and pe_rank must be <= 3, which is satisfied by T0, T1, T2
    tickers = set(result["ticker"].to_list())
    assert "T0" in tickers
    assert "T1" in tickers
    assert "T2" in tickers
    assert "T3" not in tickers


def test_lakonishok_handles_empty_input() -> None:
    lvm = LakonishokValueMomentum()
    result = lvm.filter(
        pl.DataFrame(
            schema={"ticker": pl.Utf8, "pb": pl.Float64, "pe": pl.Float64, "return_12m": pl.Float64}
        )
    )
    assert result.height == 0


# =========================================================================
# Greenblatt Magic Formula
# =========================================================================


def test_greenblatt_ranks_by_earnings_yield_plus_roc() -> None:
    """Lower magic_formula_rank = better (cheap + high ROC).

    With 3 rows, ordinal rank assigns 1, 2, 3 — ties broken arbitrarily
    by Polars, so the combined rank ordering can vary. We verify the
    *worst* stock (B: low EY, low ROC) ranks last and the *best* is either
    A or C (both have high EY but C has higher ROC).
    """
    df = pl.DataFrame(
        [
            {"ticker": "A", "ebit": 100, "ev": 500, "nwc": 50, "nfa": 100},  # EY=0.20, ROC=0.67
            {"ticker": "B", "ebit": 50, "ev": 1000, "nwc": 50, "nfa": 100},  # EY=0.05, ROC=0.33
            {"ticker": "C", "ebit": 200, "ev": 1000, "nwc": 50, "nfa": 100},  # EY=0.20, ROC=1.33
        ]
    )
    gf = GreenblattMagicFormula(top_n=10)
    ranked = gf.rank(df).sort("magic_formula_rank")
    assert ranked.height == 3
    # B has the worst EY and worst ROC → should be ranked last (highest rank number)
    assert ranked["ticker"].to_list()[-1] == "B"
    # The best is A or C (both EY-tie at top); either is acceptable
    best = ranked["ticker"].to_list()[0]
    assert best in {"A", "C"}


def test_greenblatt_top_n_limits_output() -> None:
    df = pl.DataFrame(
        [{"ticker": f"T{i}", "ebit": 100 - i, "ev": 500, "nwc": 50, "nfa": 100} for i in range(20)]
    )
    gf = GreenblattMagicFormula(top_n=5)
    ranked = gf.rank(df)
    assert ranked.height == 5


def test_greenblatt_filters_zero_ev() -> None:
    """Companies with EV=0 should be filtered out (division by zero)."""
    df = pl.DataFrame(
        [
            {"ticker": "A", "ebit": 100, "ev": 0, "nwc": 50, "nfa": 100},
            {"ticker": "B", "ebit": 50, "ev": 500, "nwc": 50, "nfa": 100},
        ]
    )
    gf = GreenblattMagicFormula(top_n=10)
    ranked = gf.rank(df)
    assert ranked.height == 1
    assert ranked["ticker"].to_list() == ["B"]


# =========================================================================
# TurnaroundScreen (composite)
# =========================================================================


def test_turnaround_screen_combines_all_three_filters() -> None:
    """Composite: F-Score >= 7 + magic_formula_rank <= 50 + past return in [-20%, +50%]."""
    df = pl.DataFrame(
        [
            {"ticker": "GOOD", "f_score": 8, "magic_formula_rank": 10, "return_12m": 0.10},
            {"ticker": "WEAK_FSCORE", "f_score": 5, "magic_formula_rank": 10, "return_12m": 0.10},
            {"ticker": "EXPENSIVE", "f_score": 8, "magic_formula_rank": 60, "return_12m": 0.10},
            {"ticker": "TOO_HYPED", "f_score": 8, "magic_formula_rank": 10, "return_12m": 0.80},
            {
                "ticker": "TOO_DEPRESSED",
                "f_score": 8,
                "magic_formula_rank": 10,
                "return_12m": -0.30,
            },
        ]
    )
    screen = TurnaroundScreen()
    result = screen.screen(df)
    # Only GOOD passes all filters
    assert result.height == 1
    assert result["ticker"].to_list() == ["GOOD"]


def test_turnaround_screen_missing_columns_returns_empty() -> None:
    df = pl.DataFrame({"ticker": ["A"]})  # no f_score, magic_formula_rank, return_12m
    screen = TurnaroundScreen()
    result = screen.screen(df)
    assert result.height == 0
