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

BL-722 enhancements (2026-08-22):

* ``ChallengeStatus.PAUSED`` — daily-loss breach with ``DailyLossAction.PAUSE``
  suspends trading for the rest of the day but does not terminate the
  challenge; ``rollover`` resumes it when no overall floor is breached.
* ``DrawdownMode.TRAILING_CLOSED`` — peak balance rises only on closed
  profits (E8 Markets Dynamic Drawdown); the floor formula uses a DD
  amount anchored to the initial balance.
* Consistency rule blocks ``PASSED`` until the best-ever day is diluted
  below ``consistency_pct`` of total profit.
* News-blackout pre-trade gate (``is_news_blackout`` flag) for profiles
  that declare ``NewsBlackout``.
* Anti-HFT helper (``check_trade_duration``) for profiles that declare
  ``min_trade_duration_minutes``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from policy.prop_firm.profile import DailyLossAction, DrawdownMode
from policy.prop_firm.profile import FirmProgramProfile as PropFirmProfile


class ChallengeStatus(StrEnum):
    """Lifecycle of a single funded-account challenge."""

    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED_DAILY = "failed_daily"
    FAILED_OVERALL = "failed_overall"
    #: BL-722: daily-loss breach with ``DailyLossAction.PAUSE`` profile.
    #: Trading is suspended for the day; ``rollover`` may resume it.
    PAUSED = "paused"


class BreachType(StrEnum):
    """Which rule was violated."""

    DAILY_LOSS = "daily_loss"
    OVERALL_LOSS = "overall_loss"
    CONSISTENCY = "consistency"
    MAX_POSITIONS = "max_positions"
    #: BL-722: trade closed below ``profile.min_trade_duration_minutes``.
    ANTI_HFT = "anti_hft"
    #: BL-722: pre-trade gate fired inside a news blackout window.
    NEWS_BLACKOUT = "news_blackout"
    #: BL-722: realised profit below ``profile.payout_buffer_pct`` of
    #: initial balance; payout not yet unlocked.
    PAYOUT_BUFFER = "payout_buffer"


@dataclass(frozen=True)
class Breach:
    """A single rule violation discovered by ``evaluate``."""

    type: BreachType
    #: "hard" breaches end the challenge (flatten + stop);
    #: "soft" breaches are warnings (e.g. consistency);
    #: "soft_pause" (BL-722) suspends trading for the rest of the day
    #: but does not terminate the challenge.
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
    """Mutable snapshot of the account, updated on every tick/fill.

    BL-722 fields:

    - ``day_profits``: closed-day positive-profit history (used by the
      real-time consistency rule to compute ``max(day_profits)/total``).
    - ``current_trade_open_ts``: epoch seconds the most recent trade
      was opened; ``record_trade_with_duration`` enforces the anti-HFT
      minimum duration rule when the trade closes.
    - ``current_trade_pnl``: realised PnL of the most recent closed
      trade (cached for tests + downstream reporting).
    - ``is_paused_today``: ``True`` once today's PAUSE-mode daily-loss
      breach has latched the challenge to ``PAUSED``.  Cleared by
      ``rollover()``.
    """

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
    #: BL-722: best profitable day across all completed sessions.
    #: Used by the consistency rule to gate PASSED transitions until
    #: additional winning days dilute the share below ``consistency_pct``.
    max_day_profit: float = 0.0
    #: BL-722: per-day closed-profit history for the consistency
    #: distribution check (``max(day_profits) / total_profit``).
    day_profits: list[float] = field(default_factory=list)
    #: BL-722: anti-HFT — epoch seconds the current/last trade opened.
    current_trade_open_ts: float | None = None
    #: BL-722: cached realised PnL of the most recent closed trade.
    current_trade_pnl: float = 0.0
    #: BL-722: daily-pause latch; cleared by ``rollover()``.
    is_paused_today: bool = False


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
        from policy.prop_firm.profile import DrawdownMode

        s = self.state
        s.current_balance = balance
        s.current_equity = equity
        if self.profile.dd_mode == DrawdownMode.TRAILING_CLOSED:
            # BL-722: peak_balance rises ONLY on closed (realized) profits,
            # recorded via ``record_trade``. Floating equity does NOT trail.
            return
        if self.profile.dd_mode != DrawdownMode.TRAILING_EOD:
            if balance > s.peak_balance:
                s.peak_balance = balance
            if equity > s.peak_equity:
                s.peak_equity = equity

    def record_trade(self, realized_pnl: float) -> None:
        """Record a closed trade's realized P&L against the daily totals."""
        from policy.prop_firm.profile import DrawdownMode

        s = self.state
        s.realized_pnl_today += realized_pnl
        if realized_pnl > 0:
            s.total_profit += realized_pnl
            s.today_profit += realized_pnl
            # BL-722: TRAILING_CLOSED — peak rises only on closed winning
            # trades; ``post_trade_balance`` is the closed-equity level
            # assuming the caller invoked ``update`` with the pre-trade
            # balance (the documented contract).
            if self.profile.dd_mode == DrawdownMode.TRAILING_CLOSED:
                post_trade_balance = s.current_balance + realized_pnl
                if post_trade_balance > s.peak_balance:
                    s.peak_balance = post_trade_balance
        s.today_has_trade = True

    def rollover(self) -> None:
        """Reset intraday counters for a new trading day (server midnight).

        Call once per day at the prop-firm server's midnight (typically
        EET, 22:00 GMT in winter / 21:00 GMT in summer).

        For ``TRAILING_EOD`` mode, the peak balance/equity is captured
        at rollover and becomes the new reference floor.  For
        ``TRAILING_INTRADAY`` the peak is continuous and does not
        reset here.  ``TRAILING_CLOSED`` peak is updated only by
        ``record_trade`` and is untouched here.

        BL-722: a PAUSED challenge resumes to ``IN_PROGRESS`` at the
        next session if the equity still sits above the overall floor;
        otherwise it transitions to ``FAILED_OVERALL``.
        """
        from policy.prop_firm.profile import DrawdownMode

        s = self.state
        if s.today_has_trade:
            s.trading_days += 1

        # BL-722: snapshot best day before resetting today_profit.
        if s.today_profit > s.max_day_profit:
            s.max_day_profit = s.today_profit
        # BL-722: archive today's profit into day_profits history so the
        # consistency rule can compute ``max(day_profits)/total``.
        if s.today_profit > 0:
            s.day_profits.append(s.today_profit)

        # EOD trailing: lock the peak at end of day
        if self.profile.dd_mode == DrawdownMode.TRAILING_EOD:
            s.peak_balance = max(s.peak_balance, s.current_balance)
            s.peak_equity = max(s.peak_equity, s.current_equity)

        s.day_start_balance = s.current_balance
        s.day_start_equity = s.current_equity
        s.realized_pnl_today = 0.0
        s.today_profit = 0.0
        s.today_has_trade = False
        # BL-722: clear the daily-pause latch so the next session starts
        # fresh.
        s.is_paused_today = False

        # BL-722: PAUSE → IN_PROGRESS at next session if overall floor holds.
        if self.status == ChallengeStatus.PAUSED:
            if s.current_equity > self.overall_floor():
                self.status = ChallengeStatus.IN_PROGRESS
            else:
                self.status = ChallengeStatus.FAILED_OVERALL

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

        if self.profile.dd_mode in (
            DrawdownMode.TRAILING_INTRADAY,
            DrawdownMode.TRAILING_EOD,
            DrawdownMode.TRAILING_CLOSED,
        ):
            return self.state.peak_balance
        return self.state.initial_balance

    def daily_loss(self) -> float:
        """Absolute daily loss in account currency (0 if not down)."""
        return max(0.0, self._daily_reference() - self.state.current_equity)

    def daily_loss_used_pct(self) -> float:
        """Daily loss as a fraction of the day's starting reference."""
        reference = self._daily_reference()
        if reference <= 0:
            return 0.0
        return self.daily_loss() / reference

    def daily_loss_limit_cash(self) -> float:
        """Configured daily loss ceiling in account currency."""
        if self.profile.max_daily_loss_amount is not None:
            return self.profile.max_daily_loss_amount
        return self.profile.max_daily_loss_pct * self._daily_reference()

    def overall_floor(self) -> float:
        """Equity level below which the overall rule is breached."""
        reference = self._overall_reference()
        # BL-722: TRAILING_CLOSED uses a DD amount anchored to the initial
        # balance (not to the moving peak), so the floor rises by exactly
        # the realized profit accumulated in peak_balance.
        if self.profile.dd_mode == DrawdownMode.TRAILING_CLOSED:
            if self.profile.max_overall_loss_amount is not None:
                return reference - self.profile.max_overall_loss_amount
            return reference - (self.state.initial_balance * self.profile.max_overall_loss_pct)
        if self.profile.max_overall_loss_amount is None:
            return reference * (1.0 - self.profile.max_overall_loss_pct)
        floor = reference - self.profile.max_overall_loss_amount
        if self.profile.overall_loss_lock_at_initial:
            floor = min(floor, self.state.initial_balance)
        return floor

    def overall_loss(self) -> float:
        """Absolute drop from the overall reference to current equity."""
        return max(0.0, self._overall_reference() - self.state.current_equity)

    def overall_loss_used_pct(self) -> float:
        """Overall loss as a fraction of the allowed maximum."""
        limit = self.overall_loss_limit_cash()
        if limit <= 0:
            return 0.0
        return self.overall_loss() / limit

    def overall_loss_limit_cash(self) -> float:
        """Configured overall loss ceiling in account currency."""
        if self.profile.max_overall_loss_amount is not None:
            return self.profile.max_overall_loss_amount
        return self.profile.max_overall_loss_pct * self._overall_reference()

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
        daily_limit_cash = self.daily_loss_limit_cash()
        remaining_daily = max(0.0, daily_limit_cash - self.daily_loss())
        per_trade_cash = self.profile.risk_per_trade_pct * self.state.current_balance
        budget = min(remaining_daily, per_trade_cash)
        return max(0.0, budget / risk_per_lot)

    # ------------------------------------------------------------------
    # Pre-trade gate
    # ------------------------------------------------------------------
    def check_new_order(
        self,
        entry: float,
        stop: float,
        lots: float,
        contract_size: float,
        *,
        is_news_blackout: bool = False,
    ) -> OrderCheck:
        """Gate a new entry: allow only if it cannot breach a hard limit.

        Checks (in order):
        1. Support mode — only AUTO_SUPPORTED profiles can trade automatically.
        2. News blackout (BL-722) — when the profile declares a
           ``NewsBlackout`` rule and the caller signals an active window,
           orders are blocked for the duration of the blackout.
        3. Challenge status — must be IN_PROGRESS.
        4. Projected loss — must not breach daily or overall ceiling.

        Computes the projected loss if the stop is hit and refuses when
        it would push the account past the daily or overall ceiling.
        """
        from policy.prop_firm.profile import SupportMode

        if self.profile.support_mode != SupportMode.AUTO_SUPPORTED:
            return OrderCheck(
                allowed=False,
                reason=f"Automation denied: support_mode={self.profile.support_mode.value}",
            )

        # BL-722: news blackout gate — only when the profile declares a
        # rule AND the caller flags the window as active.
        if is_news_blackout and self.profile.news_blackout is not None:
            return OrderCheck(allowed=False, reason="News blackout in effect")

        return self._check_projected_order(entry, stop, lots, contract_size)

    def check_replay_order(
        self, entry: float, stop: float, lots: float, contract_size: float
    ) -> OrderCheck:
        """Evaluate an order for historical replay without execution authority.

        ``RESEARCH_ONLY`` profiles remain blocked by :meth:`check_new_order`.
        This explicit path permits deterministic historical rule replay while
        preserving the live automation boundary.
        """
        return self._check_projected_order(entry, stop, lots, contract_size)

    def _check_projected_order(
        self, entry: float, stop: float, lots: float, contract_size: float
    ) -> OrderCheck:
        # BL-722: PAUSED challenges are blocked for the rest of the day,
        # with the specific pause message required by the pre-trade gate.
        if self.status == ChallengeStatus.PAUSED:
            return OrderCheck(
                allowed=False, reason="Trading paused for the day (daily loss limit hit)"
            )
        if self.status != ChallengeStatus.IN_PROGRESS:
            return OrderCheck(allowed=False, reason=f"Challenge already {self.status.value}")

        risk_per_lot = contract_size * abs(entry - stop)
        projected_loss = lots * risk_per_lot
        max_lots = self.max_position_size(entry, stop, contract_size)

        daily_limit_cash = self.daily_loss_limit_cash()
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

        overall_limit_cash = self.overall_loss_limit_cash()
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

        # Daily loss — hard (terminate) or soft_pause (suspend for the day)
        daily_used = self.daily_loss_used_pct()
        if self.daily_loss() >= self.daily_loss_limit_cash():
            if p.daily_loss_action == DailyLossAction.PAUSE:
                # BL-722: pause profile — daily limit suspends trading but
                # does NOT end the challenge; ``rollover`` resumes next day.
                breaches.append(
                    Breach(
                        type=BreachType.DAILY_LOSS,
                        severity="soft_pause",
                        message=(
                            f"Daily loss {self.daily_loss():.2f} >= limit "
                            f"{self.daily_loss_limit_cash():.2f}; "
                            f"trading paused for the day"
                        ),
                        used_pct=daily_used,
                    )
                )
            else:
                breaches.append(
                    Breach(
                        type=BreachType.DAILY_LOSS,
                        severity="hard",
                        message=(
                            f"Daily loss {self.daily_loss():.2f} >= limit "
                            f"{self.daily_loss_limit_cash():.2f}"
                        ),
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

        # Consistency — soft (per-day semantics, original behaviour preserved).
        # BL-722 history-aware check lives in :meth:`challenge_outcome`
        # where the question is "is the challenge ready to pass?", not
        # "is the live account in breach right now?".
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
                        f"Today's profit {share:.0%} of total exceeds "
                        f"consistency limit {p.consistency_pct:.0%}"
                    ),
                    used_pct=share,
                )
            )

        # BL-722: payout buffer — soft breach when realised profit
        # hasn't reached the buffer gate yet.
        if p.payout_buffer_pct > 0:
            current_profit = s.current_balance - s.initial_balance
            threshold = p.payout_buffer_pct * s.initial_balance
            if current_profit < threshold:
                breaches.append(
                    Breach(
                        type=BreachType.PAYOUT_BUFFER,
                        severity="soft",
                        message=(
                            f"Profit {current_profit:.2f} below payout "
                            f"buffer {threshold:.2f} "
                            f"({p.payout_buffer_pct:.0%} of initial)"
                        ),
                        used_pct=current_profit / threshold if threshold > 0 else 0.0,
                    )
                )

        # Promote status from hard / soft_pause breaches.
        has_hard = any(b.severity == "hard" for b in breaches)
        has_pause = any(b.severity == "soft_pause" for b in breaches)
        if has_hard:
            if any(b.type == BreachType.DAILY_LOSS for b in breaches):
                self.status = ChallengeStatus.FAILED_DAILY
            else:
                self.status = ChallengeStatus.FAILED_OVERALL
        elif has_pause:
            self.status = ChallengeStatus.PAUSED

        return breaches

    def challenge_outcome(self) -> ChallengeStatus:
        """Return the terminal status, evaluating pass conditions lazily.

        BL-722: the consistency rule blocks PASSED transitions while the
        best-ever day (across the full ``day_profits`` history plus the
        in-progress ``today_profit``) still exceeds
        ``consistency_pct`` of total profit.  Trading continues (status
        stays ``IN_PROGRESS``); additional profitable days eventually
        dilute the share and the challenge can pass.

        BL-722: ``payout_buffer_pct`` gates the PASSED transition on the
        realised profit meeting the firm-declared buffer (e.g. E8-style
        "what you keep" payouts).
        """
        if self.status != ChallengeStatus.IN_PROGRESS:
            return self.status
        s = self.state
        p = self.profile
        target_balance = round(s.initial_balance * (1.0 + p.profit_target_pct), 2)
        days_ok = s.trading_days + (1 if s.today_has_trade else 0) >= p.min_trading_days
        # BL-722: consistency rule blocks PASSED until best day is diluted.
        # best_day = max(day_profits + [today_profit]) — historical max
        # combined with the in-progress day.
        if p.consistency_pct > 0.0 and s.total_profit > 0:
            best_day = max(s.max_day_profit, s.today_profit)
            if s.day_profits:
                best_day = max(best_day, max(s.day_profits))
            if best_day / s.total_profit > p.consistency_pct:
                return ChallengeStatus.IN_PROGRESS
        # BL-722: payout buffer — pass only after realised profit clears
        # the buffer gate (firm-specific "what you keep" requirement).
        if p.payout_buffer_pct > 0.0:
            realised = s.current_balance - s.initial_balance
            if realised < p.payout_buffer_pct * s.initial_balance:
                return ChallengeStatus.IN_PROGRESS
        if s.current_balance >= target_balance and days_ok:
            self.status = ChallengeStatus.PASSED
        return self.status

    # ------------------------------------------------------------------
    # Anti-HFT (BL-722)
    # ------------------------------------------------------------------
    def check_trade_duration(self, duration_s: float) -> OrderCheck:
        """Anti-HFT gate: reject orders/trades below the firm-declared
        minimum average duration (BL-722).

        ``duration_s`` is the elapsed seconds for the candidate trade.
        Profiles that do not declare ``min_trade_duration_minutes`` are
        unrestricted.  Otherwise trades shorter than the floor are
        blocked with a descriptive reason.
        """
        min_minutes = self.profile.min_trade_duration_minutes
        if min_minutes <= 0.0:
            return OrderCheck(allowed=True, reason="No anti-HFT rule declared")
        min_s = min_minutes * 60.0
        if duration_s < min_s:
            return OrderCheck(
                allowed=False,
                reason=(
                    f"Trade duration {duration_s:.1f}s < anti-HFT min "
                    f"{min_minutes:.2f} min ({min_s:.0f}s)"
                ),
            )
        return OrderCheck(allowed=True)

    def record_trade_with_duration(
        self, realized_pnl: float, duration_minutes: float
    ) -> Breach | None:
        """Record a closed trade AND enforce the anti-HFT duration rule.

        Combines :meth:`record_trade` with the duration check and returns
        a soft ``ANTI_HFT`` ``Breach`` when the trade closed below
        ``profile.min_trade_duration_minutes``.  ``None`` when compliant
        (or when no anti-HFT rule was declared by the firm).
        """
        self.record_trade(realized_pnl)
        self.state.current_trade_pnl = realized_pnl
        min_minutes = self.profile.min_trade_duration_minutes
        if min_minutes <= 0.0:
            return None
        if duration_minutes < min_minutes:
            return Breach(
                type=BreachType.ANTI_HFT,
                severity="soft",
                message=(
                    f"Trade closed after {duration_minutes:.2f} min, below "
                    f"anti-HFT floor {min_minutes:.2f} min"
                ),
                used_pct=duration_minutes / min_minutes,
            )
        return None

    # ------------------------------------------------------------------
    # News blackout (BL-722) — calendar-driven check
    # ------------------------------------------------------------------
    def is_in_news_blackout(self, timestamp_s: float, news_events: list[tuple[float, str]]) -> bool:
        """Return True if ``timestamp_s`` falls inside any news blackout.

        ``news_events`` is a list of ``(event_epoch_seconds, instrument_id)``
        tuples — typically loaded from the BL-724 economic calendar.  Each
        event blocks trading for ``[event - before_minutes, event +
        after_minutes]`` per ``profile.news_blackout``.  Empty event list
        or ``news_blackout=None`` always returns ``False``.
        """
        if self.profile.news_blackout is None:
            return False
        if not news_events:
            return False
        before_s = self.profile.news_blackout.before_minutes * 60.0
        after_s = self.profile.news_blackout.after_minutes * 60.0
        for event_ts, _instrument in news_events:
            if (event_ts - before_s) <= timestamp_s <= (event_ts + after_s):
                return True
        return False

    def check_news_blackout(
        self, timestamp_s: float, news_events: list[tuple[float, str]]
    ) -> OrderCheck:
        """Pre-trade news-blackout gate (BL-722).

        Convenience wrapper around :meth:`is_in_news_blackout` that returns
        an ``OrderCheck`` so callers can short-circuit an order without
        duplicating the calendar/window math.
        """
        if self.profile.news_blackout is None:
            return OrderCheck(allowed=True)
        if self.is_in_news_blackout(timestamp_s, news_events):
            return OrderCheck(
                allowed=False,
                reason=(
                    f"Order blocked: timestamp {timestamp_s:.0f} falls inside news blackout window"
                ),
            )
        return OrderCheck(allowed=True)

    # ------------------------------------------------------------------
    # Consistency — real-time pre-trade warning (BL-722)
    # ------------------------------------------------------------------
    def consistency_pre_trade_warning(self, projected_day_profit: float) -> Breach | None:
        """Pre-trade check: would adding ``projected_day_profit`` breach
        the consistency rule?

        Returns a soft ``CONSISTENCY`` ``Breach`` if today's projected
        share would exceed ``profile.consistency_pct`` of total profit.
        ``None`` when compliant (or when no consistency rule declared).
        """
        p = self.profile
        s = self.state
        if p.consistency_pct <= 0.0:
            return None
        projected_today = s.today_profit + projected_day_profit
        projected_total = s.total_profit + projected_day_profit
        if projected_today <= 0 or projected_total <= 0:
            return None
        share = projected_today / projected_total
        if share <= p.consistency_pct:
            return None
        return Breach(
            type=BreachType.CONSISTENCY,
            severity="soft",
            message=(
                f"Projected today-profit {share:.0%} of total would exceed "
                f"consistency limit {p.consistency_pct:.0%}"
            ),
            used_pct=share,
        )

    # ------------------------------------------------------------------
    # Payout buffer (BL-722)
    # ------------------------------------------------------------------
    def payout_unlocked(self) -> bool:
        """Whether realised profit has cleared the payout buffer.

        Returns ``True`` when ``profile.payout_buffer_pct == 0`` (no
        buffer declared) or when ``current_balance - initial_balance``
        is at or above the buffer threshold.
        """
        p = self.profile
        if p.payout_buffer_pct <= 0.0:
            return True
        threshold = p.payout_buffer_pct * self.state.initial_balance
        return (self.state.current_balance - self.state.initial_balance) >= threshold
