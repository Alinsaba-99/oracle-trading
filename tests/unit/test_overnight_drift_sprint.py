"""Test BL-739 — overnight drift sprint (matematica, no lake)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.run_overnight_drift_sprint import _apply_costs, load_1h, overnight_leg, window_leg


def _fake_hours(n: int = 48, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="h", tz="UTC")


def test_overnight_leg_is_long_only_in_overnight_hours() -> None:
    idx = _fake_hours()
    close = pd.Series(100.0, index=idx)
    pos = overnight_leg(close)  # long 20:00->13:30, flat nel cash session
    long_hours = set(range(20, 24)) | set(range(0, 13))
    # posizioni > 0 SOLO in ore overnight
    assert pos[pos > 0].index.hour.isin(long_hours).all()
    cash_hours = set(range(13, 20))
    cash_pos = pos[pos.index.hour.isin(cash_hours)].dropna()
    assert (cash_pos == 0).all()


def test_window_leg_only_hour_seven() -> None:
    idx = _fake_hours()
    close = pd.Series(100.0, index=idx)
    pos = window_leg(close, hour=7)
    assert (pos[pos.index.hour == 7] > 0).all()
    assert (pos[pos.index.hour != 7] == 0).all()


def test_apply_costs_charges_turnover() -> None:
    idx = _fake_hours(72)
    rets = pd.Series(0.001, index=idx)  # +10bps/h flat
    costs = _apply_costs(rets, cost_bps=1.5)
    # una posizione sempre attiva senza rebalance -> costo 1x per unit turnover
    assert costs < rets.sum()
    assert costs > 0


def test_load_1h_missing_returns_none(tmp_path: Path) -> None:
    assert load_1h(tmp_path, "NOTACOIN") is None
