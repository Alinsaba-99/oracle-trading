"""Models for deterministic historical replay qualification."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReplayRegime(StrEnum):
    """Required market regimes for the M31 replay gate."""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LIQUIDITY_SHOCK = "liquidity_shock"
    MACRO_SURPRISE = "macro_surprise"


class FundManagerVariant(StrEnum):
    """Fund Manager implementation exercised by a replay variant."""

    BASELINE = "baseline"
    CHALLENGER = "challenger"


class GateDecision(StrEnum):
    """M31 gate outcome."""

    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class MacroSurpriseEvent(BaseModel):
    """Point-in-time macro release with actual and consensus values."""

    model_config = ConfigDict(frozen=True)

    event_time: datetime
    available_at: datetime
    indicator: str
    actual: float
    consensus: float
    source: str
    source_sha256: str | None = None
    retrieved_at: datetime | None = None
    raw_actual: str | None = None
    raw_consensus: str | None = None
    raw_previous: str | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if self.available_at < self.event_time:
            raise ValueError("available_at cannot precede event_time")
        if not self.source.strip():
            raise ValueError("source is required for macro surprise evidence")
        if self.source_sha256 is not None and len(self.source_sha256) != 64:
            raise ValueError("source_sha256 must be a SHA-256 hex digest")
        return self

    @property
    def absolute_surprise(self) -> float:
        """Return the absolute actual-versus-consensus surprise."""
        return abs(self.actual - self.consensus)


class ReplayPeriod(BaseModel):
    """Immutable historical period selected before strategy execution."""

    model_config = ConfigDict(frozen=True)

    name: str
    regime: ReplayRegime
    start: datetime
    end: datetime
    selection_metric: str
    selection_score: float
    source: str = "oracle-regime-selector-v1"
    event_label: str | None = None
    available_at: datetime | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.end < self.start:
            raise ValueError("replay period end cannot precede start")
        return self


class ReplayVariant(BaseModel):
    """Factorial intelligence configuration required by M31."""

    model_config = ConfigDict(frozen=True)

    name: str
    eliza_scouts_enabled: bool
    debate_enabled: bool
    fund_manager: FundManagerVariant

    @classmethod
    def factorial(cls) -> list[ReplayVariant]:
        """Return the deterministic 2x2x2 M31 variant matrix."""
        variants: list[ReplayVariant] = []
        for scouts_enabled in (False, True):
            for debate_enabled in (False, True):
                for fund_manager in FundManagerVariant:
                    scouts = "on" if scouts_enabled else "off"
                    debate = "on" if debate_enabled else "off"
                    variants.append(
                        cls(
                            name=(
                                f"scouts-{scouts}__debate-{debate}__"
                                f"fund-manager-{fund_manager.value}"
                            ),
                            eliza_scouts_enabled=scouts_enabled,
                            debate_enabled=debate_enabled,
                            fund_manager=fund_manager,
                        )
                    )
        return variants

    @classmethod
    def control(cls) -> ReplayVariant:
        """Return the signal-only discovery control configuration."""
        return cls.factorial()[0]


class ReplayMetrics(BaseModel):
    """Metrics captured for one period and one replay variant."""

    net_return: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    max_drawdown: float
    hard_breaches: int = Field(ge=0)
    soft_breaches: int = Field(ge=0)
    turnover: float = Field(ge=0)
    execution_cost: float = Field(ge=0)
    execution_cost_ratio: float = Field(ge=0)
    model_cost_usd: float = Field(ge=0)
    decision_latency_ms_p95: float | None = Field(default=None, ge=0)
    factor_attribution: dict[str, float] = Field(default_factory=dict)
    luck_p_value: float | None = Field(default=None, ge=0, le=1)
    total_trades: int = Field(ge=0)
    bars: int = Field(ge=0)
    engine_runtime_ms: float = Field(ge=0)


class IntelligenceArtifact(BaseModel):
    """Deterministic, hashed offline artifact for one factorial variant."""

    model_config = ConfigDict(frozen=True)

    variant_name: str
    period_name: str
    source: str
    artifact_sha256: str
    scout_observations: int = Field(default=0, ge=0)
    debate_observations: int = Field(default=0, ge=0)
    fund_manager_observations: int = Field(default=0, ge=0)
    model_cost_usd: float = Field(default=0.0, ge=0)
    causal: bool = True


class ExecutionEvidence(BaseModel):
    """Auditable execution-path counters for one replay observation."""

    risk_checks: int = Field(default=0, ge=0)
    risk_approvals: int = Field(default=0, ge=0)
    risk_rejections: int = Field(default=0, ge=0)
    rule_evaluations: int = Field(default=0, ge=0)
    orders_persisted: int = Field(default=0, ge=0)
    fills_recorded: int = Field(default=0, ge=0)
    ledger_entries: int = Field(default=0, ge=0)
    reconciliation_runs: int = Field(default=0, ge=0)
    reconciliation_mismatches: int = Field(default=0, ge=0)
    reconciliation_clean: bool = False
    flattened: bool = False
    final_position_quantity: float = 0.0
    simulated_execution_latency_ms_p95: float | None = Field(default=None, ge=0)
    profile_key: str
    profile_certified: bool = False
    economic_parity_verified: bool = False
    independent_cash_delta: float | None = None
    ledger_cash_delta: float | None = None
    intelligence_artifact: IntelligenceArtifact | None = None


class ReplayObservation(BaseModel):
    """One executed replay slice and its limitations."""

    period_name: str
    regime: ReplayRegime
    variant_name: str
    engine: str
    component_path: str
    metrics: ReplayMetrics
    execution_evidence: ExecutionEvidence | None = None
    warnings: list[str] = Field(default_factory=list)
    returns_for_luck_test: list[float] = Field(default_factory=list, exclude=True)


class QualificationEvidence(BaseModel):
    """Evidence required before the historical replay gate can pass."""

    discovery_engine: str
    qualification_engine: str | None = None
    qualification_engine_certified: bool = False
    selected_before_strategy_execution: bool = False
    point_in_time_data_verified: bool = False
    macro_surprise_data_verified: bool = False
    prop_profile_certified: bool = False
    prop_rule_replay_exercised: bool = False
    risk_gate_exercised: bool = False
    oms_exercised: bool = False
    ledger_reconciled: bool = False
    intelligence_variants_executed: bool = False
    economic_parity_verified: bool = False
    intelligence_artifacts_verified: bool = False
    luck_test_method: str = "per-slice bootstrap"
    data_hash: str
    config_hash: str
    git_commit: str


class QualificationThresholds(BaseModel):
    """Versioned research thresholds for M31 approval."""

    min_median_net_return: float = 0.0
    min_median_sharpe: float = 0.5
    min_median_sortino: float = 0.5
    min_median_calmar: float = 0.25
    max_worst_drawdown: float = Field(default=0.04, ge=0, le=1)
    max_hard_breaches: int = Field(default=0, ge=0)
    max_median_execution_cost_ratio: float = Field(default=0.01, ge=0)
    max_luck_p_value: float = Field(default=0.10, ge=0, le=1)
    max_decision_latency_ms_p95: float = Field(default=250.0, ge=0)
    required_regimes: tuple[ReplayRegime, ...] = tuple(ReplayRegime)
    require_full_variant_matrix: bool = True


class QualificationSummary(BaseModel):
    """Aggregate metrics used by the gate evaluator."""

    period_count: int
    expected_variant_count: int
    executed_variant_count: int
    observation_count: int
    median_net_return: float | None = None
    median_sharpe: float | None = None
    median_sortino: float | None = None
    median_calmar: float | None = None
    worst_drawdown: float | None = None
    hard_breaches: int = 0
    median_execution_cost_ratio: float | None = None
    worst_luck_p_value: float | None = None
    pooled_luck_p_value: float | None = None
    worst_decision_latency_ms_p95: float | None = None
    risk_checks: int = 0
    rule_evaluations: int = 0
    orders_persisted: int = 0
    fills_recorded: int = 0
    ledger_entries: int = 0
    reconciliation_runs: int = 0
    reconciliation_mismatches: int = 0
    unflattened_slices: int = 0


class QualificationReport(BaseModel):
    """Complete M31 report with decision, evidence, and observations."""

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decision: GateDecision
    reasons: list[str]
    thresholds: QualificationThresholds
    evidence: QualificationEvidence
    periods: list[ReplayPeriod]
    expected_variants: list[ReplayVariant]
    executed_variants: list[str]
    observations: list[ReplayObservation]
    summary: QualificationSummary
