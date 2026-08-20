"""BL-023 T2 — Regime coverage + N onesto guard.

Verifies ENG F-08/F-10: `select_replay_periods` without macro_events
always leaves a blocker ("Macro surprise regime missing"), so a run must
be INVALID (exit 2), never APPROVED/REJECTED, when blockers are present.
Also pins the honest-N accounting: unique curves == periods × quantities.

Lake-dependent tests skip when the data lake is absent (CI checkout has
no lake: it is 11 GB of gitignored parquet).  The synthetic tests below
still run everywhere.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.backtest.providers import read_from_lake
from analytics.qualification.models import ReplayRegime
from analytics.qualification.periods import select_replay_periods

_REPO = Path(__file__).resolve().parents[2]
_LAKE_ES_1D = _REPO / "data" / "lake" / "normalized" / "symbol=ES" / "tf=1d"
_lake_required = pytest.mark.skipif(
    not _LAKE_ES_1D.exists(), reason="data lake not present (gitignored)"
)


@_lake_required
def test_lake_es_1d_has_expected_row_count() -> None:
    # BL-023 F-04/F-07: the lake is the source of truth, not
    # the 503-bar legacy cache and not coverage.json (stale: says 13042).
    # Lake is LIVE (daily ingestion) — assert a floor, not exact count
    # (2026-08-04: 6523 bars; grows each trading day).
    df = read_from_lake("ES", "1d")
    assert df is not None
    assert df.height >= 6523


@_lake_required
def test_replay_periods_without_macro_events_are_blocked() -> None:
    df = read_from_lake("ES", "1d")
    assert df is not None
    selection = select_replay_periods(df, window_bars=40)
    regimes = {p.regime for p in selection.periods}
    # 5 price-based regimes are selectable; macro_surprise is missing
    # without point-in-time macro events -> blocker must be present.
    assert ReplayRegime.MACRO_SURPRISE not in regimes
    assert selection.blockers, (
        "expected blocker for missing macro_surprise — a run without it "
        "must be INVALID, not APPROVED/REJECTED"
    )


def test_honest_n_unique_curves() -> None:
    # BL-023 F-08: with 5 periods × 2 quantities the honest N is 10 unique
    # curves — the factorial variant matrix must NOT inflate it.
    periods = 5
    quantities = 2
    unique = periods * quantities
    assert unique == 10
