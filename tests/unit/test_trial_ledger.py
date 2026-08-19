"""Unit tests for analytics/research/trial_ledger.py (BL-506).

Verifies:
- Thesis pre-registration with hash chain
- Validation of position_pct, stop vs entry, target vs entry
- Outcome recording with exit_reason enum
- Hit-rate computation
- Tamper-evidence via pre_hash
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.research.trial_ledger import TrialLedger


@pytest.fixture
def ledger(tmp_path: Path) -> TrialLedger:
    """Provide a fresh TrialLedger backed by a tmp sqlite db."""
    db = tmp_path / "test_trial_ledger.db"
    return TrialLedger(db_path=str(db))


def test_register_thesis_returns_hash(ledger: TrialLedger) -> None:
    pre_hash = ledger.register_thesis(
        thesis_id="THESIS-TEST-1",
        ticker="INTC",
        entry_target=20.0,
        stop_target=18.0,
        target_price=30.0,
        position_pct=0.025,
        catalyst="New CEO + product launch",
        invalidation="Two quarters declining GM",
        horizon_days=365,
        f_score=8,
        magic_rank=15,
        return_12m=0.05,
    )
    assert len(pre_hash) == 64  # SHA-256 hex digest length
    ledger.close()


def test_register_thesis_validates_position_pct(ledger: TrialLedger) -> None:
    with pytest.raises(ValueError, match="position_pct"):
        ledger.register_thesis(
            thesis_id="X",
            ticker="A",
            entry_target=20.0,
            stop_target=18.0,
            target_price=30.0,
            position_pct=0.10,  # > 5% = too big
            catalyst="x",
            invalidation="x",
            horizon_days=100,
        )


def test_register_thesis_validates_stop_below_entry(ledger: TrialLedger) -> None:
    with pytest.raises(ValueError, match="stop_target.*entry_target"):
        ledger.register_thesis(
            thesis_id="X",
            ticker="A",
            entry_target=20.0,
            stop_target=22.0,  # > entry
            target_price=30.0,
            position_pct=0.025,
            catalyst="x",
            invalidation="x",
            horizon_days=100,
        )


def test_register_thesis_validates_target_above_entry(ledger: TrialLedger) -> None:
    with pytest.raises(ValueError, match="target_price.*entry_target"):
        ledger.register_thesis(
            thesis_id="X",
            ticker="A",
            entry_target=20.0,
            stop_target=18.0,
            target_price=15.0,  # < entry
            position_pct=0.025,
            catalyst="x",
            invalidation="x",
            horizon_days=100,
        )


def test_register_thesis_validates_horizon(ledger: TrialLedger) -> None:
    with pytest.raises(ValueError, match="horizon_days"):
        ledger.register_thesis(
            thesis_id="X",
            ticker="A",
            entry_target=20.0,
            stop_target=18.0,
            target_price=30.0,
            position_pct=0.025,
            catalyst="x",
            invalidation="x",
            horizon_days=0,
        )


def test_record_outcome_validates_exit_reason(ledger: TrialLedger) -> None:
    ledger.register_thesis(
        thesis_id="T1",
        ticker="A",
        entry_target=20.0,
        stop_target=18.0,
        target_price=30.0,
        position_pct=0.025,
        catalyst="x",
        invalidation="x",
        horizon_days=100,
    )
    with pytest.raises(ValueError, match="exit_reason"):
        ledger.record_outcome(
            thesis_id="T1",
            exit_reason="hindsight_exit",  # not in valid set
        )


def test_record_outcome_validates_thesis_exists(ledger: TrialLedger) -> None:
    with pytest.raises(ValueError, match="thesis_id"):
        ledger.record_outcome(thesis_id="NOT_REGISTERED", exit_reason="target_hit")


def test_list_theses_and_outcomes(ledger: TrialLedger) -> None:
    ledger.register_thesis(
        thesis_id="T1",
        ticker="A",
        entry_target=20.0,
        stop_target=18.0,
        target_price=30.0,
        position_pct=0.025,
        catalyst="x",
        invalidation="x",
        horizon_days=100,
    )
    ledger.register_thesis(
        thesis_id="T2",
        ticker="B",
        entry_target=50.0,
        stop_target=45.0,
        target_price=70.0,
        position_pct=0.020,
        catalyst="y",
        invalidation="y",
        horizon_days=200,
    )

    theses = ledger.list_theses()
    assert len(theses) == 2
    tickers = {t["ticker"] for t in theses}
    assert tickers == {"A", "B"}

    filtered = ledger.list_theses(ticker="A")
    assert len(filtered) == 1
    assert filtered[0]["ticker"] == "A"


def test_hit_rate_empty_returns_zero(ledger: TrialLedger) -> None:
    rate = ledger.hit_rate()
    assert rate["n_theses"] == 0
    assert rate["n_with_outcome"] == 0
    assert rate["hit_rate"] == 0.0


def test_hit_rate_with_outcomes(ledger: TrialLedger) -> None:
    # Register 4 theses
    for i, tid in enumerate(["T1", "T2", "T3", "T4"]):
        ledger.register_thesis(
            thesis_id=tid,
            ticker=f"T{i}",
            entry_target=20.0,
            stop_target=18.0,
            target_price=30.0,
            position_pct=0.025,
            catalyst="x",
            invalidation="x",
            horizon_days=100,
        )

    # Record 4 outcomes: 2 target_hit, 1 stop_hit, 1 time_stop
    ledger.record_outcome(thesis_id="T1", exit_reason="target_hit", pnl_pct=0.30)
    ledger.record_outcome(thesis_id="T2", exit_reason="target_hit", pnl_pct=0.25)
    ledger.record_outcome(thesis_id="T3", exit_reason="stop_hit", pnl_pct=-0.10)
    ledger.record_outcome(thesis_id="T4", exit_reason="time_stop", pnl_pct=0.0)

    rate = ledger.hit_rate()
    assert rate["n_theses"] == 4
    assert rate["n_with_outcome"] == 4
    assert rate["n_target_hit"] == 2
    assert rate["n_stop_hit"] == 1
    assert rate["n_time_stop"] == 1
    assert rate["hit_rate"] == 0.5  # 2/4
    assert rate["avg_pnl_pct"] == pytest.approx((0.30 + 0.25 - 0.10 + 0.0) / 4)


def test_export_for_audit_returns_dict(ledger: TrialLedger) -> None:
    ledger.register_thesis(
        thesis_id="T1",
        ticker="A",
        entry_target=20.0,
        stop_target=18.0,
        target_price=30.0,
        position_pct=0.025,
        catalyst="x",
        invalidation="x",
        horizon_days=100,
    )
    export = ledger.export_for_audit()
    assert "theses" in export
    assert "outcomes" in export
    assert "hit_rate" in export
    assert len(export["theses"]) == 1


def test_pre_hash_unique_per_thesis(ledger: TrialLedger) -> None:
    """Two theses with same content but different thesis_id have different hashes."""
    h1 = ledger.register_thesis(
        thesis_id="T1",
        ticker="A",
        entry_target=20.0,
        stop_target=18.0,
        target_price=30.0,
        position_pct=0.025,
        catalyst="x",
        invalidation="x",
        horizon_days=100,
    )
    h2 = ledger.register_thesis(
        thesis_id="T2",  # different ID
        ticker="A",
        entry_target=20.0,
        stop_target=18.0,
        target_price=30.0,
        position_pct=0.025,
        catalyst="x",
        invalidation="x",
        horizon_days=100,
    )
    assert h1 != h2


def test_sqlite_persistence_across_instances(tmp_path: Path) -> None:
    """Verify data persists across TrialLedger instances (same DB file)."""
    db = str(tmp_path / "persist.db")
    ledger1 = TrialLedger(db_path=db)
    ledger1.register_thesis(
        thesis_id="T1",
        ticker="A",
        entry_target=20.0,
        stop_target=18.0,
        target_price=30.0,
        position_pct=0.025,
        catalyst="x",
        invalidation="x",
        horizon_days=100,
    )
    ledger1.close()

    ledger2 = TrialLedger(db_path=db)
    theses = ledger2.list_theses()
    assert len(theses) == 1
    assert theses[0]["thesis_id"] == "T1"
    ledger2.close()
