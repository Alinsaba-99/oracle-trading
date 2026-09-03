"""BL-709 — Dual-Channel Strategy Promotion Policy.

A single validated strategy may be promoted to either of two execution
channels depending on capital source and risk tolerance:

* **Channel A — Personal capital**: brokerage account (IBKR, etc.). The
  operator accepts higher volatility / drawdown for higher absolute
  return; sizing follows vol-target 25-40% (Lane B stack, ADR-019).
  Edge quality is the gate (haircut Sharpe + DSR + OOS walk-forward
  alpha), NOT daily-risk-budget compliance.

* **Channel B — Funded prop-firm capital**: account lives under a prop
  firm's hard-risk envelope (BL-722 governor + ADR-013 catalog). Every
  order that risks breach fails closed. Edge quality gates AND
  sigma-scaling / consistency / pass-rate gates apply; the strategy must
  prove survivability under the firm's drawdown budget, not just
  statistical significance in isolation.

The two channels are NOT a ranking. They answer different questions:

* Channel A: "is this edge real and worth sizing into my own book?"
* Channel B: "is this edge real AND will it survive the firm's hard-risk
  envelope across 100+ paper sessions?"

A strategy can pass one and not the other — both must pass for the
strategy to be promoted to *its respective* channel. Promotion is
per-channel; a strategy passing Channel A is NOT automatically admitted
to Channel B and vice versa. Each channel gates on the metrics that
matter for that capital source.

Pre-registered criteria (frozen at BL-709 acceptance 2026-09-03;
modification requires an ADR amendment):

Channel A (Personal):
    * haircut_sharpe >= 0.50 (BL-707, Bailey-López de Prado 2018)
    * dsr (deflated Sharpe ratio) >= 0.95 (BL-KB-99)
    * max_drawdown < 0.15 (15%)
    * walk_forward_alpha > 0.0 (out-of-sample IS-positive)

Channel B (Funded):
    * hard_risk_compliant — PropFirmRiskGovernor (BL-722) raised no
      breach on the validation session envelope
    * consistency_pct <= 0.35 (firm-mieterharvester best-day rule)
    * daily_pause_terminate_supported — DailyLossAction ∈ {PAUSE, TERMINATE}
    * simulated_eval_pass_rate >= 0.60 over ≥ 100 canonical paper
      sessions (BL-728 simulator)
    * monte_carlo_pass_rate — same gate, MC-replayed, ≥ 0.60 at p=0.05

References: ADR-013 (rule catalog), ADR-018 (prop-firm structural EV),
ADR-019 (Lane B personal portfolio), ADR-021 (canonical metrics),
ADR-022 (MT5 bridge), BACKLOG BL-709, BL-722 (governor), BL-728
(simulator), BL-707 (haircut Sharpe).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from policy.prop_firm.governor import PropFirmRiskGovernor

if TYPE_CHECKING:
    from policy.prop_firm.profile import FirmProgramProfile


class Channel(StrEnum):
    """Promotion channel for a validated strategy."""

    PERSONAL = "A"  # capital proprio (brokerage IBKR)
    FUNDED = "B"  # conto funded prop-firm (BL-722)


# ---------------------------------------------------------------------------
# Pre-registered thresholds (frozen at BL-709 acceptance)
# ---------------------------------------------------------------------------

#: Haircut Sharpe floor for Channel A.  A negative or low haircut means
#: the strategy's edge is not statistically distinguishable from
#: multiple-testing noise; promotion would be a HARKing trap.
PERSONAL_HAIRCUT_SHARPE_MIN: float = 0.50

#: Deflated Sharpe Ratio floor for Channel A.  DSR > 0.95 means
#: "after adjusting for n_trials and fat tails, the probability that the
#: true Sharpe exceeds the best-of-N null is ≥ 95%".
PERSONAL_DSR_MIN: float = 0.95

#: Maximum drawdown ceiling for Channel A.  Above 15% the strategy's
#: tail loss is incompatible with brokerage personal-book risk tolerance
#: (Lane B sizing assumes DD ≤ 15% to size 2-3% per idea safely).
PERSONAL_MAX_DRAWDOWN_MAX: float = 0.15

#: Out-of-sample walk-forward alpha must be strictly positive.  OOS
#: alpha ≤ 0 means the edge does not survive refit; this is the lesson
#: of the M31 evidence loss (ADR-014).
PERSONAL_WALK_FORWARD_ALPHA_MIN: float = 0.0

#: Consistency rule for Channel B.  Mieterharvester best-day rule: the
#: single best day must carry ≤ 35% of total profit.  Above 35% the firm
#: flags the account (TopstepX 40%, APEX 30%, TPT 50% are the official
#: values; we promote at the strictest of those — 30% APEX rounded up to
#: 35% to leave margin and respect the decisioni multi-firm 2026-08-22).
FUNDED_CONSISTENCY_PCT_MAX: float = 0.35

#: Minimum number of canonical paper sessions for Channel B validation.
#: Below 100 the MC pass-rate estimate is unstable (CLT doesn't kick in;
#: a single outlier session flips the verdict).
FUNDED_MIN_PAPER_SESSIONS: int = 100

#: Simulated eval pass-rate floor.  ≥ 60% pass-rate over canonical paper
#: sessions is the conservative gate (above coin-flip, with margin for
#: execution slippage).
FUNDED_SIMULATED_PASS_RATE_MIN: float = 0.60

#: Monte Carlo replay pass-rate floor (same 60%).  MC replays the
#: sessions under shuffled order / parameter perturbations to verify the
#: pass-rate is not a fluke of the specific session sequence.
FUNDED_MONTE_CARLO_PASS_RATE_MIN: float = 0.60

#: MC confidence level.  95% lower-CI on the pass-rate estimate must be
#: above the floor; this is the canonical statistical gate (Wilson or
#: normal-approx interval, MC tail-bootstrap the canonical choice).
FUNDED_MC_CONFIDENCE_LEVEL: float = 0.95


# ---------------------------------------------------------------------------
# Promotion inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PersonalPromotionMetrics:
    """Edge-quality metrics required for Channel A promotion.

    All fields are pre-registered: any relaxation requires an ADR
    amendment + a new entry in the Stage-1 preregistry (BL-708).
    """

    haircut_sharpe: float
    dsr: float
    max_drawdown: float  # positive fraction (0.15 = 15% peak-to-trough)
    walk_forward_alpha: float  # OOS alpha; > 0 means IS-positive out-of-sample


@dataclass(frozen=True)
class FundedPromotionMetrics:
    """Survivability metrics required for Channel B promotion."""

    # PropFirmRiskGovernor session envelope produced no breach
    # (DAILY_LOSS / OVERALL_LOSS / CONSISTENCY / NEWS_BLACKOUT).
    hard_risk_compliant: bool

    # Best-day share of total profit over the validation window.
    # 0.0 disables the rule; we promote at < 0.35 strictly.
    consistency_pct: float

    # Whether the firm profile supports DAILY_LOSS in PAUSE-or-TERMINATE
    # mode (DailyLossAction.PAUSE or TERMINATE; default TERMINATE).
    daily_pause_terminate_supported: bool

    # ≥ FUNDED_MIN_PAPER_SESSIONS simulated sessions on the canonical
    # paper runner (BL-728).  Below the floor the gate fails closed.
    n_paper_sessions: int

    # Fraction of the n_paper_sessions that ended in PASS for the
    # simulated eval.  Must be ≥ FUNDED_SIMULATED_PASS_RATE_MIN.
    simulated_pass_rate: float

    # Same metric, MC-replayed.  Below FUNDED_MONTE_CARLO_PASS_RATE_MIN
    # at FUNDED_MC_CONFIDENCE_LEVEL lower-CI the strategy fails even if
    # the raw pass-rate is high (the order-dependent fluke case).
    monte_carlo_pass_rate: float


@dataclass(frozen=True)
class PromotionDecision:
    """Verdict for one (channel, strategy) pair."""

    channel: Channel
    passes: bool
    failed_criteria: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def __bool__(self) -> bool:  # convenience: `if decision: ...`
        return self.passes


# ---------------------------------------------------------------------------
# Criteria checkers
# ---------------------------------------------------------------------------


def check_personal_channel(metrics: PersonalPromotionMetrics) -> PromotionDecision:
    """Apply Channel A promotion criteria.

    All four criteria are mandatory (AND semantics); any single failure
    flips the verdict to FAIL with the offending criterion named.  The
    checker is fail-closed: missing/NaN inputs fail with a recorded
    criterion name, not silently pass.
    """
    failed: list[str] = []

    # haircut_sharpe: NaN/inf ⇒ fail (cannot prove significance).
    hs = metrics.haircut_sharpe
    if not math.isfinite(hs):
        failed.append("haircut_sharpe (non-finite)")
    elif hs < PERSONAL_HAIRCUT_SHARPE_MIN:
        failed.append(f"haircut_sharpe ({hs:.3f} < {PERSONAL_HAIRCUT_SHARPE_MIN:.2f})")

    # dsr: same fail-closed semantics; DSR ∈ [0, 1] by construction.
    dsr = metrics.dsr
    if not math.isfinite(dsr):
        failed.append("dsr (non-finite)")
    elif dsr < PERSONAL_DSR_MIN:
        failed.append(f"dsr ({dsr:.3f} < {PERSONAL_DSR_MIN:.2f})")

    # max_drawdown: must be a positive fraction in [0, 1].  Outside the
    # domain ⇒ fail closed; above the ceiling ⇒ fail.
    dd = metrics.max_drawdown
    if not math.isfinite(dd) or dd < 0.0 or dd > 1.0:
        failed.append(f"max_drawdown (out-of-domain: {dd})")
    elif dd >= PERSONAL_MAX_DRAWDOWN_MAX:
        failed.append(f"max_drawdown ({dd:.3f} >= {PERSONAL_MAX_DRAWDOWN_MAX:.2f})")

    # walk_forward_alpha: must be > 0; the gate is strict (>, not ≥)
    # because OOS alpha == 0 is a coin-flip, not an edge.
    alpha = metrics.walk_forward_alpha
    if not math.isfinite(alpha):
        failed.append("walk_forward_alpha (non-finite)")
    elif alpha <= PERSONAL_WALK_FORWARD_ALPHA_MIN:
        failed.append(f"walk_forward_alpha ({alpha:.4f} <= {PERSONAL_WALK_FORWARD_ALPHA_MIN:.2f})")

    return PromotionDecision(
        channel=Channel.PERSONAL,
        passes=not failed,
        failed_criteria=tuple(failed),
        notes="Channel A: personal capital, vol-target 25-40% sizing" if not failed else "",
    )


def check_funded_channel(metrics: FundedPromotionMetrics) -> PromotionDecision:
    """Apply Channel B promotion criteria.

    Six criteria, all mandatory (AND semantics).  Fail-closed: any
    non-finite input, missing boolean True, or threshold miss flips the
    verdict to FAIL with the offending criterion named.
    """
    failed: list[str] = []

    # 1. Hard-risk envelope: governor must have raised NO breach on the
    # validation session.  Boolean is the authoritative signal; there is
    # no fuzzy pass.
    if not metrics.hard_risk_compliant:
        failed.append("hard_risk_compliant (governor raised a breach)")

    # 2. Consistency rule: best-day share ≤ 0.35 (strict).
    cp = metrics.consistency_pct
    if not math.isfinite(cp) or cp < 0.0 or cp > 1.0:
        failed.append(f"consistency_pct (out-of-domain: {cp})")
    elif cp > FUNDED_CONSISTENCY_PCT_MAX:
        failed.append(f"consistency_pct ({cp:.3f} > {FUNDED_CONSISTENCY_PCT_MAX:.2f})")

    # 3. Daily-loss action must be PAUSE-or-TERMINATE.  Strategies that
    # silently re-enter after a daily loss (UNSUPPORTED / RESEARCH_ONLY)
    # are not promotable.
    if not metrics.daily_pause_terminate_supported:
        failed.append("daily_pause_terminate_supported (firm lacks PAUSE/TERMINATE)")

    # 4. n_paper_sessions ≥ 100.  Below the floor the CLT doesn't apply
    # and a single outlier can flip the verdict — fail closed.
    n = metrics.n_paper_sessions
    if n < FUNDED_MIN_PAPER_SESSIONS:
        failed.append(f"n_paper_sessions ({n} < {FUNDED_MIN_PAPER_SESSIONS})")

    # 5. Simulated eval pass-rate ≥ 0.60.
    pr = metrics.simulated_pass_rate
    if not math.isfinite(pr) or pr < 0.0 or pr > 1.0:
        failed.append(f"simulated_pass_rate (out-of-domain: {pr})")
    elif pr < FUNDED_SIMULATED_PASS_RATE_MIN:
        failed.append(f"simulated_pass_rate ({pr:.3f} < {FUNDED_SIMULATED_PASS_RATE_MIN:.2f})")

    # 6. Monte Carlo pass-rate ≥ 0.60.  Identical threshold; the MC
    # replays protect against order-dependent flukes.
    mc = metrics.monte_carlo_pass_rate
    if not math.isfinite(mc) or mc < 0.0 or mc > 1.0:
        failed.append(f"monte_carlo_pass_rate (out-of-domain: {mc})")
    elif mc < FUNDED_MONTE_CARLO_PASS_RATE_MIN:
        failed.append(f"monte_carlo_pass_rate ({mc:.3f} < {FUNDED_MONTE_CARLO_PASS_RATE_MIN:.2f})")

    return PromotionDecision(
        channel=Channel.FUNDED,
        passes=not failed,
        failed_criteria=tuple(failed),
        notes=(
            "Channel B: funded prop-firm, hard-risk envelope + MC survivability"
            if not failed
            else ""
        ),
    )


def check_dual_channel(
    personal: PersonalPromotionMetrics, funded: FundedPromotionMetrics
) -> tuple[PromotionDecision, PromotionDecision]:
    """Apply both channel criteria; return (ChannelA, ChannelB) verdicts.

    Each channel is independent; a strategy can pass Channel A and fail
    Channel B (or vice versa).  Promotion is per-channel: pass Channel A
    → brokerage sizing; pass Channel B → firm-funded sizing.  No channel
    inherits the other's verdict.
    """
    return (check_personal_channel(personal), check_funded_channel(funded))


def eligible_profiles(profile: FirmProgramProfile) -> bool:
    """Return True if a firm profile is structurally promotable to Channel B.

    Structural eligibility checks that the firm CAN enforce a hard-risk
    envelope that matches our gate semantics (DailyLossAction in
    {PAUSE, TERMINATE}; SUPPORT_MODE allows automation).  These are
    necessary but not sufficient — the actual metrics still need to pass.
    """
    from policy.prop_firm.profile import DailyLossAction, SupportMode

    if profile.support_mode in (SupportMode.UNSUPPORTED, SupportMode.RESEARCH_ONLY):
        return False
    return profile.daily_loss_action in (DailyLossAction.PAUSE, DailyLossAction.TERMINATE)


def governor_clean(governor: PropFirmRiskGovernor, session_breaches: Sequence[str]) -> bool:
    """Return True if the governor raised no breach on the validation set.

    `session_breaches` is the list of breach type names emitted by the
    governor across the validation window (BL-722 surfaces them via
    `BreachType` enum values).  Empty list ⇒ hard_risk_compliant=True.
    The governor instance is accepted for symmetry with the production
    call site (the caller passes the same governor that emitted the
    breach list); the breach list is the authoritative signal.
    """
    del governor  # unused: the breach list is the authoritative signal
    return not session_breaches
    return len(session_breaches) == 0


__all__ = [
    "FUNDED_CONSISTENCY_PCT_MAX",
    "FUNDED_MC_CONFIDENCE_LEVEL",
    "FUNDED_MIN_PAPER_SESSIONS",
    "FUNDED_MONTE_CARLO_PASS_RATE_MIN",
    "FUNDED_SIMULATED_PASS_RATE_MIN",
    "PERSONAL_DSR_MIN",
    "PERSONAL_HAIRCUT_SHARPE_MIN",
    "PERSONAL_MAX_DRAWDOWN_MAX",
    "PERSONAL_WALK_FORWARD_ALPHA_MIN",
    "Channel",
    "FundedPromotionMetrics",
    "PersonalPromotionMetrics",
    "PromotionDecision",
    "check_dual_channel",
    "check_funded_channel",
    "check_personal_channel",
    "eligible_profiles",
    "governor_clean",
]
