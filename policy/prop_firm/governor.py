"""Prop-firm risk governor — enforces funded-account rules in real time.

The governor is a *pure, deterministic* decision component.  It tracks
account state (balance, equity, peaks, daily counters) and answers two
questions the live trading loop needs:

1. **Pre-trade gate** — ``check_new_order``: may I open this position
   without projecting a breach of the daily or overall loss limit?
2. **Live breach scan** — ``evaluate``: given the current balance and
   equity, which rules (if any) are now violated, and is the challenge
   passed or failed?

It also provides position sizing (``max_position_size``) that respects
the remaining daily-loss budget, and day rollover (``rollover``) to
reset intraday counters at server midnight.

The governor is intentionally decoupled from any specific broker: it
receives balance/equity as plain floats, so it works identically against
the paper broker today and the MetaTrader 5 bridge (Fase 5) tomorrow.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from policy.prop_firm.profile import FirmProgramProfile as PropFirmProfile


class ChallengeStatus(StrEnum):
    """Lifecycle of a single funded-account challenge."""

    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED_DAILY = "failed_daily"
    FAILED_OVERALL = "failed_overall"


class BreachType(StrEnum):
    """Which rule was violated."""

    DAILY_LOSS = "daily_loss"
    OVERALL_LOSS = "overall_loss"
    CONSISTENCY = "consistency"
    MAX_POSITIONS = "max_positions"


@dataclass(frozen=True)
class Breach:
    """A single rule violation discovered by ``evaluate``."""

    type: BreachType
    #: "hard" breaches end the challenge (flatten + stop);
    #: "soft" breaches are warnings (e.g. consistency).
    severity: str
    message: str
    #: Current usage as a fraction of the limit (0.0 to 1.0+).
    used_pct: float = 0.0


@dataclass(frozen=True)
class OrderCheck:
    """Result of the pre-trade gate."""

    allowed: bool
    reason: str = ""
    #: Maximum lots the governor would permit for this risk, if computed.
    max_lots: float | None = None


@dataclass
class AccountState:
    """Mutable snapshot of the account, updated on every tick/fill."""

    initial_balance: float
    current_balance: float
    current_equity: float
    day_start_balance: float
    day_start_equity: float
    peak_balance: float
    peak_equity: float
    realized_pnl_today: float = 0.0
    total_profit: float = 0.0
    trading_days: int = 0
    today_has_trade: bool = False
    today_profit: float = 0.0


class PropFirmRiskGovernor:
    """Stateful enforcer of a :class:`~policy.prop_firm.profile.FirmProgramProfile`.

    Usage::

        gov = PropFirmRiskGovernor(THE5ERS, initial_balance=100_000)
        gov.update(balance=99_500, equity=99_200)        # each tick
        check = gov.check_new_order(entry=1.10, stop=1.095,
                                    lots=1.0, contract_size=100_000)
        for breach in gov.evaluate():
            if breach.severity == "hard":
                ...  # flatten everything
    """

    def __init__(self, profile: PropFirmProfile, initial_balance: float) -> None:
        if initial_balance <= 0:
            raise ValueError("initial_balance must be positive")
        self.profile = profile
        self.status = ChallengeStatus.IN_PROGRESS
        self.state = AccountState(
            initial_balance=initial_balance,
            current_balance=initial_balance,
            current_equity=initial_balance,
            day_start_balance=initial_balance,
            day_start_equity=initial_balance,
            peak_balance=initial_balance,
            peak_equity=initial_balance,
        )

    # ------------------------------------------------------------------
    # State ingestion
    # ------------------------------------------------------------------
    def update(self, balance: float, equity: float) -> None:
        """Record the latest balance and equity (call every tick/fill)."""
        s = self.state
        s.current_balance = balance
        s.current_equity = equity
        if balance > s.peak_balance:
            s.peak_balance = balance
        if equity > s.peak_equity:
            s.peak_equity = equity

    def record_trade(self, realized_pnl: float) -> None:
        """Record a closed trade's realized P&L against the daily totals."""
        s = self.state
        s.realized_pnl_today += realized_pnl
        if realized_pnl > 0:
            s.total_profit += realized_pnl
            s.today_profit += realized_pnl
        s.today_has_trade = True

    def rollover(self) -> None:
        """Reset intraday counters for a new trading day (server midnight).

        Call once per day at the prop-firm server's midnight (typically
        EET, 22:00 GMT in winter / 21:00 GMT in summer).

        For ``TRAILING_EOD`` mode, the peak balance/equity is captured
        at rollover and becomes the new reference floor.  For
        ``TRAILING_INTRADAY`` the peak is continuous and does not
        reset here.
        """
        from policy.prop_firm.profile import DrawdownMode

        s = self.state
        if s.today_has_trade:
            s.trading_days += 1

        # EOD trailing: lock the peak at end of day
        if self.profile.dd_mode == DrawdownMode.TRAILING_EOD:
            s.peak_balance = max(s.peak_balance, s.current_balance)
            s.peak_equity = max(s.peak_equity, s.current_equity)

        s.day_start_balance = s.current_balance
        s.day_start_equity = s.current_equity
        s.realized_pnl_today = 0.0
        s.today_profit = 0.0
        s.today_has_trade = False

    # ------------------------------------------------------------------
    # Loss measurement
    # ------------------------------------------------------------------
    def _daily_reference(self) -> float:
        """Day-start balance or equity per ``daily_loss_basis``."""
        s = self.state
        if str(self.profile.daily_loss_basis) == "equity":
            return s.day_start_equity
        return s.day_start_balance

    def _overall_reference(self) -> float:
        """Peak balance (trailing) or initial balance (static)."""
        from policy.prop_firm.profile import DrawdownMode

        if self.profile.dd_mode in (DrawdownMode.TRAILING_INTRADAY, DrawdownMode.TRAILING_EOD):
            return self.state.peak_balance
        return self.state.initial_balance

    def daily_loss(self) -> float:
        """Absolute daily loss in account currency (0 if not down)."""
        return max(0.0, self._daily_reference() - self.state.current_equity)

    def daily_loss_used_pct(self) -> float:
        """Daily loss as a fraction of the day's starting reference."""
        base = self._daily_reference()
        if base <= 0:
            return 0.0
        return self.daily_loss() / base

    def overall_floor(self) -> float:
        """Equity level below which the overall rule is breached."""
        return self._overall_reference() * (1.0 - self.profile.max_overall_loss_pct)

    def overall_loss(self) -> float:
        """Absolute drop from the overall reference to current equity."""
        return max(0.0, self._overall_reference() - self.state.current_equity)

    def overall_loss_used_pct(self) -> float:
        """Overall loss as a fraction of the allowed maximum."""
        pct = self.profile.max_overall_loss_pct
        if pct <= 0:
            return 0.0
        ref = self._overall_reference()
        if ref <= 0:
            return 0.0
        return self.overall_loss() / (ref * pct)

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------
    def max_position_size(self, entry: float, stop: float, contract_size: float) -> float:
        """Maximum lots allowed without breaching the daily-loss budget.

        Two caps bind: the remaining daily-loss budget, and the per-trade
        risk cap (``risk_per_trade_pct`` of balance).  The smaller wins.

        Args:
            entry: Planned entry price.
            stop: Planned stop-loss price.
            contract_size: Units per lot in account currency per price unit
                (e.g. 100_000 for a standard FX lot; 1 for 1-unit contracts).

        Returns:
            Max lots (>= 0).  ``risk_per_lot`` is ``contract_size * |entry-stop|``.
        """
        risk_per_lot = contract_size * abs(entry - stop)
        if risk_per_lot <= 0:
            return 0.0
        daily_limit_cash = self.profile.max_daily_loss_pct * self._daily_reference()
        remaining_daily = max(0.0, daily_limit_cash - self.daily_loss())
        per_trade_cash = self.profile.risk_per_trade_pct * self.state.current_balance
        budget = min(remaining_daily, per_trade_cash)
        return max(0.0, budget / risk_per_lot)

    # ------------------------------------------------------------------
    # Pre-trade gate
    # ------------------------------------------------------------------
    def check_new_order(
        self, entry: float, stop: float, lots: float, contract_size: float
    ) -> OrderCheck:
        """Gate a new entry: allow only if it cannot breach a hard limit.

        Checks (in order):
        1. Support mode — only AUTO_SUPPORTED profiles can trade automatically.
        2. Challenge status — must be IN_PROGRESS.
        3. Projected loss — must not breach daily or overall ceiling.

        Computes the projected loss if the stop is hit and refuses when
        it would push the account past the daily or overall ceiling.
        """
        # Gate 0: Support mode check
        from policy.prop_firm.profile import SupportMode

        if self.profile.support_mode != SupportMode.AUTO_SUPPORTED:
            return OrderCheck(
                allowed=False,
                reason=f"Automation denied: support_mode={self.profile.support_mode.value}",
            )

        if self.status != ChallengeStatus.IN_PROGRESS:
            return OrderCheck(allowed=False, reason=f"Challenge already {self.status.value}")

        risk_per_lot = contract_size * abs(entry - stop)
        projected_loss = lots * risk_per_lot
        max_lots = self.max_position_size(entry, stop, contract_size)

        daily_limit_cash = self.profile.max_daily_loss_pct * self._daily_reference()
        if self.daily_loss() + projected_loss >= daily_limit_cash:
            used = self.daily_loss_used_pct()
            return OrderCheck(
                allowed=False,
                reason=(
                    f"Projected loss {projected_loss:.2f} would breach daily "
                    f"limit ({self.profile.max_daily_loss_pct:.0%}); "
                    f"daily used {used:.0%}"
                ),
                max_lots=max_lots,
            )

        overall_limit_cash = self.profile.max_overall_loss_pct * self._overall_reference()
        if self.overall_loss() + projected_loss >= overall_limit_cash:
            used = self.overall_loss_used_pct()
            return OrderCheck(
                allowed=False,
                reason=(
                    f"Projected loss {projected_loss:.2f} would breach overall "
                    f"limit ({self.profile.max_overall_loss_pct:.0%}); "
                    f"overall used {used:.0%}"
                ),
                max_lots=max_lots,
            )

        if lots > max_lots:
            return OrderCheck(
                allowed=False,
                reason=(
                    f"Requested size {lots:.4f} exceeds risk budget; "
                    f"maximum allowed is {max_lots:.4f}"
                ),
                max_lots=max_lots,
            )

        return OrderCheck(allowed=True, max_lots=max_lots)

    # ------------------------------------------------------------------
    # Breach scan + challenge outcome
    # ------------------------------------------------------------------
    def evaluate(self) -> list[Breach]:
        """Scan all rules and return every violation (hard + soft)."""
        breaches: list[Breach] = []
        p = self.profile
        s = self.state

        # Daily loss — hard
        daily_used = self.daily_loss_used_pct()
        if daily_used >= p.max_daily_loss_pct:
            breaches.append(
                Breach(
                    type=BreachType.DAILY_LOSS,
                    severity="hard",
                    message=f"Daily loss {daily_used:.1%} >= limit {p.max_daily_loss_pct:.0%}",
                    used_pct=daily_used,
                )
            )

        # Overall loss — hard
        overall_used = self.overall_loss_used_pct()
        if s.current_equity <= self.overall_floor():
            breaches.append(
                Breach(
                    type=BreachType.OVERALL_LOSS,
                    severity="hard",
                    message=(
                        f"Equity {s.current_equity:.2f} at/below overall floor "
                        f"{self.overall_floor():.2f} ({p.dd_mode})"
                    ),
                    used_pct=overall_used,
                )
            )

        # Consistency — soft (only meaningful once profitable)
        dominates = (
            p.consistency_pct > 0
            and s.total_profit > 0
            and s.today_profit > p.consistency_pct * s.total_profit
        )
        if dominates:
            share = s.today_profit / s.total_profit
            breaches.append(
                Breach(
                    type=BreachType.CONSISTENCY,
                    severity="soft",
                    message=(
                        f"Today's profit {share:.0%} of total exceeds consistency "
                        f"limit {p.consistency_pct:.0%}"
                    ),
                    used_pct=share,
                )
            )

        # Promote status from hard breaches
        if any(b.severity == "hard" for b in breaches):
            if any(b.type == BreachType.DAILY_LOSS for b in breaches):
                self.status = ChallengeStatus.FAILED_DAILY
            else:
                self.status = ChallengeStatus.FAILED_OVERALL

        return breaches

    def challenge_outcome(self) -> ChallengeStatus:
        """Return the terminal status, evaluating pass conditions lazily."""
        if self.status != ChallengeStatus.IN_PROGRESS:
            return self.status
        s = self.state
        p = self.profile
        target_balance = round(s.initial_balance * (1.0 + p.profit_target_pct), 2)
        days_ok = s.trading_days + (1 if s.today_has_trade else 0) >= p.min_trading_days
        if s.current_balance >= target_balance and days_ok:
            self.status = ChallengeStatus.PASSED
        return self.status
