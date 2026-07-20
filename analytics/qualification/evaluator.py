"""Fail-closed evaluator for the M31 historical replay gate."""

from __future__ import annotations

from statistics import median

import numpy as np

from analytics.qualification.models import (
    GateDecision,
    QualificationEvidence,
    QualificationReport,
    QualificationSummary,
    QualificationThresholds,
    ReplayObservation,
    ReplayPeriod,
    ReplayVariant,
)
from analytics.qualification.statistics import bootstrap_luck_p_value


def build_qualification_report(
    *,
    periods: list[ReplayPeriod],
    expected_variants: list[ReplayVariant],
    observations: list[ReplayObservation],
    evidence: QualificationEvidence,
    thresholds: QualificationThresholds,
    selection_blockers: list[str] | None = None,
) -> QualificationReport:
    """Evaluate coverage, authority evidence, and economic thresholds."""
    executed_variants = sorted({observation.variant_name for observation in observations})
    observed_regimes = {period.regime for period in periods}
    required_regimes = set(thresholds.required_regimes)
    missing_regimes = sorted(regime.value for regime in required_regimes - observed_regimes)
    expected_variant_names = {variant.name for variant in expected_variants}
    missing_variants = sorted(expected_variant_names - set(executed_variants))

    blockers = list(selection_blockers or [])
    if missing_regimes:
        blockers.append(f"Missing required replay regimes: {', '.join(missing_regimes)}")
    if thresholds.require_full_variant_matrix and missing_variants:
        blockers.append(f"Missing replay variants: {', '.join(missing_variants)}")

    evidence_checks = (
        (evidence.selected_before_strategy_execution, "Replay periods were not preregistered."),
        (evidence.point_in_time_data_verified, "Point-in-time data provenance is not verified."),
        (evidence.macro_surprise_data_verified, "Macro surprise evidence is not verified."),
        (evidence.prop_profile_certified, "The replay prop-rule profile is not certified."),
        (
            evidence.qualification_engine_certified,
            "The event-driven qualification engine is not certified.",
        ),
        (evidence.prop_rule_replay_exercised, "Prop-rule replay was not exercised."),
        (evidence.risk_gate_exercised, "The mandatory order risk gate was not exercised."),
        (evidence.oms_exercised, "The authoritative OMS was not exercised."),
        (evidence.ledger_reconciled, "The ledger was not reconciled after replay."),
        (
            evidence.intelligence_variants_executed,
            "Eliza, debate, and Fund Manager variants were not executed end-to-end.",
        ),
        (evidence.intelligence_artifacts_verified, "Intelligence artifacts are not verified."),
        (evidence.economic_parity_verified, "Economic parity is not verified."),
    )
    blockers.extend(message for passed, message in evidence_checks if not passed)

    if observations and any(
        observation.metrics.decision_latency_ms_p95 is None for observation in observations
    ):
        blockers.append("Decision latency evidence is incomplete.")
    if observations and any(
        not observation.metrics.factor_attribution for observation in observations
    ):
        blockers.append("Factor attribution evidence is incomplete.")
    if observations and any(
        observation.metrics.luck_p_value is None for observation in observations
    ):
        blockers.append("Luck-versus-skill evidence is incomplete.")
    if not observations:
        blockers.append("No replay observations were produced.")

    summary = _summarize(periods, expected_variants, executed_variants, observations)
    if evidence.risk_gate_exercised and summary.risk_checks == 0:
        blockers.append("Risk-gate evidence has no recorded checks.")
    if evidence.prop_rule_replay_exercised and summary.rule_evaluations == 0:
        blockers.append("Prop-rule evidence has no recorded evaluations.")
    if evidence.oms_exercised and summary.orders_persisted == 0:
        blockers.append("OMS evidence has no persisted orders.")
    if evidence.ledger_reconciled and summary.ledger_entries == 0:
        blockers.append("Ledger evidence has no recorded entries.")
    if evidence.ledger_reconciled and (
        summary.reconciliation_runs != len(observations)
        or summary.reconciliation_mismatches > 0
        or summary.unflattened_slices > 0
    ):
        blockers.append("Ledger reconciliation evidence is incomplete or not clean.")
    if evidence.prop_profile_certified and any(
        item.execution_evidence is None or not item.execution_evidence.profile_certified
        for item in observations
    ):
        blockers.append("Certified prop-profile evidence is missing from replay slices.")
    if evidence.economic_parity_verified and any(
        item.execution_evidence is None or not item.execution_evidence.economic_parity_verified
        for item in observations
    ):
        blockers.append("Economic parity evidence is missing from replay slices.")
    if evidence.intelligence_artifacts_verified and any(
        item.execution_evidence is None or item.execution_evidence.intelligence_artifact is None
        for item in observations
    ):
        blockers.append("Intelligence artifact evidence is missing from replay slices.")
    failures = _threshold_failures(summary, thresholds)
    if blockers:
        decision = GateDecision.BLOCKED
        reasons = _deduplicate(blockers + failures)
    elif failures:
        decision = GateDecision.REJECTED
        reasons = failures
    else:
        decision = GateDecision.APPROVED
        reasons = ["All M31 coverage, authority, and threshold checks passed."]

    return QualificationReport(
        decision=decision,
        reasons=reasons,
        thresholds=thresholds,
        evidence=evidence,
        periods=periods,
        expected_variants=expected_variants,
        executed_variants=executed_variants,
        observations=observations,
        summary=summary,
    )


def _summarize(
    periods: list[ReplayPeriod],
    expected_variants: list[ReplayVariant],
    executed_variants: list[str],
    observations: list[ReplayObservation],
) -> QualificationSummary:
    metrics = [observation.metrics for observation in observations]
    execution = [
        observation.execution_evidence
        for observation in observations
        if observation.execution_evidence is not None
    ]
    pooled_returns = np.asarray(
        [value for observation in observations for value in observation.returns_for_luck_test],
        dtype=float,
    )
    pooled_luck_p_value = bootstrap_luck_p_value(pooled_returns)
    return QualificationSummary(
        period_count=len(periods),
        expected_variant_count=len(expected_variants),
        executed_variant_count=len(executed_variants),
        observation_count=len(observations),
        median_net_return=_median([metric.net_return for metric in metrics]),
        median_sharpe=_median_optional([metric.sharpe_ratio for metric in metrics]),
        median_sortino=_median_optional([metric.sortino_ratio for metric in metrics]),
        median_calmar=_median_optional([metric.calmar_ratio for metric in metrics]),
        worst_drawdown=max((metric.max_drawdown for metric in metrics), default=None),
        hard_breaches=sum(metric.hard_breaches for metric in metrics),
        median_execution_cost_ratio=_median([metric.execution_cost_ratio for metric in metrics]),
        worst_luck_p_value=max(
            (metric.luck_p_value for metric in metrics if metric.luck_p_value is not None),
            default=None,
        ),
        pooled_luck_p_value=pooled_luck_p_value,
        worst_decision_latency_ms_p95=max(
            (
                metric.decision_latency_ms_p95
                for metric in metrics
                if metric.decision_latency_ms_p95 is not None
            ),
            default=None,
        ),
        risk_checks=sum(item.risk_checks for item in execution),
        rule_evaluations=sum(item.rule_evaluations for item in execution),
        orders_persisted=sum(item.orders_persisted for item in execution),
        fills_recorded=sum(item.fills_recorded for item in execution),
        ledger_entries=sum(item.ledger_entries for item in execution),
        reconciliation_runs=sum(item.reconciliation_runs for item in execution),
        reconciliation_mismatches=sum(item.reconciliation_mismatches for item in execution),
        unflattened_slices=sum(not item.flattened for item in execution),
    )


def _threshold_failures(
    summary: QualificationSummary, thresholds: QualificationThresholds
) -> list[str]:
    checks: tuple[tuple[float | int | None, str, str, float | int], ...] = (
        (
            summary.median_net_return,
            "minimum",
            "Median net return",
            thresholds.min_median_net_return,
        ),
        (summary.median_sharpe, "minimum", "Median Sharpe", thresholds.min_median_sharpe),
        (summary.median_sortino, "minimum", "Median Sortino", thresholds.min_median_sortino),
        (summary.median_calmar, "minimum", "Median Calmar", thresholds.min_median_calmar),
        (summary.worst_drawdown, "maximum", "Worst drawdown", thresholds.max_worst_drawdown),
        (summary.hard_breaches, "maximum", "Hard breaches", thresholds.max_hard_breaches),
        (
            summary.median_execution_cost_ratio,
            "maximum",
            "Median execution cost ratio",
            thresholds.max_median_execution_cost_ratio,
        ),
        (
            summary.pooled_luck_p_value
            if summary.pooled_luck_p_value is not None
            else summary.worst_luck_p_value,
            "maximum",
            "Pooled luck p-value",
            thresholds.max_luck_p_value,
        ),
        (
            summary.worst_decision_latency_ms_p95,
            "maximum",
            "Worst decision latency p95",
            thresholds.max_decision_latency_ms_p95,
        ),
    )
    failures: list[str] = []
    for actual, direction, label, threshold in checks:
        if actual is None:
            continue
        failed = actual < threshold if direction == "minimum" else actual > threshold
        if failed:
            failures.append(f"{label} {actual:.6g} fails {direction} threshold {threshold:.6g}.")
    return failures


def _median(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _median_optional(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return _median(present)


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
