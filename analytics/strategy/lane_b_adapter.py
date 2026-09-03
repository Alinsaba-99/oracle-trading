"""BL-728 — Lane B signal adapter for the PaperOrchestrator.

Translates the pre-registered Lane B composite screen
(Piotroski 40% + Greenblatt 40% + Lakonishok 20%, threshold 0.65,
top-N = 15) into :class:`OrderIntent` objects that the
:class:`~execution.paper_orchestrator.PaperOrchestrator` can submit to
the paper broker.

Architectural placement
-----------------------
The adapter lives in ``analytics/strategy/`` because its primary input
is the pre-registered fundamental composite score from
:mod:`analytics.strategy.catalog.value`.  Per
``tests/unit/test_architecture_boundaries.py`` the ``analytics`` package
is allowed to import from ``execution`` (the P2 parity-port exception is
tracked there), so importing :class:`OrderIntent` from
:mod:`execution.paper_orchestrator` is the established pattern (see
``analytics/qualification/execution.py`` for a precedent).

Lookahead safety
----------------
The adapter does NOT touch network resources.  It receives
already-merged fundamental signals + price data from the caller and
selects the most recent ``publish_date <= as_of_date`` per SimFinId.
This mirrors the discipline used in
:mod:`analytics.strategy.lane_b_backtester`.

Stop-loss tracking
------------------
The adapter maintains an in-memory dict of :class:`LaneBPosition`
records so it can emit ``sell`` intents when a held position drops
``per_idea_stop_loss_pct`` from its entry price.  The caller is
expected to call :meth:`register_entry` whenever an entry intent is
filled, and to pass the live ``current_prices`` dict at every rebalance.

Usage
-----
    from datetime import datetime
    from decimal import Decimal

    from analytics.strategy.lane_b_adapter import (
        LaneBSignalAdapter,
        LaneBSignalAdapterConfig,
    )

    adapter = LaneBSignalAdapter()
    holdings = adapter.screen_universe(
        as_of_date=datetime(2024, 1, 1),
        merged=merged_signals,   # SimFinId, publish_date, f_score, magic_formula_rank, return_12m
        prices=price_history,    # SimFinId, date, Close
        companies=companies_df,  # SimFinId, Ticker
    )
    intents = adapter.generate_rebalance_intents(
        current_positions={"AAPL": Decimal("10")},
        current_prices={"AAPL": Decimal("150.00")},
        portfolio_nav=Decimal("100000"),
        as_of_date="2024-01-01",
        target_holdings=holdings,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

import polars as pl

from analytics.strategy.catalog.value import CompositeLaneBScore
from execution.paper_orchestrator import OrderIntent

#: Default top-N holdings (ADR-019 v2 — was 25 in v1, tightened to 15
#: to bring Max DD below 35%).
DEFAULT_TOP_N_HOLDINGS = 15

#: Default composite threshold (the registered Screen from
#: :class:`~analytics.strategy.catalog.value.CompositeLaneBScore`).
DEFAULT_MIN_COMPOSITE_THRESHOLD = 0.65

#: Default composite weights — Piotroski 40%, Greenblatt 40%, Lakonishok 20%.
DEFAULT_COMPOSITE_WEIGHTS: tuple[float, float, float] = (0.40, 0.40, 0.20)

#: Default Lakonishok band — return_12m must be in ``[-20%, +50%]``.
DEFAULT_COMPOSITE_RETURN_BAND: tuple[float, float] = (-0.20, 0.50)

#: Default per-idea stop-loss — exit when drawdown from entry exceeds 5%.
DEFAULT_PER_IDEA_STOP_LOSS_PCT = Decimal("0.05")

#: Default strategy tag stamped on every emitted :class:`OrderIntent`.
DEFAULT_STRATEGY_TAG = "lane_b_composite"

#: Quantisation step for share quantities (1 share — no fractional shares).
_QUANTITY_STEP = Decimal("1")


@dataclass(frozen=True)
class LaneBSignalAdapterConfig:
    """Lane B adapter configuration.

    Attributes
    ----------
    top_n_holdings : int
        Number of holdings after the composite screen (default 15, ADR-019 v2).
    min_composite_threshold : float
        Minimum composite score to qualify (default 0.65).
    composite_weights : tuple[float, float, float]
        Weights for ``(Piotroski F, Greenblatt rank, Lakonishok return_12m)``.
    composite_return_band : tuple[float, float]
        Lakonishok band — return_12m outside the band is clamped to 0/1.
    per_idea_stop_loss_pct : Decimal | None
        Per-idea stop-loss as a fraction of the entry price (e.g.
        ``Decimal("0.05")`` = -5%).  ``None`` disables stop-loss tracking.
    strategy : str
        Strategy tag stamped on every emitted :class:`OrderIntent`.
    """

    top_n_holdings: int = DEFAULT_TOP_N_HOLDINGS
    min_composite_threshold: float = DEFAULT_MIN_COMPOSITE_THRESHOLD
    composite_weights: tuple[float, float, float] = DEFAULT_COMPOSITE_WEIGHTS
    composite_return_band: tuple[float, float] = DEFAULT_COMPOSITE_RETURN_BAND
    per_idea_stop_loss_pct: Decimal | None = DEFAULT_PER_IDEA_STOP_LOSS_PCT
    strategy: str = DEFAULT_STRATEGY_TAG

    def __post_init__(self) -> None:
        if self.top_n_holdings <= 0:
            raise ValueError(f"top_n_holdings must be positive (got {self.top_n_holdings})")
        total_w = sum(self.composite_weights)
        if abs(total_w - 1.0) >= 1e-6:
            raise ValueError(f"composite_weights must sum to 1.0 (got {total_w:.4f})")
        if self.min_composite_threshold < 0 or self.min_composite_threshold > 1:
            raise ValueError(
                f"min_composite_threshold must be in [0, 1] (got {self.min_composite_threshold})"
            )


@dataclass(frozen=True)
class LaneBTargetHolding:
    """One target holding produced by the screen.

    Attributes
    ----------
    ticker : str
        Stock ticker (e.g. "AAPL").
    simfin_id : int | None
        SimFinId from the source data (``None`` if the caller did not
        pass a ``companies`` lookup).
    backtest_price : Decimal
        As-of closing price used as the entry reference (no lookahead).
    composite_score : float | None
        Composite score (0..1) — ``None`` if the row had missing signals.
    composite_rank : int | None
        Cross-sectional rank of the composite score (lower = better,
    ``1`` = best in the cross-section).
    """

    ticker: str
    simfin_id: int | None
    backtest_price: Decimal
    composite_score: float | None = None
    composite_rank: int | None = None


@dataclass
class LaneBPosition:
    """In-memory tracking state for an active Lane B position.

    Used by :meth:`LaneBSignalAdapter.generate_rebalance_intents` to
    emit stop-loss ``sell`` intents when a held position drops
    ``per_idea_stop_loss_pct`` from its entry price.

    Attributes
    ----------
    ticker : str
        Stock ticker.
    simfin_id : int | None
        SimFinId from the source data.
    entry_price : Decimal
        Price recorded when the position was opened.
    quantity : Decimal
        Quantity currently held.
    composite_score : float | None
        Composite score at the time of entry (for the audit trail).
    composite_rank : int | None
        Cross-sectional rank at the time of entry.
    entry_date : str
        ISO-8601 UTC timestamp of the entry fill.
    """

    ticker: str
    simfin_id: int | None
    entry_price: Decimal
    quantity: Decimal
    composite_score: float | None = None
    composite_rank: int | None = None
    entry_date: str = ""

    def is_stop_breached(self, current_price: Decimal, stop_loss_pct: Decimal | None) -> bool:
        """Return ``True`` if ``current_price <= entry_price * (1 - stop_loss_pct)``.

        A ``None`` stop_loss_pct (or zero / negative) means stop-loss is
        disabled; the method returns ``False``.
        """
        if stop_loss_pct is None or stop_loss_pct <= 0:
            return False
        if self.entry_price <= 0:
            return False
        threshold = self.entry_price * (Decimal("1") - stop_loss_pct)
        return current_price <= threshold


class LaneBSignalAdapter:
    """Adapter that converts the Lane B composite screen to OrderIntents.

    The adapter is intentionally stateless w.r.t. fundamental data —
    callers pass in pre-built cross-sections so it can be tested
    deterministically without touching the network or SimFin's bulk
    download.

    Lifecycle
    ---------
    1. Construct with a :class:`LaneBSignalAdapterConfig` (defaults to
       the pre-registered ADR-019 Lane B composite screen).
    2. Call :meth:`screen_universe` with the merged fundamental signals
       + price history to produce a list of :class:`LaneBTargetHolding`.
    3. Call :meth:`generate_rebalance_intents` to translate the
       target list (plus active positions + current prices) into a list
       of :class:`OrderIntent` ready for the orchestrator.
    4. After fills, call :meth:`register_entry` /
       :meth:`unregister_position` to keep the in-memory stop-loss
       tracker in sync with the live book.

    The adapter is NOT a singleton — create one per strategy instance.
    """

    def __init__(self, config: LaneBSignalAdapterConfig | None = None) -> None:
        self.config = config or LaneBSignalAdapterConfig()
        self._composite = CompositeLaneBScore(
            w_f_score=self.config.composite_weights[0],
            w_magic_rank=self.config.composite_weights[1],
            w_return_12m=self.config.composite_weights[2],
            return_band_min=self.config.composite_return_band[0],
            return_band_max=self.config.composite_return_band[1],
            min_composite_threshold=self.config.min_composite_threshold,
        )
        self._active_positions: dict[str, LaneBPosition] = {}

    # ------------------------------------------------------------------
    # Public surface — screen + rebalance
    # ------------------------------------------------------------------
    def screen_universe(
        self,
        *,
        as_of_date: datetime,
        merged: pl.DataFrame,
        prices: pl.DataFrame,
        companies: pl.DataFrame | None = None,
    ) -> list[LaneBTargetHolding]:
        """Screen the universe at ``as_of_date`` using cached fundamental signals.

        Parameters
        ----------
        as_of_date : datetime
            The point-in-time cut-off.  Only ``publish_date <= as_of_date``
            rows are considered — this is the anti-lookahead invariant.
        merged : pl.DataFrame
            Pre-merged fundamental signals (typically produced by
            :meth:`LaneBBacktester._compute_piotroski_signals` +
            ``_compute_greenblatt_signals`` + the 12-month return join).
            Required columns: ``SimFinId``, ``publish_date``,
            ``f_score``, ``magic_formula_rank``, ``return_12m``.
        prices : pl.DataFrame
            Per-``(SimFinId, date)`` close price history.  Required
            columns: ``SimFinId``, ``date``, ``Close``.  Only the price
            on or before ``as_of_date`` is used for ``backtest_price``.
        companies : pl.DataFrame | None
            Optional ``SimFinId -> Ticker`` lookup (produced by
            :meth:`SimFinLoader.companies`).  If ``None``, the returned
            :class:`LaneBTargetHolding` will use the SimFinId stringified
            as the ticker — useful in tests that don't care about
            human-readable tickers.

        Returns
        -------
        list[LaneBTargetHolding]
            Top-N target holdings sorted by ``composite_rank``
            (ascending — lower rank is better).  Empty list if the
            screen produced no qualifying names.
        """
        if merged.height == 0:
            return []

        # 1. Filter to the most recent publish_date per SimFinId
        #    on or before as_of_date (anti-lookahead).
        as_of_naive = as_of_date.replace(tzinfo=None) if as_of_date.tzinfo else as_of_date
        recent = merged.filter(pl.col("publish_date") <= as_of_naive)
        if recent.height == 0:
            return []
        # Most recent per SimFinId
        recent = recent.sort("publish_date", descending=True).group_by("SimFinId").first()

        # 2. Score with CompositeLaneBScore and filter by threshold.
        scored = self._composite.score(recent)
        screened = self._composite.screen(scored)
        if screened.height == 0:
            return []

        # 3. Sort by composite_rank (ascending) and take top-N.
        screened = screened.sort("composite_rank").head(self.config.top_n_holdings)

        # 4. Join price as-of as_of_date per SimFinId.
        price_as_of = self._price_at_or_before(prices, as_of_naive)
        if price_as_of is None or price_as_of.height == 0:
            return []

        screened_with_price = screened.join(price_as_of, on="SimFinId", how="inner")
        if screened_with_price.height == 0:
            return []

        # 5. Join ticker if companies provided.
        if companies is not None:
            comp_min = companies.select(
                [pl.col("SimFinId"), pl.col("Ticker").alias("Ticker_lookup")]
            )
            screened_with_price = screened_with_price.join(comp_min, on="SimFinId", how="left")

        # 6. Build LaneBTargetHolding list.
        holdings: list[LaneBTargetHolding] = []
        for row in screened_with_price.iter_rows(named=True):
            simfin_id = int(row["SimFinId"])
            if "Ticker_lookup" in row and row["Ticker_lookup"] is not None:
                ticker = str(row["Ticker_lookup"])
            else:
                ticker = str(simfin_id)
            close_val = row.get("Close")
            if close_val is None:
                continue
            try:
                backtest_price = Decimal(str(close_val))
            except Exception:
                continue

            composite_score_raw = row.get("composite_score")
            composite_score: float | None
            if composite_score_raw is None:
                composite_score = None
            else:
                try:
                    composite_score = float(composite_score_raw)
                except (TypeError, ValueError):
                    composite_score = None

            composite_rank_raw = row.get("composite_rank")
            composite_rank: int | None
            if composite_rank_raw is None:
                composite_rank = None
            else:
                try:
                    composite_rank = int(composite_rank_raw)
                except (TypeError, ValueError):
                    composite_rank = None

            holdings.append(
                LaneBTargetHolding(
                    ticker=ticker,
                    simfin_id=simfin_id,
                    backtest_price=backtest_price,
                    composite_score=composite_score,
                    composite_rank=composite_rank,
                )
            )

        # Re-sort by composite_rank (None treated as worst).
        holdings.sort(
            key=lambda h: (h.composite_rank if h.composite_rank is not None else 10**9, h.ticker)
        )
        return holdings

    def generate_rebalance_intents(
        self,
        *,
        current_positions: dict[str, Decimal],
        current_prices: dict[str, Decimal],
        portfolio_nav: Decimal,
        as_of_date: str,
        target_holdings: list[LaneBTargetHolding],
    ) -> list[OrderIntent]:
        """Generate :class:`OrderIntent` objects to rebalance to ``target_holdings``.

        Algorithm
        ---------
        1. Emit SELL intents first for any ticker that:
           - is currently held AND no longer in the target list, OR
           - is currently held AND its stop-loss has been breached.
        2. Compute target weight per holding = ``1 / top_n_holdings``
           (equal-weight), so the gross allocation is ``<= 1.0``.
        3. For each target holding:
           - If the ticker is not currently held → BUY up to the target
             notional, floored to whole shares.
           - If the ticker is currently held at a quantity below the
             target → BUY the difference (top-up).
           - If the ticker is currently held at a quantity above the
             target → SELL the difference (trim).
        4. All quantities are Decimal with ``ROUND_DOWN`` for buys and
           ``ROUND_DOWN`` for sells (whole shares only).

        Parameters
        ----------
        current_positions : dict[str, Decimal]
            Live position book — ticker → current quantity.
        current_prices : dict[str, Decimal]
            Latest prices — ticker → current price (used for
            backtest_price and for stop-loss evaluation).
        portfolio_nav : Decimal
            Total account equity (cash + mark-to-market positions).
        as_of_date : str
            ISO-8601 date stamp included in every emitted intent's
            ``meta`` for the audit trail.
        target_holdings : list[LaneBTargetHolding]
            Output of :meth:`screen_universe` for this rebalance cycle.

        Returns
        -------
        list[OrderIntent]
            SELL intents first (frees cash), then BUY intents.  Empty
            list if the current book already matches the target (HOLD).
        """
        intents: list[OrderIntent] = []

        if portfolio_nav <= 0:
            raise ValueError(f"portfolio_nav must be positive (got {portfolio_nav})")

        # 1. Build target set + lookup by ticker.
        target_by_ticker: dict[str, LaneBTargetHolding] = {h.ticker: h for h in target_holdings}
        n_targets = len(target_holdings)
        if n_targets == 0:
            # Defensive: no target → exit every held name (and any
            # stop-loss breaches).  This is a "go to cash" signal.
            for ticker, qty in current_positions.items():
                if qty <= 0:
                    continue
                price = current_prices.get(ticker)
                if price is None or price <= 0:
                    continue
                intents.append(
                    self._make_intent(
                        ticker=ticker,
                        side="sell",
                        quantity=qty,
                        backtest_price=price,
                        as_of_date=as_of_date,
                        score=None,
                        rank=None,
                        reason="exited_target",
                    )
                )
            return intents

        # Equal-weight target per holding.  n_targets is bounded by
        # ``self.config.top_n_holdings`` so the sum is <= 1.0 by
        # construction (no overlap / leverage in this MVP).
        target_weight = Decimal("1") / Decimal(n_targets)
        # Defensive check: weights must sum to <= 1.0
        total_weight = target_weight * Decimal(n_targets)
        if total_weight > Decimal("1") + Decimal("0.0000001"):
            raise ValueError(f"target weights sum > 1.0 ({total_weight}) — adapter config error")

        target_value_per_holding = portfolio_nav * target_weight

        # 2. Stop-loss pass: emit SELL intents for any held ticker that
        # is BOTH in the target AND has breached the stop.  This must
        # happen before the rebalance math so a stop-loss exit isn't
        # masked by a top-up BUY in the same cycle.
        stopped_out_tickers: set[str] = set()
        if self.config.per_idea_stop_loss_pct is not None:
            for ticker, position in list(self._active_positions.items()):
                if ticker not in current_positions:
                    # The position has already been sold externally —
                    # remove from the in-memory tracker to keep it in
                    # sync with the live book.
                    self._active_positions.pop(ticker, None)
                    continue
                price = current_prices.get(ticker)
                if price is None:
                    continue
                if position.is_stop_breached(price, self.config.per_idea_stop_loss_pct):
                    qty = current_positions[ticker]
                    if qty <= 0:
                        continue
                    intents.append(
                        self._make_intent(
                            ticker=ticker,
                            side="sell",
                            quantity=qty,
                            backtest_price=price,
                            as_of_date=as_of_date,
                            score=position.composite_score,
                            rank=position.composite_rank,
                            reason="stop_loss",
                        )
                    )
                    # Mark as exited so the rebalance pass below treats
                    # it as "no longer held" and skips re-buying in the same cycle.
                    stopped_out_tickers.add(ticker)
                    current_positions = dict(current_positions)
                    current_positions[ticker] = Decimal("0")
                    self._active_positions.pop(ticker, None)

        # 3. SELL pass — tickers that are held but no longer in the
        # target list.
        for ticker, qty in current_positions.items():
            if qty <= 0:
                continue
            if ticker not in target_by_ticker:
                price = current_prices.get(ticker)
                if price is None or price <= 0:
                    continue
                intents.append(
                    self._make_intent(
                        ticker=ticker,
                        side="sell",
                        quantity=qty,
                        backtest_price=price,
                        as_of_date=as_of_date,
                        score=None,
                        rank=None,
                        reason="exited_target",
                    )
                )
                self._active_positions.pop(ticker, None)

        # 4. BUY + trim pass — for each target, compute the delta to
        # the target notional and emit the appropriate intent.
        for holding in target_holdings:
            ticker = holding.ticker
            if ticker in stopped_out_tickers:
                continue
            price = holding.backtest_price
            if price <= 0:
                continue
            target_quantity = (target_value_per_holding / price).quantize(
                _QUANTITY_STEP, rounding=ROUND_DOWN
            )
            current_qty = current_positions.get(ticker, Decimal("0"))
            delta = target_quantity - current_qty
            if delta == 0:
                continue
            if delta > 0:
                intents.append(
                    self._make_intent(
                        ticker=ticker,
                        side="buy",
                        quantity=delta,
                        backtest_price=price,
                        as_of_date=as_of_date,
                        score=holding.composite_score,
                        rank=holding.composite_rank,
                        reason="entry_or_topup",
                    )
                )
            else:
                # Trim — sell the excess (negative delta → positive qty).
                intents.append(
                    self._make_intent(
                        ticker=ticker,
                        side="sell",
                        quantity=-delta,
                        backtest_price=price,
                        as_of_date=as_of_date,
                        score=holding.composite_score,
                        rank=holding.composite_rank,
                        reason="rebalance_trim",
                    )
                )

        return intents

    # ------------------------------------------------------------------
    # Position tracking (stop-loss)
    # ------------------------------------------------------------------
    def register_entry(
        self,
        *,
        ticker: str,
        simfin_id: int | None,
        entry_price: Decimal,
        quantity: Decimal,
        composite_score: float | None,
        composite_rank: int | None,
        entry_date: str | None = None,
    ) -> None:
        """Record a new entry in the in-memory stop-loss tracker.

        Call this once an entry intent has been filled so that
        :meth:`generate_rebalance_intents` can monitor the position
        against :attr:`LaneBSignalAdapterConfig.per_idea_stop_loss_pct`.
        """
        if quantity <= 0:
            raise ValueError(f"quantity must be positive (got {quantity})")
        if entry_price <= 0:
            raise ValueError(f"entry_price must be positive (got {entry_price})")
        self._active_positions[ticker] = LaneBPosition(
            ticker=ticker,
            simfin_id=simfin_id,
            entry_price=entry_price,
            quantity=quantity,
            composite_score=composite_score,
            composite_rank=composite_rank,
            entry_date=entry_date or datetime.now(UTC).isoformat(),
        )

    def unregister_position(self, ticker: str) -> None:
        """Remove a ticker from the in-memory stop-loss tracker."""
        self._active_positions.pop(ticker, None)

    def active_positions(self) -> dict[str, LaneBPosition]:
        """Return a snapshot of the in-memory stop-loss tracker."""
        return dict(self._active_positions)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _price_at_or_before(prices: pl.DataFrame, as_of_date: datetime) -> pl.DataFrame | None:
        """Return the latest ``Close`` per SimFinId on or before ``as_of_date``.

        Returns ``None`` if the prices frame is empty or missing the
        required columns.
        """
        if prices.height == 0:
            return None
        cols = prices.columns
        if "SimFinId" not in cols or "Close" not in cols:
            return None
        date_col = "date" if "date" in cols else ("Date" if "Date" in cols else None)
        if date_col is None:
            return None
        pre = prices.filter(pl.col(date_col) <= as_of_date)
        if pre.height == 0:
            return None
        # Most recent date per SimFinId
        return (
            pre.sort(date_col, descending=True)
            .group_by("SimFinId")
            .first()
            .select(["SimFinId", "Close"])
        )

    def _make_intent(
        self,
        *,
        ticker: str,
        side: str,
        quantity: Decimal,
        backtest_price: Decimal,
        as_of_date: str,
        score: float | None,
        rank: int | None,
        reason: str,
    ) -> OrderIntent:
        """Build a single :class:`OrderIntent` with the canonical Lane B metadata."""
        meta: dict[str, Any] = {
            "screen_date": as_of_date,
            "strategy": self.config.strategy,
            "reason": reason,
        }
        if score is not None:
            meta["composite_score"] = float(score)
        if rank is not None:
            meta["composite_rank"] = int(rank)
        return OrderIntent(
            instrument_id=ticker,
            side=side,
            quantity=quantity,
            backtest_price=backtest_price,
            strategy=self.config.strategy,
            meta=meta,
        )


__all__: list[str] = [
    "DEFAULT_COMPOSITE_RETURN_BAND",
    "DEFAULT_COMPOSITE_WEIGHTS",
    "DEFAULT_MIN_COMPOSITE_THRESHOLD",
    "DEFAULT_PER_IDEA_STOP_LOSS_PCT",
    "DEFAULT_STRATEGY_TAG",
    "DEFAULT_TOP_N_HOLDINGS",
    "LaneBPosition",
    "LaneBSignalAdapter",
    "LaneBSignalAdapterConfig",
    "LaneBTargetHolding",
]
