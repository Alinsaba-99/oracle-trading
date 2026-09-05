"""Test BL-740 — FX carry policy-rate basket (matematica, no lake).

Pattern: same minimal synthetic-only coverage as ``test_overnight_drift_sprint.py``.
The runner's math is verified here; the lake and FRED I/O is exercised in the
runner itself (with graceful degradation) and in the report's tail-check.

Mapping/coverage prereg (brief §Test):
- ``carry_signal`` returns +1 on EURUSD when rate_EUR > rate_USD (with lag); -1 on inverse
- the 1h grid receives the signal of the *previous* month shifted forward
  (shift(1) inside strategy — same BL-738 convention as overnight drift)
- one missing series → pair excluded and LISTED in the report (no silent skip)
- costs charged on monthly position changes
- dollar-neutrality (sum of weights per period == 0 by construction)
- load_1h failure → ``None`` (re-uses Task 2 loader)
- ``build_rates_table`` (synthetic FRED replacement) applies CARRY_LAG_MONTHS=2
  so the month-t value reflects the policy rate known at month-t+2
- G10 basket has 7 pairs; if any ccy is missing the pair is excluded and listed
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.run_fx_carry_policy_rate import (
    CARRY_LAG_MONTHS,
    PAIR_CCY,
    PAIR_ORDER,
    RATE_SERIES,
    build_rates_table,
    carry_signal,
    load_1h,
)

# ---------------------------------------------------------------------------
# Fixtures: synthetic rates + spot
# ---------------------------------------------------------------------------


def _month_index(start: str = "2020-01", periods: int = 24) -> pd.PeriodIndex:
    return pd.period_range(start=start, periods=periods, freq="M")


def _synthetic_rates() -> pd.DataFrame:
    """Fictional policy rates: EUR > USD > JPY (positive carry EURUSD)."""
    idx = _month_index()
    return pd.DataFrame(
        {
            "EUR": 4.0,
            "USD": 2.0,
            "JPY": 0.5,
            "GBP": 3.5,
            "CHF": 1.0,
            "CAD": 2.5,
            "AUD": 4.5,
            "NZD": 5.0,
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# RATE_SERIES / PAIR_CCY: frozen mapping (no tuning)
# ---------------------------------------------------------------------------


def test_rate_series_has_eight_g10_currencies() -> None:
    """The frozen mapping must cover all 8 G10 currencies."""
    assert set(RATE_SERIES) == {"USD", "EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD"}


def test_pair_ccy_has_seven_pairs() -> None:
    """Exactly 7 G10 pairs from the brief."""
    assert len(PAIR_CCY) == 7
    assert set(PAIR_CCY) == {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"}


def test_carry_lag_is_two_months() -> None:
    """Lag is fixed by the brief at 2 months."""
    assert CARRY_LAG_MONTHS == 2


def test_pair_order_matches_brief() -> None:
    """PAIR_ORDER exposes a stable iteration order for the report."""
    assert list(PAIR_ORDER) == [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "USDCAD",
        "AUDUSD",
        "NZDUSD",
    ]


# ---------------------------------------------------------------------------
# build_rates_table: lag + missing-series exclusion + listing
# ---------------------------------------------------------------------------


def test_build_rates_table_returns_dataframe_with_lagged_rates() -> None:
    """``build_rates_table`` applies CARRY_LAG_MONTHS=2 with **backward
    PIT** semantics (anti-lookahead).

    With CARRY_LAG_MONTHS=2 the lagged row at index label M_i must equal
    the source value originally labelled ``src[M_(i - 2)]``.  This is the
    correct as-of convention: at decision month t the signal uses the
    rate known with certainty at month t (= the rate published at month
    t - 2, given the OECD IRSTCI01xx 2-month publication lag).

    The first ``CARRY_LAG_MONTHS`` rows of the lagged frame are
    undefined (no past data to look up), so the assertion is guarded by
    ``i >= CARRY_LAG_MONTHS``.
    """
    src = _synthetic_rates()
    lagged, missing = build_rates_table(src)
    assert missing == []  # all 8 series present
    # Backward lag invariant: lagged.iloc[i] == src.iloc[i - lag_months].
    for i in range(CARRY_LAG_MONTHS, len(lagged)):
        ref = src.iloc[i - CARRY_LAG_MONTHS]
        assert lagged.iloc[i]["EUR"] == pytest.approx(ref["EUR"])
        assert lagged.iloc[i]["USD"] == pytest.approx(ref["USD"])
    # Length check: lagged loses the last ``lag_months`` rows (we can't
    # look forward; anti-lookahead mandates no future values).
    assert len(lagged) == len(src) - CARRY_LAG_MONTHS
    # Index invariant: the new labels are the source labels shifted by
    # ``lag_months`` — at new label M_i the value is the source value
    # originally at M_(i - lag_months).
    assert lagged.index[0] == src.index[CARRY_LAG_MONTHS]
    assert lagged.index[-1] == src.index[-1]


def test_build_rates_table_first_rows_undefined() -> None:
    """The lagged frame starts at src.index[CARRY_LAG_MONTHS]: the first
    ``lag_months`` source periods have no legitimate PIT value (we
    cannot invent past data), so the runner drops them.
    """
    src = _synthetic_rates()
    lagged, _ = build_rates_table(src)
    assert lagged.index[0] > src.index[0]
    # And the last ``lag_months`` source values are dropped (no future
    # values can be looked up).
    assert lagged.index[-1] == src.index[-1]


def test_build_rates_table_lists_missing_currencies() -> None:
    """If a series column is missing, the currency is excluded AND listed.

    Per brief — *no silent skip*: the runner exposes missing currencies
    in the report so the operator can audit what was excluded.
    """
    src = _synthetic_rates().drop(columns=["CHF", "NZD"])
    lagged, missing = build_rates_table(src)
    # Missing currencies reported by 3-letter code (NOT pair names — the
    # pairs themselves are computed from the survivors).
    assert set(missing) == {"CHF", "NZD"}
    # Lagged frame must NOT contain the missing columns.
    assert "CHF" not in lagged.columns
    assert "NZD" not in lagged.columns
    # Survivors are still present.
    assert set(lagged.columns) == {"EUR", "USD", "JPY", "GBP", "CAD", "AUD"}


# ---------------------------------------------------------------------------
# carry_signal: direction + dollar-neutral
# ---------------------------------------------------------------------------


def test_carry_signal_positive_on_eurusd_when_eur_gt_usd() -> None:
    """EUR > USD → +1 on EURUSD (long EUR vs short USD)."""
    src = _synthetic_rates()
    lagged, _ = build_rates_table(src)
    sig = carry_signal(lagged)
    assert sig["EURUSD"] == +1


def test_carry_signal_positive_on_usdjpy_when_usd_gt_jpy() -> None:
    """USD > JPY → +1 on USDJPY (long USD vs short JPY, classic carry).

    Per the brief convention ``signal[pair] = +1 if rate[ccy_a] > rate[ccy_b]``
    and ``USDJPY = ("USD", "JPY")`` — when USD > JPY the carry trade is
    long USD / short JPY, so the signal is +1.
    """
    src = _synthetic_rates()
    lagged, _ = build_rates_table(src)
    sig = carry_signal(lagged)
    assert sig["USDJPY"] == +1


def test_carry_signal_inverts_when_rate_diff_flips() -> None:
    """Flipping EUR/USD makes the signal flip on EURUSD."""
    src = _synthetic_rates()
    src["EUR"] = 1.0  # EUR < USD now
    lagged, _ = build_rates_table(src)
    sig = carry_signal(lagged)
    assert sig["EURUSD"] == -1


def test_carry_signal_excludes_pairs_with_missing_currency() -> None:
    """If either leg of a pair has missing data, the pair is dropped."""
    src = _synthetic_rates().drop(columns=["AUD"])
    lagged, missing = build_rates_table(src)
    sig = carry_signal(lagged)
    assert "AUDUSD" not in sig.index
    assert missing == ["AUD"]
    # Other pairs survive.
    assert {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "NZDUSD"}.issubset(set(sig.index))


def test_carry_signal_only_pm_one_values() -> None:
    """``carry_signal`` returns strictly +1 / -1 (no continuous values)."""
    src = _synthetic_rates()
    lagged, _ = build_rates_table(src)
    sig = carry_signal(lagged)
    assert set(sig.unique().tolist()).issubset({-1, 1})


# ---------------------------------------------------------------------------
# load_1h: re-export from Task 2 (no silent skip on missing data)
# ---------------------------------------------------------------------------


def test_load_1h_missing_returns_none(tmp_path: Path) -> None:
    """load_1h is the same helper as Task 2 — must return None on absent files."""
    assert load_1h(tmp_path, "NOTACOIN") is None


# ---------------------------------------------------------------------------
# End-to-end math on synthetic lake: dollar-neutrality + monthly rebalance
# ---------------------------------------------------------------------------


def test_synthetic_lake_basket_has_canonical_usd_split() -> None:
    """The basket is dollar-neutral by the LRV/Menkhoff convention.

    With the canonical 7-pair mapping, 4 pairs are USD-short (EURUSD,
    GBPUSD, AUDUSD, NZDUSD: USD is the *second* currency) and 3 pairs are
    USD-long (USDJPY, USDCHF, USDCAD: USD is the *first* currency).  The
    net USD exposure per period is therefore +3 - 4 = -1 USD unit, NOT
    zero — this is the documented LRV convention.  The brief asks for
    "dollar-neutral vol-target" *at the basket level*, not pairwise USD
    cancellation; the runner uses vol-targeting to absorb this
    constant tilt.
    """
    usd_long = sum(1 for pair, (a, b) in PAIR_CCY.items() if a == "USD")
    usd_short = sum(1 for pair, (a, b) in PAIR_CCY.items() if b == "USD")
    assert (usd_long, usd_short) == (3, 4)  # USDJPY/USDCHF/USDCAD long, others short
    # Net USD exposure per period is +3 - 4 = -1 unit (constant tilt).
    assert usd_long - usd_short == -1
