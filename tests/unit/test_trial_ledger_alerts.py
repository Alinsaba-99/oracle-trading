"""Unit tests for analytics/research/trial_ledger_alerts.py (BL-506b)."""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.research.trial_ledger import TrialLedger
from analytics.research.trial_ledger_alerts import (
    cumulative_hit_rate_over_time,
    detect_alerts,
    generate_alert_report,
    max_consecutive_failures,
    rolling_hit_rate,
)


@pytest.fixture
def ledger(tmp_path: Path) -> TrialLedger:
    return TrialLedger(db_path=str(tmp_path / "test_alerts.db"))


def _register_thesis(ledger: TrialLedger, thesis_id: str, ticker: str = "TEST") -> None:
    ledger.register_thesis(
        thesis_id=thesis_id,
        ticker=ticker,
        entry_target=20.0,
        stop_target=18.0,
        target_price=30.0,
        position_pct=0.025,
        catalyst="x",
        invalidation="x",
        horizon_days=100,
    )


def _record_outcome(
    ledger: TrialLedger, thesis_id: str, exit_reason: str, pnl_pct: float = 0.0
) -> None:
    ledger.record_outcome(thesis_id=thesis_id, exit_reason=exit_reason, pnl_pct=pnl_pct)


def test_cumulative_hit_rate_empty_returns_empty(ledger: TrialLedger) -> None:
    series = cumulative_hit_rate_over_time(ledger)
    assert series == []


def test_cumulative_hit_rate_with_mixed_outcomes(ledger: TrialLedger) -> None:
    for i, (reason, _) in enumerate(
        [("target_hit", 0.30), ("stop_hit", -0.10), ("target_hit", 0.25), ("target_hit", 0.20)]
    ):
        _register_thesis(ledger, f"T{i}")
        _record_outcome(ledger, f"T{i}", reason, _)
    series = cumulative_hit_rate_over_time(ledger)
    assert len(series) == 4
    # 4 outcomes: 1 hit (1/1), 1 hit (1/2), 2 hits (2/3), 3 hits (3/4)
    assert series[0].cumulative_hit_rate == pytest.approx(1.0)
    assert series[1].cumulative_hit_rate == pytest.approx(0.5)
    assert series[2].cumulative_hit_rate == pytest.approx(2 / 3)
    assert series[3].cumulative_hit_rate == pytest.approx(0.75)


def test_rolling_hit_rate_returns_window_entries(ledger: TrialLedger) -> None:
    for i in range(15):
        _register_thesis(ledger, f"T{i}")
        reason = "target_hit" if i % 3 == 0 else "stop_hit"
        _record_outcome(ledger, f"T{i}", reason)
    series = rolling_hit_rate(ledger, window_size=10)
    # First window entry after 10 outcomes
    assert len(series) == 6  # 15 - 10 + 1


def test_max_consecutive_failures_zero_when_all_hits(ledger: TrialLedger) -> None:
    for i in range(5):
        _register_thesis(ledger, f"T{i}")
        _record_outcome(ledger, f"T{i}", "target_hit")
    assert max_consecutive_failures(ledger) == 0


def test_max_consecutive_failures_counts_longest_streak(ledger: TrialLedger) -> None:
    # Pattern: fail, fail, fail, hit, fail, hit, fail, fail
    pattern = [
        "stop_hit",
        "stop_hit",
        "stop_hit",
        "target_hit",
        "stop_hit",
        "target_hit",
        "stop_hit",
        "stop_hit",
    ]
    for i, reason in enumerate(pattern):
        _register_thesis(ledger, f"T{i}")
        _record_outcome(ledger, f"T{i}", reason)
    assert max_consecutive_failures(ledger) == 3


def test_detect_alerts_empty_when_no_outcomes(ledger: TrialLedger) -> None:
    alerts = detect_alerts(ledger)
    assert alerts == []


def test_detect_alerts_consecutive_failures(ledger: TrialLedger) -> None:
    """5 consecutive non-hit outcomes → warning alert."""
    for i in range(5):
        _register_thesis(ledger, f"T{i}")
        _record_outcome(ledger, f"T{i}", "stop_hit")
    alerts = detect_alerts(ledger, consecutive_failure_threshold=5)
    alert_types = [a.alert_type for a in alerts]
    assert "consecutive_failures" in alert_types


def test_detect_alerts_low_cumulative_hit_rate(ledger: TrialLedger) -> None:
    """After 20 outcomes with <30% hit rate → critical alert."""
    # 20 outcomes: 5 hits, 15 fails = 25% hit rate < 30%
    for i in range(20):
        _register_thesis(ledger, f"T{i}")
        reason = "target_hit" if i < 5 else "stop_hit"
        _record_outcome(ledger, f"T{i}", reason)
    alerts = detect_alerts(
        ledger, cumulative_hit_rate_threshold=0.30, cumulative_n_outcomes_threshold=20
    )
    critical_alerts = [a for a in alerts if a.severity == "critical"]
    assert any(a.alert_type == "low_cumulative_hit_rate" for a in critical_alerts)


def test_detect_alerts_does_not_trigger_below_sample_threshold(ledger: TrialLedger) -> None:
    """5 outcomes with low hit rate should NOT trigger cumulative alert (need 20)."""
    for i in range(5):
        _register_thesis(ledger, f"T{i}")
        _record_outcome(ledger, f"T{i}", "stop_hit")
    alerts = detect_alerts(ledger, cumulative_n_outcomes_threshold=20)
    # No cumulative alert (sample too small)
    assert not any(a.alert_type == "low_cumulative_hit_rate" for a in alerts)


def test_detect_alerts_sorts_by_severity_critical_first(ledger: TrialLedger) -> None:
    """Critical alerts come before warnings."""
    for i in range(25):
        _register_thesis(ledger, f"T{i}")
        reason = "target_hit" if i < 5 else "stop_hit"
        _record_outcome(ledger, f"T{i}", reason)
    alerts = detect_alerts(
        ledger,
        consecutive_failure_threshold=5,
        cumulative_hit_rate_threshold=0.30,
        cumulative_n_outcomes_threshold=20,
    )
    # Should have at least one critical (low_cumulative_hit_rate) and one warning (consecutive_failures)
    severities = [a.severity for a in alerts]
    # Critical alerts should appear before warning
    if "critical" in severities and "warning" in severities:
        assert severities.index("critical") < severities.index("warning")


def test_generate_alert_report_returns_markdown_string(ledger: TrialLedger) -> None:
    _register_thesis(ledger, "T1")
    _record_outcome(ledger, "T1", "target_hit", pnl_pct=0.20)
    report = generate_alert_report(ledger)
    assert isinstance(report, str)
    assert "Trial Ledger Alert Report" in report
    assert "Cumulative hit rate" in report
    assert "Meta-kill" in report


def test_generate_alert_report_includes_alerts_section(ledger: TrialLedger) -> None:
    """When alerts are triggered, the report includes them."""
    for i in range(5):
        _register_thesis(ledger, f"T{i}")
        _record_outcome(ledger, f"T{i}", "stop_hit")
    report = generate_alert_report(ledger, consecutive_failure_threshold=5)
    assert "consecutive_failures" in report
