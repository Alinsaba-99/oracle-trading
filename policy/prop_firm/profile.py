"""Prop-firm evaluation profiles — versioned, immutable, source-verified.

Each profile encodes the *exact* rules a funded-account program enforces:
profit target, drawdown limits (static/trailing/EOD), daily loss with
timezone-aware reset, contract caps, scaling plans, session rules, news
blackout, consistency rule, minimum days, and allowed products.

Profiles are *versioned* and *immutable*.  Every profile carries its
source URL, verification date, and content hash so rule changes can be
tracked without overwriting legacy accounts.

Support modes:

- ``AUTO_SUPPORTED`` — automation allowed, certified adapter available.
- ``ASSISTED_ONLY`` — Oracle generates signals, but order submission is
  manual (firm rules prohibit bots / API automation).
- ``RESEARCH_ONLY`` — rules modelled for backtesting only; no execution.
- ``UNSUPPORTED`` — rules unavailable, platform unsupported, or source
  cannot be verified.
"""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from typing import Any


class SupportMode(StrEnum):
    """Level of automation a prop firm allows."""

    AUTO_SUPPORTED = "auto_supported"
    ASSISTED_ONLY = "assisted_only"
    RESEARCH_ONLY = "research_only"
    UNSUPPORTED = "unsupported"


class DrawdownMode(StrEnum):
    """How the maximum overall loss is calculated."""

    STATIC = "static"  # fixed floor from initial balance
    TRAILING_INTRADAY = "trailing_intraday"  # trails peak intraday
    TRAILING_EOD = "trailing_eod"  # trails peak at end of day only
    LOCK = "lock"  # locks at a specific level


class DailyLossBasis(StrEnum):
    """Reference for daily loss limit."""

    BALANCE = "balance"
    EQUITY = "equity"


class OverallLossBasis(StrEnum):
    """Reference for overall loss limit."""

    BALANCE = "balance"
    EQUITY = "equity"


class SessionRule(StrEnum):
    """When trading is allowed."""

    STANDARD = "standard"  # CME regular trading hours
    EXTENDED = "extended"  # includes electronic / overnight
    RESTRICTED = "restricted"  # limited hours defined by the firm
    NEWS_ONLY = "news_only"  # blackout around major news events


# ---------------------------------------------------------------------------
# Contract cap
# ---------------------------------------------------------------------------


class ContractCap:
    """Maximum contracts allowed, in mini-equivalent units.

    A standard ES contract = 5 micro (MES) units.  The cap is stored in
    mini-equivalents so scaling rules apply uniformly across contract
    sizes.
    """

    def __init__(self, max_mini_eq: int, per_product: dict[str, int] | None = None) -> None:
        self.max_mini_eq = max_mini_eq
        self.per_product = per_product or {}

    def to_dict(self) -> dict[str, Any]:
        return {"max_mini_eq": self.max_mini_eq, "per_product": dict(self.per_product)}


# ---------------------------------------------------------------------------
# Scaling plan
# ---------------------------------------------------------------------------


class ScalingPlan:
    """Account growth milestones.

    When the account reaches a profit threshold, the max contract cap
    increases according to the scaling table.
    """

    def __init__(self, tiers: list[tuple[float, int]]) -> None:
        """*tiers*: list of ``(profit_target_pct, new_max_mini_eq)``."""
        self.tiers = list(tiers)

    def max_at_profit(self, profit_pct: float) -> int:
        """Return the max contracts at the given profit level."""
        result = 0
        for threshold, cap in self.tiers:
            if profit_pct >= threshold:
                result = cap
            else:
                break
        return result

    def to_dict(self) -> dict[str, Any]:
        return {"tiers": [(t, c) for t, c in self.tiers]}


# ---------------------------------------------------------------------------
# News blackout
# ---------------------------------------------------------------------------


class NewsBlackout:
    """Trading blackout around scheduled high-impact news events.

    Many prop firms prohibit trading N minutes before and after
    pre-scheduled Tier-1 news events (FOMC, NFP, CPI, etc.).
    """

    def __init__(self, before_minutes: int = 5, after_minutes: int = 5) -> None:
        self.before_minutes = before_minutes
        self.after_minutes = after_minutes

    def to_dict(self) -> dict[str, Any]:
        return {"before_minutes": self.before_minutes, "after_minutes": self.after_minutes}


# ---------------------------------------------------------------------------
# Main profile model
# ---------------------------------------------------------------------------


class FirmProgramProfile:
    """Versioned, immutable rule-set for a single funded-account program.

    Parameters
    ----------
    firm :
        Firm name, e.g. ``"TOPSTEP"``.
    program :
        Program name, e.g. ``"Trading Combine"``, ``"XFA"``.
    stage :
        Stage within the program: ``"evaluation"``, ``"funded"``, ``"express"``.
    platform :
        Trading platform, e.g. ``"TopstepX"``, ``"Rithmic"``, ``"Tradovate"``.
    account_size :
        Account size in USD.
    rule_version :
        Semantic version string for this snapshot of rules.
    effective_from :
        ISO date the rule version became effective.
    effective_to :
        ISO date the rule version was superseded (``None`` if current).
    source_url :
        URL where the official rules were obtained.
    source_checked_at :
        ISO datetime the source was last verified.
    support_mode :
        Automation support level.
    profit_target_pct :
        Profit target as a decimal (0.10 = 10%).
    max_daily_loss_pct :
        Maximum daily loss as a decimal.
    max_overall_loss_pct :
        Maximum overall drawdown as a decimal.
    dd_mode :
        How the overall loss floor is calculated.
    daily_loss_basis :
        Balance or equity reference for daily loss.
    daily_loss_reset_timezone :
        IANA timezone name for daily loss reset (e.g. ``"America/Chicago"``).
    overall_loss_basis :
        Balance or equity reference for overall loss.
    min_trading_days :
        Minimum number of trading days required to pass.
    min_profitable_days :
        Minimum number of profitable days required.
    consistency_pct :
        Max fraction of total profit from a single day (0.0 = disabled).
    max_concurrent_positions :
        Max simultaneous open positions (0 = unlimited).
    contract_cap :
        Maximum contracts in mini-equivalent.
    scaling_plan :
        Account growth milestones.
    session_rule :
        Allowed trading sessions.
    news_blackout :
        Blackout rules around news events.
    allowed_products :
        List of product symbols allowed for trading.
    risk_per_trade_pct :
        Default per-trade risk as a fraction of balance.
    """

    def __init__(
        self,
        firm: str,
        program: str,
        stage: str,
        platform: str,
        account_size: int,
        rule_version: str,
        effective_from: str,
        source_url: str,
        source_checked_at: str,
        support_mode: SupportMode,
        profit_target_pct: float,
        max_daily_loss_pct: float,
        max_overall_loss_pct: float,
        max_daily_loss_amount: float | None = None,
        max_overall_loss_amount: float | None = None,
        overall_loss_lock_at_initial: bool = False,
        dd_mode: DrawdownMode = DrawdownMode.STATIC,
        daily_loss_basis: str = "equity",
        daily_loss_reset_timezone: str = "America/Chicago",
        overall_loss_basis: str = "equity",
        min_trading_days: int = 0,
        min_profitable_days: int = 0,
        consistency_pct: float = 0.0,
        max_concurrent_positions: int = 0,
        contract_cap: ContractCap | None = None,
        scaling_plan: ScalingPlan | None = None,
        session_rule: SessionRule = SessionRule.STANDARD,
        news_blackout: NewsBlackout | None = None,
        allowed_products: list[str] | None = None,
        risk_per_trade_pct: float = 0.01,
        effective_to: str | None = None,
    ) -> None:
        self.firm = firm
        self.program = program
        self.stage = stage
        self.platform = platform
        self.account_size = account_size
        self.rule_version = rule_version
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.source_url = source_url
        self.source_checked_at = source_checked_at
        self.support_mode = support_mode
        self.profit_target_pct = profit_target_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_overall_loss_pct = max_overall_loss_pct
        self.max_daily_loss_amount = max_daily_loss_amount
        self.max_overall_loss_amount = max_overall_loss_amount
        self.overall_loss_lock_at_initial = overall_loss_lock_at_initial
        self.dd_mode = dd_mode
        self.daily_loss_basis = daily_loss_basis
        self.daily_loss_reset_timezone = daily_loss_reset_timezone
        self.overall_loss_basis = overall_loss_basis
        self.min_trading_days = min_trading_days
        self.min_profitable_days = min_profitable_days
        self.consistency_pct = consistency_pct
        self.max_concurrent_positions = max_concurrent_positions
        self.contract_cap = contract_cap
        self.scaling_plan = scaling_plan
        self.session_rule = session_rule
        self.news_blackout = news_blackout
        self.allowed_products = allowed_products or []
        self.risk_per_trade_pct = risk_per_trade_pct

    @property
    def version_key(self) -> str:
        """Canonical key: firm+program+stage+platform+account_size+rule_version."""
        return (
            f"{self.firm}/{self.program}/{self.stage}/"
            f"{self.platform}/{self.account_size}/{self.rule_version}"
        )

    @property
    def content_hash(self) -> str:
        """SHA-256 of the serialised profile for integrity verification."""
        raw = (
            f"{self.version_key}|{self.effective_from}|{self.profit_target_pct}|"
            f"{self.max_daily_loss_pct}|{self.max_overall_loss_pct}|{self.dd_mode}|"
            f"{self.max_daily_loss_amount}|{self.max_overall_loss_amount}|"
            f"{self.overall_loss_lock_at_initial}|{self.daily_loss_basis}|{self.support_mode}"
        )
        return sha256(raw.encode()).hexdigest()[:16]

    def is_effective_at(self, date_str: str) -> bool:
        """Check if this profile version is effective on a given date."""
        return not (
            date_str < self.effective_from or (self.effective_to and date_str > self.effective_to)
        )

    def describe(self) -> str:
        """Human-readable summary."""
        return (
            f"[{self.support_mode.value}] {self.firm} {self.program} {self.stage} "
            f"- ${self.account_size:,} (v{self.rule_version})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_key": self.version_key,
            "firm": self.firm,
            "program": self.program,
            "stage": self.stage,
            "platform": self.platform,
            "account_size": self.account_size,
            "rule_version": self.rule_version,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "support_mode": self.support_mode.value,
            "profit_target_pct": self.profit_target_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_overall_loss_pct": self.max_overall_loss_pct,
            "max_daily_loss_amount": self.max_daily_loss_amount,
            "max_overall_loss_amount": self.max_overall_loss_amount,
            "overall_loss_lock_at_initial": self.overall_loss_lock_at_initial,
            "dd_mode": self.dd_mode.value,
            "daily_loss_basis": str(self.daily_loss_basis),
            "overall_loss_basis": str(self.overall_loss_basis),
            "min_trading_days": self.min_trading_days,
            "min_profitable_days": self.min_profitable_days,
            "consistency_pct": self.consistency_pct,
            "contract_cap": self.contract_cap.to_dict() if self.contract_cap else None,
            "content_hash": self.content_hash,
        }

    def __repr__(self) -> str:
        return self.describe()


#: Backward-compatible alias.
PropFirmProfile = FirmProgramProfile


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class FirmProgramRegistry:
    """Versioned registry of prop-firm profiles.

    Profiles are indexed by ``version_key`` and can be looked up by
    canonical fields and effective date.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, FirmProgramProfile] = {}

    def register(self, profile: FirmProgramProfile) -> None:
        """Register a profile.  Overwrites if the same version_key exists."""
        self._profiles[profile.version_key] = profile

    def get(
        self,
        firm: str,
        program: str,
        stage: str,
        platform: str,
        account_size: int,
        rule_version: str | None = None,
    ) -> FirmProgramProfile | None:
        """Lookup a profile by canonical fields."""
        if rule_version:
            key = f"{firm}/{program}/{stage}/{platform}/{account_size}/{rule_version}"
            return self._profiles.get(key)
        # Return the latest (highest rule_version) matching the key prefix
        prefix = f"{firm}/{program}/{stage}/{platform}/{account_size}/"
        candidates = [k for k in self._profiles if k.startswith(prefix)]
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return self._profiles[candidates[0]]

    def list_active(self, date_str: str) -> list[FirmProgramProfile]:
        """Return all profiles effective on a given date."""
        return [p for p in self._profiles.values() if p.is_effective_at(date_str)]

    def all(self) -> list[FirmProgramProfile]:
        return list(self._profiles.values())

    def count(self) -> int:
        return len(self._profiles)
