"""Deterministic offline intelligence artifacts used by M31 replay."""

from __future__ import annotations

import hashlib
import json

from analytics.qualification.models import IntelligenceArtifact, ReplayPeriod, ReplayVariant


def build_offline_intelligence_artifact(
    period: ReplayPeriod, variant: ReplayVariant
) -> IntelligenceArtifact:
    """Build a causal, reproducible artifact without external model calls.

    M31 needs every factorial branch to be exercised, but a historical replay
    must not invent live Eliza or LLM output.  This artifact implements the
    published contract (scout observations, debate result, and fund-manager
    decision) from preregistered metadata and records a content hash.
    """
    payload = {
        "period": period.model_dump(mode="json"),
        "variant": variant.model_dump(mode="json"),
        "policy": "causal-pass-through-v1",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return IntelligenceArtifact(
        variant_name=variant.name,
        period_name=period.name,
        source="offline-eliza-compatible-causal-v1",
        artifact_sha256=digest,
        scout_observations=2 if variant.eliza_scouts_enabled else 0,
        debate_observations=2 if variant.debate_enabled else 0,
        fund_manager_observations=1,
        model_cost_usd=0.0,
        causal=True,
    )
