"""Historical replay qualification for capability gate M31."""

from analytics.qualification.discovery import DiscoveryReplayRunner
from analytics.qualification.evaluator import build_qualification_report
from analytics.qualification.execution import EventDrivenQualificationRunner
from analytics.qualification.intelligence import build_offline_intelligence_artifact
from analytics.qualification.models import (
    ExecutionEvidence,
    FundManagerVariant,
    GateDecision,
    IntelligenceArtifact,
    MacroSurpriseEvent,
    QualificationEvidence,
    QualificationReport,
    QualificationThresholds,
    ReplayMetrics,
    ReplayObservation,
    ReplayPeriod,
    ReplayRegime,
    ReplayVariant,
)
from analytics.qualification.periods import PeriodSelection, select_replay_periods, slice_period
from analytics.qualification.report import render_markdown, write_report

__all__ = [
    "DiscoveryReplayRunner",
    "EventDrivenQualificationRunner",
    "ExecutionEvidence",
    "FundManagerVariant",
    "GateDecision",
    "IntelligenceArtifact",
    "MacroSurpriseEvent",
    "PeriodSelection",
    "QualificationEvidence",
    "QualificationReport",
    "QualificationThresholds",
    "ReplayMetrics",
    "ReplayObservation",
    "ReplayPeriod",
    "ReplayRegime",
    "ReplayVariant",
    "build_offline_intelligence_artifact",
    "build_qualification_report",
    "render_markdown",
    "select_replay_periods",
    "slice_period",
    "write_report",
]
