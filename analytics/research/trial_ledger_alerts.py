"""BL-506b — Trial ledger alert triggers + cumulative hit-rate report.

Extends ``analytics/research/trial_ledger.py`` with:
- ``cumulative_hit_rate_over_time``: hit rate computed at each outcome point
- ``alert_trigger``: detect 5 consecutive failed theses → flag process review
- ``rolling_hit_rate``: rolling-window hit rate (e.g. last 10 outcomes)
- ``generate_alert_report``: markdown report with red flags

Per ADR-019: meta-kill rule is "after 50 real theses if cumulative hit rate < 30%,
re-screening with more stringent criteria". Alert trigger at 5 consecutive failures
gives an early warning before the meta-kill.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

from analytics.research.trial_ledger import TrialLedger


@dataclass(frozen=True)
class AlertTrigger:
    """One alert triggered by the trial ledger.

    Attributes
    ----------
    alert_type : str
        One of: 'consecutive_failures', 'low_cumulative_hit_rate',
        'low_rolling_hit_rate', 'high_max_consecutive_losses'.
    message : str
        Human-readable description.
    severity : str
        'warning' or 'critical'.
    value : float | int
        The metric value that triggered the alert.
    threshold : float | int
        The threshold that was violated.
    triggered_at : str
        ISO timestamp when the alert was detected.
    """

    alert_type: str
    message: str
    severity: str
    value: float | int
    threshold: float | int
    triggered_at: str


@dataclass(frozen=True)
class HitRateOverTime:
    """Cumulative hit rate at each outcome point.

    Attributes
    ----------
    date : str
        ISO date of the outcome.
    cumulative_hit_rate : float
        Hit rate up to and including this outcome.
    cumulative_n_outcomes : int
        Number of outcomes recorded up to this point.
    """

    date: str
    cumulative_hit_rate: float
    cumulative_n_outcomes: int


def cumulative_hit_rate_over_time(
    ledger: TrialLedger, *, window_size: int = 10
) -> list[HitRateOverTime]:
    """Return cumulative hit rate at each outcome point.

    Parameters
    ----------
    ledger : TrialLedger
        The trial ledger to query.
    window_size : int
        Window size for rolling hit rate (default 10).

    Returns
    -------
    list[HitRateOverTime]
        One entry per outcome, in chronological order.
    """
    outcomes = ledger.list_outcomes()
    if not outcomes:
        return []

    # Sort by closed_at
    outcomes.sort(key=lambda r: r["closed_at"])
    series: list[HitRateOverTime] = []
    n_hits = 0
    n_total = 0
    for row in outcomes:
        n_total += 1
        if row["exit_reason"] == "target_hit":
            n_hits += 1
        series.append(
            HitRateOverTime(
                date=str(row["closed_at"]),
                cumulative_hit_rate=n_hits / n_total,
                cumulative_n_outcomes=n_total,
            )
        )
    return series


def rolling_hit_rate(ledger: TrialLedger, *, window_size: int = 10) -> list[HitRateOverTime]:
    """Return rolling-window hit rate (last N outcomes).

    Parameters
    ----------
    ledger : TrialLedger
        The trial ledger to query.
    window_size : int
        Window size (default 10; the last 10 outcomes).

    Returns
    -------
    list[HitRateOverTime]
        One entry per outcome starting from the (window_size)-th outcome.
    """
    outcomes = ledger.list_outcomes()
    if not outcomes:
        return []
    outcomes.sort(key=lambda r: r["closed_at"])

    series: list[HitRateOverTime] = []
    window: deque[int] = deque(maxlen=window_size)  # 1 = hit, 0 = miss
    n_total = 0
    for row in outcomes:
        n_total += 1
        is_hit = 1 if row["exit_reason"] == "target_hit" else 0
        window.append(is_hit)
        if len(window) == window_size:
            series.append(
                HitRateOverTime(
                    date=str(row["closed_at"]),
                    cumulative_hit_rate=sum(window) / window_size,
                    cumulative_n_outcomes=n_total,
                )
            )
    return series


def max_consecutive_failures(ledger: TrialLedger) -> int:
    """Return the maximum number of consecutive non-hit outcomes.

    A "failure" is any outcome where exit_reason != 'target_hit'
    (i.e., stop_hit, time_stop, invalidation, manual_close).
    """
    outcomes = ledger.list_outcomes()
    if not outcomes:
        return 0
    outcomes.sort(key=lambda r: r["closed_at"])

    max_streak = 0
    current_streak = 0
    for row in outcomes:
        if row["exit_reason"] != "target_hit":
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    return max_streak


def detect_alerts(
    ledger: TrialLedger,
    *,
    consecutive_failure_threshold: int = 5,
    cumulative_hit_rate_threshold: float = 0.30,
    cumulative_n_outcomes_threshold: int = 20,
    rolling_hit_rate_threshold: float = 0.30,
    rolling_window_size: int = 10,
    max_consecutive_loss_threshold: int = 10,
) -> list[AlertTrigger]:
    """Detect alert triggers in the trial ledger.

    Per ADR-019 §3 (meta-kill rule): "if after 50 real theses cumulative
    hit rate < 30%, process is broken". This function detects early-warning
    signals before the meta-kill triggers.

    Parameters
    ----------
    ledger : TrialLedger
        The trial ledger to query.
    consecutive_failure_threshold : int
        Number of consecutive failures that triggers an alert (default 5).
    cumulative_hit_rate_threshold : float
        Cumulative hit rate below which (after N outcomes) the alert
        triggers (default 0.30 per ADR-019 meta-kill).
    cumulative_n_outcomes_threshold : int
        Minimum number of outcomes before the cumulative alert triggers
        (default 20; need a sample size to be meaningful).
    rolling_hit_rate_threshold : float
        Rolling-window hit rate below which the alert triggers (default 0.30).
    rolling_window_size : int
        Window size for the rolling hit rate (default 10).
    max_consecutive_loss_threshold : int
        Max consecutive losses (any non-hit outcome) before alert (default 10).

    Returns
    -------
    list[AlertTrigger]
        List of alerts detected, ordered by severity (critical first).
    """
    alerts: list[AlertTrigger] = []
    now = datetime.now(UTC).isoformat()

    # 1. Consecutive failures alert
    max_consec = max_consecutive_failures(ledger)
    if max_consec >= consecutive_failure_threshold:
        alerts.append(
            AlertTrigger(
                alert_type="consecutive_failures",
                message=(
                    f"{max_consec} consecutive non-hit outcomes — process review "
                    f"recommended. Threshold: {consecutive_failure_threshold}."
                ),
                severity="warning",
                value=max_consec,
                threshold=consecutive_failure_threshold,
                triggered_at=now,
            )
        )

    # 2. Cumulative hit rate alert (only if enough outcomes)
    hr = ledger.hit_rate()
    n_with_outcome = hr["n_with_outcome"]
    cum_hit_rate = hr["hit_rate"]
    if (
        n_with_outcome >= cumulative_n_outcomes_threshold
        and cum_hit_rate < cumulative_hit_rate_threshold
    ):
        alerts.append(
            AlertTrigger(
                alert_type="low_cumulative_hit_rate",
                message=(
                    f"Cumulative hit rate {cum_hit_rate:.0%} after {n_with_outcome} "
                    f"outcomes is below {cumulative_hit_rate_threshold:.0%} — "
                    f"meta-kill rule (ADR-019) approaching."
                ),
                severity="critical",
                value=cum_hit_rate,
                threshold=cumulative_hit_rate_threshold,
                triggered_at=now,
            )
        )

    # 3. Rolling hit rate alert (only if enough outcomes for a window)
    rolling_series = rolling_hit_rate(ledger, window_size=rolling_window_size)
    if rolling_series:
        latest_rolling = rolling_series[-1]
        if latest_rolling.cumulative_hit_rate < rolling_hit_rate_threshold:
            alerts.append(
                AlertTrigger(
                    alert_type="low_rolling_hit_rate",
                    message=(
                        f"Rolling hit rate (last {rolling_window_size} outcomes) "
                        f"{latest_rolling.cumulative_hit_rate:.0%} is below "
                        f"{rolling_hit_rate_threshold:.0%} — recent process "
                        f"degradation."
                    ),
                    severity="warning",
                    value=latest_rolling.cumulative_hit_rate,
                    threshold=rolling_hit_rate_threshold,
                    triggered_at=now,
                )
            )

    # 4. Max consecutive losses alert
    if max_consec >= max_consecutive_loss_threshold:
        alerts.append(
            AlertTrigger(
                alert_type="high_max_consecutive_losses",
                message=(
                    f"{max_consec} consecutive losses — extreme drawdown risk. "
                    f"Threshold: {max_consecutive_loss_threshold}."
                ),
                severity="critical",
                value=max_consec,
                threshold=max_consecutive_loss_threshold,
                triggered_at=now,
            )
        )

    # Sort by severity (critical first, then warning)
    alerts.sort(key=lambda a: 0 if a.severity == "critical" else 1)
    return alerts


def generate_alert_report(
    ledger: TrialLedger,
    *,
    consecutive_failure_threshold: int = 5,
    cumulative_hit_rate_threshold: float = 0.30,
    cumulative_n_outcomes_threshold: int = 20,
    rolling_hit_rate_threshold: float = 0.30,
    rolling_window_size: int = 10,
    max_consecutive_loss_threshold: int = 10,
) -> str:
    """Generate a markdown alert report.

    Returns
    -------
    str
        Markdown report with alerts + cumulative hit rate time series +
        rolling hit rate time series.
    """
    alerts = detect_alerts(
        ledger,
        consecutive_failure_threshold=consecutive_failure_threshold,
        cumulative_hit_rate_threshold=cumulative_hit_rate_threshold,
        cumulative_n_outcomes_threshold=cumulative_n_outcomes_threshold,
        rolling_hit_rate_threshold=rolling_hit_rate_threshold,
        rolling_window_size=rolling_window_size,
        max_consecutive_loss_threshold=max_consecutive_loss_threshold,
    )

    cum_series = cumulative_hit_rate_over_time(ledger)
    roll_series = rolling_hit_rate(ledger, window_size=rolling_window_size)

    lines: list[str] = []
    lines.append("# Trial Ledger Alert Report (BL-506b)\n\n")
    lines.append(f"**Generated**: {datetime.now(UTC).isoformat()}\n\n")

    hr = ledger.hit_rate()
    lines.append("## Summary\n\n")
    lines.append(f"- Theses registered: {hr['n_theses']}\n")
    lines.append(f"- Outcomes recorded: {hr['n_with_outcome']}\n")
    lines.append(f"- Cumulative hit rate: {hr['hit_rate']:.1%}\n")
    lines.append(f"- Target hit: {hr['n_target_hit']}\n")
    lines.append(f"- Stop hit: {hr['n_stop_hit']}\n")
    lines.append(f"- Time stop: {hr['n_time_stop']}\n")
    lines.append(f"- Invalidation: {hr['n_invalidation']}\n")
    lines.append(f"- Manual close: {hr['n_manual_close']}\n")
    lines.append(f"- Avg P&L pct: {hr['avg_pnl_pct']:.2%}\n")
    lines.append(f"- Max consecutive failures: {max_consecutive_failures(ledger)}\n\n")

    lines.append("## Alerts\n\n")
    if not alerts:
        lines.append("✅ No alerts triggered. Process is within thresholds.\n\n")
    else:
        for alert in alerts:
            icon = "🚨" if alert.severity == "critical" else "⚠️"
            lines.append(f"{icon} **{alert.alert_type}** ({alert.severity}):\n")
            lines.append(f"  - {alert.message}\n")
            lines.append(f"  - Value: {alert.value}, threshold: {alert.threshold}\n\n")

    lines.append("## Cumulative hit rate over time\n\n")
    lines.append("| Date | Outcomes | Hit rate |\n|---|---|---|\n")
    for point in cum_series[-20:]:  # last 20 to keep table readable
        lines.append(
            f"| {point.date} | {point.cumulative_n_outcomes} | {point.cumulative_hit_rate:.1%} |\n"
        )
    if len(cum_series) > 20:
        lines.append(f"\n*...showing last 20 of {len(cum_series)} outcomes*\n\n")

    if roll_series:
        lines.append(f"## Rolling hit rate (window={rolling_window_size})\n\n")
        lines.append("| Date | Window outcomes | Rolling hit rate |\n|---|---|---|\n")
        for point in roll_series[-10:]:
            lines.append(
                f"| {point.date} | {point.cumulative_n_outcomes} | {point.cumulative_hit_rate:.1%} |\n"
            )
        lines.append("\n")

    lines.append("## ADR-019 meta-kill rule reminder\n\n")
    lines.append(
        'Per ADR-019 §3: "if after 50 real theses the cumulative hit rate < 30%, the process is broken."\n'
    )
    lines.append(f"Current: {hr['n_with_outcome']}/{50} outcomes toward meta-kill threshold.\n")
    if hr["n_with_outcome"] >= 50 and hr["hit_rate"] < 0.30:
        lines.append(
            "🚨 **META-KILL TRIGGERED**: process is broken. Action required: re-screen with more stringent criteria.\n"
        )
    else:
        lines.append("✅ Meta-kill not yet triggered.\n")

    return "".join(lines)


__all__: list[str] = [
    "AlertTrigger",
    "HitRateOverTime",
    "cumulative_hit_rate_over_time",
    "detect_alerts",
    "generate_alert_report",
    "max_consecutive_failures",
    "rolling_hit_rate",
]
