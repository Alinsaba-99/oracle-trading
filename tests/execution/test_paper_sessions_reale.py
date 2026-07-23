"""Regression tests for the M32 real-data paper-session runner."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from scripts.run_paper_sessions_reale import _apply_fill, _evaluate_gate, _run_one_session


def test_apply_fill_reversal_realizes_es_point_value() -> None:
    position, entry, realized, closed = _apply_fill(
        position=Decimal("1"),
        entry_price=Decimal("100"),
        side="sell",
        quantity=Decimal("2"),
        fill_price=Decimal("110"),
        point_value=Decimal("50"),
    )

    assert position == Decimal("-1")
    assert entry == Decimal("110")
    assert realized == Decimal("500")
    assert closed == Decimal("1")


@pytest.mark.parametrize(
    ("closes", "expected_pnl"),
    [([6.0, 5.0, 4.0, 3.0, 6.0, 8.0], 100.0), ([3.0, 4.0, 5.0, 6.0, 3.0, 1.0], 100.0)],
)
async def test_session_realizes_long_and_short_pnl(
    closes: list[float], expected_pnl: float
) -> None:
    timestamps = list(pd.date_range("2026-01-01", periods=len(closes), freq="h", tz="UTC"))

    result = await _run_one_session(
        session_id=1,
        trading_date=date(2026, 1, 1),
        closes=closes,
        timestamps=timestamps,
        fast=2,
        slow=3,
        capital=Decimal("100000"),
        realistic=False,
    )

    assert result["gross_realized_pnl"] == expected_pnl
    assert result["total_commission"] == 0.0
    assert result["total_pnl"] == expected_pnl
    assert result["final_equity"] == 100000.0 + expected_pnl
    assert result["final_position"] == 0.0
    assert result["fill_rate"] == 1.0


async def test_flatten_commission_is_included_in_net_pnl() -> None:
    closes = [6.0, 5.0, 4.0, 3.0, 6.0, 8.0]
    timestamps = list(pd.date_range("2026-01-01", periods=len(closes), freq="h", tz="UTC"))

    with (
        patch("execution.brokers.paper.random.uniform", return_value=0.0),
        patch("execution.brokers.paper.random.random", return_value=1.0),
    ):
        result = await _run_one_session(
            session_id=1,
            trading_date=date(2026, 1, 1),
            closes=closes,
            timestamps=timestamps,
            fast=2,
            slow=3,
            capital=Decimal("100000"),
            realistic=True,
        )

    assert result["total_commission"] == 1.7
    assert result["gross_realized_pnl"] == 99.5
    assert result["total_pnl"] == 97.8
    assert result["final_position"] == 0.0


def test_gate_rejects_hard_incidents_across_all_windows() -> None:
    result = {
        "passed": False,
        "hard_incidents": ["max_dd_exceeded"],
        "sharpe": 1.0,
        "max_drawdown_pct": 6.0,
    }

    gate = _evaluate_gate([result] * 60)

    assert gate["decision"] == "rejected"
    assert gate["failed_windows"] == 60
    assert gate["hard_incidents"] == 60
