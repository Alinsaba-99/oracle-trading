"""Tests for the fail-closed M31 gate evaluator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from analytics.qualification.evaluator import build_qualification_report
from analytics.qualification.models import (
    ExecutionEvidence,
    GateDecision,
    IntelligenceArtifact,
    QualificationEvidence,
    QualificationThresholds,
    ReplayMetrics,
    ReplayObservation,
    ReplayPeriod,
    ReplayRegime,
    ReplayVariant,
)


def _periods() -> list[ReplayPeriod]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        ReplayPeriod(
            name=regime.value,
            regime=regime,
            start=start,
            end=start + timedelta(days=30),
            selection_metric="test",
            selection_score=1.0,
        )
        for regime in ReplayRegime
    ]


def _metrics(*, hard_breaches: int = 0) -> ReplayMetrics:
    return ReplayMetrics(
        net_return=0.02,
        sharpe_ratio=1.2,
        sortino_ratio=1.4,
        calmar_ratio=0.8,
        max_drawdown=0.02,
        hard_breaches=hard_breaches,
        soft_breaches=0,
        turnover=1.0,
        execution_cost=10.0,
        execution_cost_ratio=0.001,
        model_cost_usd=1.0,
        decision_latency_ms_p95=50.0,
        factor_attribution={"market_beta": 0.4},
        luck_p_value=0.05,
        total_trades=5,
        bars=40,
        engine_runtime_ms=100.0,
    )


def _execution_evidence() -> ExecutionEvidence:
    return ExecutionEvidence(
        risk_checks=1,
        risk_approvals=1,
        rule_evaluations=40,
        orders_persisted=2,
        fills_recorded=2,
        ledger_entries=4,
        reconciliation_runs=1,
        reconciliation_clean=True,
        flattened=True,
        profile_key="certified/test/v1",
        profile_certified=True,
        economic_parity_verified=True,
        independent_cash_delta=100.0,
        ledger_cash_delta=100.0,
        intelligence_artifact=IntelligenceArtifact(
            variant_name="test",
            period_name="test",
            source="test",
            artifact_sha256="a" * 64,
            fund_manager_observations=1,
        ),
    )


def _evidence(*, certified: bool = True) -> QualificationEvidence:
    return QualificationEvidence(
        discovery_engine="vectorized",
        qualification_engine="event-driven",
        qualification_engine_certified=certified,
        selected_before_strategy_execution=True,
        point_in_time_data_verified=True,
        macro_surprise_data_verified=True,
        prop_profile_certified=True,
        prop_rule_replay_exercised=True,
        risk_gate_exercised=True,
        oms_exercised=True,
        ledger_reconciled=True,
        intelligence_variants_executed=True,
        economic_parity_verified=True,
        intelligence_artifacts_verified=True,
        data_hash="data",
        config_hash="config",
        git_commit="commit",
    )


def _observations(*, hard_breaches: int = 0) -> list[ReplayObservation]:
    return [
        ReplayObservation(
            period_name=period.name,
            regime=period.regime,
            variant_name=variant.name,
            engine="event-driven",
            component_path="risk-oms-ledger",
            metrics=_metrics(hard_breaches=hard_breaches),
            execution_evidence=_execution_evidence(),
        )
        for period in _periods()
        for variant in ReplayVariant.factorial()
    ]


def test_approves_only_complete_evidence_and_metrics() -> None:
    report = build_qualification_report(
        periods=_periods(),
        expected_variants=ReplayVariant.factorial(),
        observations=_observations(),
        evidence=_evidence(),
        thresholds=QualificationThresholds(),
    )

    assert report.decision == GateDecision.APPROVED
    assert report.summary.observation_count == 48


def test_blocks_uncertified_engine() -> None:
    report = build_qualification_report(
        periods=_periods(),
        expected_variants=ReplayVariant.factorial(),
        observations=_observations(),
        evidence=_evidence(certified=False),
        thresholds=QualificationThresholds(),
    )

    assert report.decision == GateDecision.BLOCKED
    assert any("not certified" in reason for reason in report.reasons)


def test_rejects_hard_rule_breach_after_evidence_is_complete() -> None:
    report = build_qualification_report(
        periods=_periods(),
        expected_variants=ReplayVariant.factorial(),
        observations=_observations(hard_breaches=1),
        evidence=_evidence(),
        thresholds=QualificationThresholds(),
    )

    assert report.decision == GateDecision.REJECTED
    assert any("Hard breaches" in reason for reason in report.reasons)


def test_blocks_incomplete_variant_matrix() -> None:
    report = build_qualification_report(
        periods=_periods(),
        expected_variants=ReplayVariant.factorial(),
        observations=_observations()[:6],
        evidence=_evidence(),
        thresholds=QualificationThresholds(),
    )

    assert report.decision == GateDecision.BLOCKED
    assert any("Missing replay variants" in reason for reason in report.reasons)


def test_blocks_unsubstantiated_execution_evidence() -> None:
    observations = _observations()
    observations[0] = observations[0].model_copy(update={"execution_evidence": None})
    report = build_qualification_report(
        periods=_periods(),
        expected_variants=ReplayVariant.factorial(),
        observations=observations,
        evidence=_evidence(),
        thresholds=QualificationThresholds(),
    )

    assert report.decision == GateDecision.BLOCKED
    assert any("reconciliation evidence" in reason.lower() for reason in report.reasons)
