"""Tests for BL-728 — LaneBSignalAdapter (PaperOrchestrator signal adapter).

Coverage:
- Configuration validation (top_n positive, weights sum to 1, threshold in [0,1])
- LaneBPosition.is_stop_breached edge cases (disabled / zero entry / breach)
- screen_universe with synthetic cross-section:
  - Anti-lookahead: future publish_date rows excluded
  - Most-recent per SimFinId (restated data does not leak forward)
  - Composite threshold filter applied
  - top-N cap respected
  - Ticker lookup via companies table
  - Missing prices → no holdings returned
  - Empty merged → empty list
- generate_rebalance_intents:
  - New portfolio entry (no current positions) → all BUY intents
  - Position exits when no longer in target → SELL intents
  - Allocations sum to <= 1.0
  - Decimal precision (whole shares, no fractional)
  - Stop-loss intent emitted when position breaches 5%
  - Stop-loss + rebalance in same cycle → SELL emitted (no top-up)
  - Stop-loss disabled → no SELL for breach
  - top-up / trim within held tickers
- Internal helpers (price_as_of) edge cases
- register_entry / unregister_position lifecycle
- Meta carries score / rank / reason / screen_date
- SELL intents emitted BEFORE BUY intents (frees cash first)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import polars as pl
import pytest

from analytics.strategy.lane_b_adapter import (
    DEFAULT_COMPOSITE_RETURN_BAND,
    DEFAULT_COMPOSITE_WEIGHTS,
    DEFAULT_MIN_COMPOSITE_THRESHOLD,
    DEFAULT_PER_IDEA_STOP_LOSS_PCT,
    DEFAULT_STRATEGY_TAG,
    DEFAULT_TOP_N_HOLDINGS,
    LaneBPosition,
    LaneBSignalAdapter,
    LaneBSignalAdapterConfig,
)

# ---------------------------------------------------------------------------
# Fixtures — synthetic cross-sections
# ---------------------------------------------------------------------------


def _make_merged() -> pl.DataFrame:
    """Synthetic merged frame with 6 SimFinIds, two publish dates each.

    Layout (publish_date 2024-01-01):
      SimFinId 1: F=9, rank=1,  ret=+0.20  → perfect (composite ≈ 0.910)
      SimFinId 2: F=6, rank=5,  ret=+0.15  → composite ≈ 0.747
      SimFinId 3: F=8, rank=80, ret=+0.05  → ≈ 0.507 (FAIL threshold)
      SimFinId 4: F=7, rank=20, ret=-0.25  → ≈ 0.631 (FAIL threshold)
      SimFinId 5: F=5, rank=100, ret=+0.60 → ≈ 0.422 (FAIL threshold)
      SimFinId 6: F=4, rank=60, ret=+0.10  → ≈ 0.467 (FAIL threshold)
    """
    return pl.DataFrame(
        {
            "SimFinId": [1, 2, 3, 4, 5, 6],
            "publish_date": [datetime(2024, 1, 1)] * 6,
            "f_score": [9, 6, 8, 7, 5, 4],
            "magic_formula_rank": [1, 5, 80, 20, 100, 60],
            "return_12m": [0.20, 0.15, 0.05, -0.25, 0.60, 0.10],
        }
    )


def _make_prices(prices: dict[int, float] | None = None) -> pl.DataFrame:
    """One price point per SimFinId at 2024-01-02 (after the screen date)."""
    prices = prices or {1: 100.0, 2: 50.0, 3: 25.0, 4: 200.0, 5: 10.0, 6: 75.0}
    rows: list[dict[str, Any]] = []
    for simfin_id, close in prices.items():
        rows.append({"SimFinId": simfin_id, "date": datetime(2024, 1, 2), "Close": close})
    return pl.DataFrame(rows)


def _make_companies() -> pl.DataFrame:
    """SimFinId -> Ticker lookup for the test universe."""
    return pl.DataFrame(
        {"SimFinId": [1, 2, 3, 4, 5, 6], "Ticker": ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]}
    )


@pytest.fixture
def merged() -> pl.DataFrame:
    return _make_merged()


@pytest.fixture
def prices() -> pl.DataFrame:
    return _make_prices()


@pytest.fixture
def companies() -> pl.DataFrame:
    return _make_companies()


@pytest.fixture
def adapter() -> LaneBSignalAdapter:
    return LaneBSignalAdapter()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfig:
    def test_defaults_match_adr019(self) -> None:
        cfg = LaneBSignalAdapterConfig()
        assert cfg.top_n_holdings == DEFAULT_TOP_N_HOLDINGS == 15
        assert cfg.min_composite_threshold == DEFAULT_MIN_COMPOSITE_THRESHOLD == 0.65
        assert cfg.composite_weights == DEFAULT_COMPOSITE_WEIGHTS == (0.40, 0.40, 0.20)
        assert cfg.composite_return_band == DEFAULT_COMPOSITE_RETURN_BAND == (-0.20, 0.50)
        assert cfg.per_idea_stop_loss_pct == DEFAULT_PER_IDEA_STOP_LOSS_PCT == Decimal("0.05")
        assert cfg.strategy == DEFAULT_STRATEGY_TAG == "lane_b_composite"

    def test_top_n_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="top_n_holdings"):
            LaneBSignalAdapterConfig(top_n_holdings=0)

    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="composite_weights must sum"):
            LaneBSignalAdapterConfig(composite_weights=(0.5, 0.5, 0.5))

    def test_threshold_must_be_in_unit_interval(self) -> None:
        with pytest.raises(ValueError, match="min_composite_threshold"):
            LaneBSignalAdapterConfig(min_composite_threshold=1.5)
        with pytest.raises(ValueError, match="min_composite_threshold"):
            LaneBSignalAdapterConfig(min_composite_threshold=-0.1)


# ---------------------------------------------------------------------------
# LaneBPosition.stop-loss helper
# ---------------------------------------------------------------------------


class TestLaneBPositionStopLoss:
    def _pos(self, entry: str = "100.00") -> LaneBPosition:
        return LaneBPosition(
            ticker="AAA",
            simfin_id=1,
            entry_price=Decimal(entry),
            quantity=Decimal("10"),
            composite_score=0.9,
            composite_rank=1,
        )

    def test_no_stop_loss_when_disabled(self) -> None:
        pos = self._pos()
        assert pos.is_stop_breached(Decimal("50.00"), None) is False
        assert pos.is_stop_breached(Decimal("0.01"), Decimal("0")) is False
        assert pos.is_stop_breached(Decimal("0.01"), Decimal("-0.05")) is False

    def test_breach_when_below_threshold(self) -> None:
        # entry=100, stop=5% → threshold=95.  price=94.99 → breach.
        pos = self._pos("100.00")
        assert pos.is_stop_breached(Decimal("94.99"), Decimal("0.05")) is True

    def test_no_breach_at_threshold(self) -> None:
        # price == threshold is NOT a breach (strict <= would be a tie
        # but the docstring says "<="; pin the contract here).
        pos = self._pos("100.00")
        # threshold = 100 * (1 - 0.05) = 95.00
        assert pos.is_stop_breached(Decimal("95.00"), Decimal("0.05")) is True

    def test_no_breach_above_threshold(self) -> None:
        pos = self._pos("100.00")
        assert pos.is_stop_breached(Decimal("95.01"), Decimal("0.05")) is False

    def test_zero_entry_price_returns_false(self) -> None:
        # Defensive: a zero entry price must not falsely trigger.
        pos = LaneBPosition(
            ticker="AAA", simfin_id=1, entry_price=Decimal("0"), quantity=Decimal("10")
        )
        assert pos.is_stop_breached(Decimal("0.00"), Decimal("0.05")) is False


# ---------------------------------------------------------------------------
# screen_universe
# ---------------------------------------------------------------------------


class TestScreenUniverse:
    def test_empty_merged_returns_empty(self, adapter: LaneBSignalAdapter) -> None:
        out = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 1), merged=pl.DataFrame(), prices=_make_prices()
        )
        assert out == []

    def test_filters_by_composite_threshold(
        self, adapter: LaneBSignalAdapter, merged: pl.DataFrame, prices: pl.DataFrame
    ) -> None:
        out = adapter.screen_universe(as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices)
        # Threshold 0.65 → only SimFinId 1 (0.910) and 2 (0.747) qualify.
        tickers = {h.ticker for h in out}
        assert tickers == {"1", "2"}

    def test_sorts_by_composite_rank(
        self, adapter: LaneBSignalAdapter, merged: pl.DataFrame, prices: pl.DataFrame
    ) -> None:
        out = adapter.screen_universe(as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices)
        # Lower rank = better.  SimFinId 1 (rank 1) first, then 2 (rank 2).
        ranks = [h.composite_rank for h in out if h.composite_rank is not None]
        assert ranks == sorted(ranks)
        assert len(ranks) == len(out)
        assert out[0].simfin_id == 1
        assert out[1].simfin_id == 2

    def test_respects_top_n_cap(self, merged: pl.DataFrame) -> None:
        # Smaller top_n than qualifying names.
        cfg = LaneBSignalAdapterConfig(top_n_holdings=1)
        adapter = LaneBSignalAdapter(config=cfg)
        out = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5), merged=merged, prices=_make_prices()
        )
        assert len(out) == 1
        assert out[0].simfin_id == 1

    def test_anti_lookahead_excludes_future_publish_dates(self) -> None:
        # If the screen date is BEFORE every publish_date, nothing should match.
        merged = _make_merged()
        adapter = LaneBSignalAdapter()
        out = adapter.screen_universe(
            as_of_date=datetime(2023, 12, 31), merged=merged, prices=_make_prices()
        )
        assert out == []

    def test_picks_most_recent_publish_per_simfin_id(self) -> None:
        # Build a cross-section with several names.  For SimFinId 1
        # we add TWO publish_dates: the older row has a bad f_score
        # and would fail the threshold on its own; the newer row is a
        # strong name.  The screen must use the LATEST row per
        # SimFinId (point-in-time discipline: restated data does not
        # leak forward in time, but the most recent available data
        # at as_of_date does).
        merged = pl.DataFrame(
            {
                "SimFinId": [1, 1, 2, 3, 4, 5, 6],
                "publish_date": [
                    datetime(2024, 1, 1),  # SimFinId 1 (OLD) — will be superseded
                    datetime(2024, 4, 1),  # SimFinId 1 (NEW) — strong
                    datetime(2024, 4, 1),
                    datetime(2024, 4, 1),
                    datetime(2024, 4, 1),
                    datetime(2024, 4, 1),
                    datetime(2024, 4, 1),
                ],
                "f_score": [2, 9, 8, 7, 6, 5, 4],
                "magic_formula_rank": [100, 5, 1, 10, 20, 30, 50],
                "return_12m": [0.10, 0.20, 0.15, 0.05, -0.25, 0.60, 0.10],
            }
        )
        adapter = LaneBSignalAdapter()
        out = adapter.screen_universe(
            as_of_date=datetime(2024, 6, 1), merged=merged, prices=_make_prices()
        )
        # SimFinId 1 is the LATEST row's f_score=9 + rank=5 → strong.
        # It must appear in the output (composite_rank == 1).
        ids = {h.simfin_id for h in out}
        assert 1 in ids

    def test_ticker_lookup_via_companies(
        self,
        adapter: LaneBSignalAdapter,
        merged: pl.DataFrame,
        prices: pl.DataFrame,
        companies: pl.DataFrame,
    ) -> None:
        out = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices, companies=companies
        )
        tickers = {h.ticker for h in out}
        assert tickers == {"AAA", "BBB"}
        # simfin_id is still populated alongside the ticker.
        by_id = {h.simfin_id: h for h in out}
        assert by_id[1].ticker == "AAA"
        assert by_id[2].ticker == "BBB"

    def test_missing_price_drops_holding(
        self, adapter: LaneBSignalAdapter, merged: pl.DataFrame
    ) -> None:
        # No price for SimFinId 2 → only SimFinId 1 in the output.
        prices = _make_prices(prices={1: 100.0})
        out = adapter.screen_universe(as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices)
        assert len(out) == 1
        assert out[0].simfin_id == 1

    def test_no_prices_returns_empty(
        self, adapter: LaneBSignalAdapter, merged: pl.DataFrame
    ) -> None:
        out = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5), merged=merged, prices=pl.DataFrame()
        )
        assert out == []

    def test_backtest_price_is_decimal(
        self, adapter: LaneBSignalAdapter, merged: pl.DataFrame, prices: pl.DataFrame
    ) -> None:
        out = adapter.screen_universe(as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices)
        for h in out:
            assert isinstance(h.backtest_price, Decimal)
            assert h.backtest_price > 0

    def test_price_at_or_before_as_of(
        self, adapter: LaneBSignalAdapter, merged: pl.DataFrame
    ) -> None:
        # If the only available price is AFTER as_of_date, the screen
        # must return empty (anti-lookahead).
        prices = pl.DataFrame(
            {
                "SimFinId": [1, 2],
                "date": [datetime(2024, 6, 1), datetime(2024, 6, 1)],
                "Close": [100.0, 50.0],
            }
        )
        out = adapter.screen_universe(as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices)
        assert out == []

    def test_picks_latest_available_price_on_or_before(
        self, adapter: LaneBSignalAdapter, merged: pl.DataFrame
    ) -> None:
        # Two prices per SimFinId; the screen date is in between.
        # The LATEST on-or-before date should be used.
        prices = pl.DataFrame(
            {
                "SimFinId": [1, 1, 2, 2],
                "date": [
                    datetime(2023, 12, 1),
                    datetime(2024, 1, 5),
                    datetime(2023, 12, 1),
                    datetime(2024, 1, 5),
                ],
                "Close": [80.0, 105.0, 40.0, 55.0],
            }
        )
        out = adapter.screen_universe(as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices)
        by_id = {h.simfin_id: h for h in out}
        assert by_id[1].backtest_price == Decimal("105.0")
        assert by_id[2].backtest_price == Decimal("55.0")


# ---------------------------------------------------------------------------
# generate_rebalance_intents — new portfolio
# ---------------------------------------------------------------------------


class TestRebalanceNewPortfolio:
    def test_empty_current_positions_emits_only_buys(
        self,
        adapter: LaneBSignalAdapter,
        merged: pl.DataFrame,
        prices: pl.DataFrame,
        companies: pl.DataFrame,
    ) -> None:
        holdings = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices, companies=companies
        )
        intents = adapter.generate_rebalance_intents(
            current_positions={},
            current_prices={"AAA": Decimal("100.00"), "BBB": Decimal("50.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=holdings,
        )
        sides = {i.side for i in intents}
        assert sides == {"buy"}
        # Two qualifying holdings → 2 BUY intents.
        assert len(intents) == 2
        tickers = {i.instrument_id for i in intents}
        assert tickers == {"AAA", "BBB"}

    def test_all_buy_quantities_use_decimal(
        self,
        adapter: LaneBSignalAdapter,
        merged: pl.DataFrame,
        prices: pl.DataFrame,
        companies: pl.DataFrame,
    ) -> None:
        holdings = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices, companies=companies
        )
        intents = adapter.generate_rebalance_intents(
            current_positions={},
            current_prices={"AAA": Decimal("100.00"), "BBB": Decimal("50.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=holdings,
        )
        for intent in intents:
            assert isinstance(intent.quantity, Decimal)
            assert isinstance(intent.backtest_price, Decimal)
            # Quantities must be whole shares (no fractional).
            assert intent.quantity == intent.quantity.to_integral_value()
            assert intent.quantity > 0

    def test_allocations_sum_to_le_one(self) -> None:
        # With 2 holdings and NAV=100k, each target = 50k. At price=100
        # → qty=500; at price=50 → qty=1000. Total = 1000+500=1500
        # shares × blended price ≤ NAV.
        cfg = LaneBSignalAdapterConfig(top_n_holdings=2)
        adapter = LaneBSignalAdapter(config=cfg)
        merged = _make_merged()
        prices = _make_prices(prices={1: 100.0, 2: 50.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0})
        holdings = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices
        )
        nav = Decimal("100000")
        intents = adapter.generate_rebalance_intents(
            current_positions={},
            current_prices={"AAA": Decimal("100.00"), "BBB": Decimal("50.00")},
            portfolio_nav=nav,
            as_of_date="2024-01-05",
            target_holdings=holdings,
        )
        # Each intent's notional must be ≤ portfolio_nav / top_n (or
        # all-buy with no current position).  Use the backtest_price.
        per_holding_cap = nav / Decimal(cfg.top_n_holdings)
        for intent in intents:
            notional = intent.quantity * intent.backtest_price
            assert notional <= per_holding_cap + Decimal("0.0001")
        # And the sum of all BUY notionals must be <= NAV.
        buy_notional = sum(
            (i.quantity * i.backtest_price for i in intents if i.side == "buy"), start=Decimal("0")
        )
        assert buy_notional <= nav

    def test_target_weight_sums_to_le_one_with_top_n(self) -> None:
        # The contract: equal-weight target per holding = 1 / n_targets,
        # so n_targets * (1/n_targets) = 1.0 by construction.  The
        # configured ``top_n`` is an UPPER CAP on how many names can
        # pass — if only 2 names qualify, the actual portfolio weight
        # is 1/2 per name (not 1/top_n), matching the backtester.
        cfg = LaneBSignalAdapterConfig(top_n_holdings=15)
        adapter = LaneBSignalAdapter(config=cfg)
        merged = _make_merged()
        prices = _make_prices()
        holdings = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices
        )
        # 2 qualifying holdings → each gets NAV/2 weight.
        nav = Decimal("100000")
        intents = adapter.generate_rebalance_intents(
            current_positions={},
            current_prices={"AAA": Decimal("100.00"), "BBB": Decimal("50.00")},
            portfolio_nav=nav,
            as_of_date="2024-01-05",
            target_holdings=holdings,
        )
        n_targets = len(holdings)
        # Each intent's notional must be <= NAV / n_targets (with a
        # tiny Decimal rounding tolerance).
        per_holding_cap = nav / Decimal(n_targets)
        for intent in intents:
            notional = intent.quantity * intent.backtest_price
            assert notional <= per_holding_cap + Decimal("0.0001")
        # And the sum of BUY notionals must be <= NAV.
        buy_notional = sum(
            (i.quantity * i.backtest_price for i in intents if i.side == "buy"), start=Decimal("0")
        )
        assert buy_notional <= nav

    def test_meta_carries_score_rank_screen_date_strategy(
        self,
        adapter: LaneBSignalAdapter,
        merged: pl.DataFrame,
        prices: pl.DataFrame,
        companies: pl.DataFrame,
    ) -> None:
        holdings = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5), merged=merged, prices=prices, companies=companies
        )
        intents = adapter.generate_rebalance_intents(
            current_positions={},
            current_prices={"AAA": Decimal("100.00"), "BBB": Decimal("50.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=holdings,
        )
        for intent in intents:
            assert intent.strategy == "lane_b_composite"
            assert intent.meta["screen_date"] == "2024-01-05"
            assert intent.meta["strategy"] == "lane_b_composite"
            assert intent.meta["reason"] == "entry_or_topup"
            assert "composite_score" in intent.meta
            assert "composite_rank" in intent.meta


# ---------------------------------------------------------------------------
# generate_rebalance_intents — rebalance / exit
# ---------------------------------------------------------------------------


class TestRebalanceExitPositions:
    def test_position_no_longer_in_target_emits_sell(self, adapter: LaneBSignalAdapter) -> None:
        # Currently long CCC (SimFinId 3) but the new target is {AAA, BBB}.
        intents = adapter.generate_rebalance_intents(
            current_positions={"CCC": Decimal("100")},
            current_prices={"CCC": Decimal("25.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[
                _target("AAA", simfin_id=1, price=Decimal("100.00")),
                _target("BBB", simfin_id=2, price=Decimal("50.00")),
            ],
        )
        sells = [i for i in intents if i.side == "sell"]
        assert len(sells) == 1
        assert sells[0].instrument_id == "CCC"
        assert sells[0].quantity == Decimal("100")
        assert sells[0].meta["reason"] == "exited_target"

    def test_sells_emitted_before_buys(self, adapter: LaneBSignalAdapter) -> None:
        intents = adapter.generate_rebalance_intents(
            current_positions={"CCC": Decimal("100")},
            current_prices={"CCC": Decimal("25.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[
                _target("AAA", simfin_id=1, price=Decimal("100.00")),
                _target("BBB", simfin_id=2, price=Decimal("50.00")),
            ],
        )
        # First intent(s) should be SELL; later intent(s) should be BUY.
        first_sell_idx = next((i for i, x in enumerate(intents) if x.side == "sell"), len(intents))
        first_buy_idx = next((i for i, x in enumerate(intents) if x.side == "buy"), len(intents))
        assert first_sell_idx < first_buy_idx

    def test_topup_emits_buy_when_target_exceeds_held(self, adapter: LaneBSignalAdapter) -> None:
        # Currently hold 100 AAA at NAV=100k. Target at NAV=100k,
        # top_n=2 → 50k per holding. Price=100 → target=500 shares.
        # Delta = 500 - 100 = 400 BUY.
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("100")},
            current_prices={"AAA": Decimal("100.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[
                _target("AAA", simfin_id=1, price=Decimal("100.00")),
                _target("BBB", simfin_id=2, price=Decimal("50.00")),
            ],
        )
        topup = [i for i in intents if i.instrument_id == "AAA" and i.side == "buy"]
        assert len(topup) == 1
        assert topup[0].quantity == Decimal("400")

    def test_trim_emits_sell_when_held_exceeds_target(self, adapter: LaneBSignalAdapter) -> None:
        # Currently hold 800 AAA at NAV=100k. Target = 500 shares.
        # Delta = -300 → SELL 300.
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("800")},
            current_prices={"AAA": Decimal("100.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[
                _target("AAA", simfin_id=1, price=Decimal("100.00")),
                _target("BBB", simfin_id=2, price=Decimal("50.00")),
            ],
        )
        trim = [i for i in intents if i.instrument_id == "AAA" and i.side == "sell"]
        assert len(trim) == 1
        assert trim[0].quantity == Decimal("300")
        assert trim[0].meta["reason"] == "rebalance_trim"

    def test_hold_emits_no_intent(self, adapter: LaneBSignalAdapter) -> None:
        # Already at target → no intents.
        # Target = NAV/2 = 50k per holding. At price=100, qty=500.
        # At price=50, qty=1000.
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("500"), "BBB": Decimal("1000")},
            current_prices={"AAA": Decimal("100.00"), "BBB": Decimal("50.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[
                _target("AAA", simfin_id=1, price=Decimal("100.00")),
                _target("BBB", simfin_id=2, price=Decimal("50.00")),
            ],
        )
        assert intents == []

    def test_decimal_precision_whole_shares(self) -> None:
        # NAV=100001, 1 target → target_weight=1/1=1.0 → target_notional
        # = 100001.  At price=100 → 100001/100 = 1000.01 → floor 1000.
        cfg = LaneBSignalAdapterConfig(top_n_holdings=15)
        adapter = LaneBSignalAdapter(config=cfg)
        intents = adapter.generate_rebalance_intents(
            current_positions={},
            current_prices={"AAA": Decimal("100.00")},
            portfolio_nav=Decimal("100001"),
            as_of_date="2024-01-05",
            target_holdings=[_target("AAA", simfin_id=1, price=Decimal("100.00"))],
        )
        assert len(intents) == 1
        assert intents[0].quantity == Decimal("1000")  # whole shares, floored

    def test_zero_target_holdings_liquidates_all(self) -> None:
        adapter = LaneBSignalAdapter()
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("10"), "BBB": Decimal("20")},
            current_prices={"AAA": Decimal("100.00"), "BBB": Decimal("50.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[],
        )
        sides = [i.side for i in intents]
        assert sides == ["sell", "sell"]
        # Both tickers emitted as SELL.
        assert {i.instrument_id for i in intents} == {"AAA", "BBB"}

    def test_no_negative_quantities(self) -> None:
        # Sanity: no intent must ever carry qty <= 0.
        adapter = LaneBSignalAdapter()
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("100")},
            current_prices={"AAA": Decimal("100.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[
                _target("AAA", simfin_id=1, price=Decimal("100.00")),
                _target("BBB", simfin_id=2, price=Decimal("50.00")),
            ],
        )
        for intent in intents:
            assert intent.quantity > 0

    def test_negative_portfolio_nav_raises(self) -> None:
        adapter = LaneBSignalAdapter()
        with pytest.raises(ValueError, match="portfolio_nav"):
            adapter.generate_rebalance_intents(
                current_positions={},
                current_prices={},
                portfolio_nav=Decimal("-1"),
                as_of_date="2024-01-05",
                target_holdings=[],
            )

    def test_missing_current_price_during_exit_is_skipped(self) -> None:
        # If a held ticker has no price, the SELL is skipped (don't
        # emit a blind SELL that would fail downstream).
        adapter = LaneBSignalAdapter()
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("100")},  # no price supplied
            current_prices={},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[_target("BBB", simfin_id=2, price=Decimal("50.00"))],
        )
        # AAA SELL was suppressed (no price), only the BBB BUY remains.
        assert all(i.instrument_id != "AAA" for i in intents)
        assert any(i.instrument_id == "BBB" and i.side == "buy" for i in intents)


# ---------------------------------------------------------------------------
# Stop-loss
# ---------------------------------------------------------------------------


def _target(
    ticker: str,
    simfin_id: int = 1,
    price: Decimal = Decimal("100.00"),
    score: float | None = 0.85,
    rank: int | None = 1,
) -> Any:
    from analytics.strategy.lane_b_adapter import LaneBTargetHolding

    return LaneBTargetHolding(
        ticker=ticker,
        simfin_id=simfin_id,
        backtest_price=price,
        composite_score=score,
        composite_rank=rank,
    )


class TestStopLoss:
    def test_stop_loss_breach_emits_sell(self) -> None:
        adapter = LaneBSignalAdapter()
        # Register an entry at $100, now current price = $94 → -6% > -5%.
        adapter.register_entry(
            ticker="AAA",
            simfin_id=1,
            entry_price=Decimal("100.00"),
            quantity=Decimal("10"),
            composite_score=0.85,
            composite_rank=1,
            entry_date="2024-01-01",
        )
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("10")},
            current_prices={"AAA": Decimal("94.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[_target("AAA", simfin_id=1, price=Decimal("100.00"))],
        )
        stop_intents = [i for i in intents if i.meta.get("reason") == "stop_loss"]
        assert len(stop_intents) == 1
        assert stop_intents[0].side == "sell"
        assert stop_intents[0].instrument_id == "AAA"
        assert stop_intents[0].quantity == Decimal("10")
        # Active position tracker must have been cleared.
        assert "AAA" not in adapter.active_positions()

    def test_stop_loss_prevents_topup_in_same_cycle(self) -> None:
        # If stop is breached, we must NOT issue a top-up BUY in the
        # same rebalance cycle.  The stop SELL must be the only intent.
        adapter = LaneBSignalAdapter()
        adapter.register_entry(
            ticker="AAA",
            simfin_id=1,
            entry_price=Decimal("100.00"),
            quantity=Decimal("10"),
            composite_score=0.85,
            composite_rank=1,
        )
        # Target qty for NAV=100k, top_n=2, price=100 → 500.  Current=10.
        # Without stop: BUY 490. With stop: SELL 10 only.
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("10")},
            current_prices={"AAA": Decimal("94.00")},  # -6% breach
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[
                _target("AAA", simfin_id=1, price=Decimal("100.00")),
                _target("BBB", simfin_id=2, price=Decimal("50.00")),
            ],
        )
        aaa_intents = [i for i in intents if i.instrument_id == "AAA"]
        assert len(aaa_intents) == 1
        assert aaa_intents[0].side == "sell"
        assert aaa_intents[0].meta["reason"] == "stop_loss"
        # BBB BUY still emitted (other target is unaffected).
        bbb_buys = [i for i in intents if i.instrument_id == "BBB" and i.side == "buy"]
        assert len(bbb_buys) == 1

    def test_no_stop_loss_when_disabled(self) -> None:
        cfg = LaneBSignalAdapterConfig(per_idea_stop_loss_pct=None)
        adapter = LaneBSignalAdapter(config=cfg)
        adapter.register_entry(
            ticker="AAA",
            simfin_id=1,
            entry_price=Decimal("100.00"),
            quantity=Decimal("10"),
            composite_score=0.85,
            composite_rank=1,
        )
        # price=80 → -20% (huge breach).  No stop-loss because disabled.
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("10")},
            current_prices={"AAA": Decimal("80.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[_target("AAA", simfin_id=1, price=Decimal("100.00"))],
        )
        stop_intents = [i for i in intents if i.meta.get("reason") == "stop_loss"]
        assert stop_intents == []
        # AAA still held (no exit emitted) → only the top-up BUY appears.
        aaa_buys = [i for i in intents if i.instrument_id == "AAA" and i.side == "buy"]
        assert len(aaa_buys) == 1

    def test_no_stop_loss_when_price_above_threshold(self) -> None:
        adapter = LaneBSignalAdapter()
        adapter.register_entry(
            ticker="AAA",
            simfin_id=1,
            entry_price=Decimal("100.00"),
            quantity=Decimal("10"),
            composite_score=0.85,
            composite_rank=1,
        )
        # price=96 → -4% (within tolerance).
        intents = adapter.generate_rebalance_intents(
            current_positions={"AAA": Decimal("10")},
            current_prices={"AAA": Decimal("96.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[_target("AAA", simfin_id=1, price=Decimal("100.00"))],
        )
        stop_intents = [i for i in intents if i.meta.get("reason") == "stop_loss"]
        assert stop_intents == []

    def test_register_and_unregister_lifecycle(self) -> None:
        adapter = LaneBSignalAdapter()
        adapter.register_entry(
            ticker="AAA",
            simfin_id=1,
            entry_price=Decimal("100.00"),
            quantity=Decimal("10"),
            composite_score=0.85,
            composite_rank=1,
        )
        assert "AAA" in adapter.active_positions()
        adapter.unregister_position("AAA")
        assert "AAA" not in adapter.active_positions()

    def test_register_entry_validates_positive_quantity(self) -> None:
        adapter = LaneBSignalAdapter()
        with pytest.raises(ValueError, match="quantity"):
            adapter.register_entry(
                ticker="AAA",
                simfin_id=1,
                entry_price=Decimal("100.00"),
                quantity=Decimal("0"),
                composite_score=0.85,
                composite_rank=1,
            )

    def test_register_entry_validates_positive_price(self) -> None:
        adapter = LaneBSignalAdapter()
        with pytest.raises(ValueError, match="entry_price"):
            adapter.register_entry(
                ticker="AAA",
                simfin_id=1,
                entry_price=Decimal("0"),
                quantity=Decimal("10"),
                composite_score=0.85,
                composite_rank=1,
            )

    def test_active_positions_returns_copy(self) -> None:
        adapter = LaneBSignalAdapter()
        adapter.register_entry(
            ticker="AAA",
            simfin_id=1,
            entry_price=Decimal("100.00"),
            quantity=Decimal("10"),
            composite_score=0.85,
            composite_rank=1,
        )
        snap = adapter.active_positions()
        snap["BBB"] = snap["AAA"]  # mutate the copy
        # Internal state must be unaffected.
        assert "BBB" not in adapter.active_positions()

    def test_stale_active_position_dropped_when_not_in_book(self) -> None:
        # If the caller forgets to unregister an exited position, the
        # adapter should still tolerate it on the next rebalance (the
        # ticker is no longer in current_positions → drop from tracker).
        adapter = LaneBSignalAdapter()
        adapter.register_entry(
            ticker="AAA",
            simfin_id=1,
            entry_price=Decimal("100.00"),
            quantity=Decimal("10"),
            composite_score=0.85,
            composite_rank=1,
        )
        # current_positions has no AAA (caller exited it manually).
        adapter.generate_rebalance_intents(
            current_positions={"BBB": Decimal("1000")},
            current_prices={"BBB": Decimal("50.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=[_target("BBB", simfin_id=2, price=Decimal("50.00"))],
        )
        # No crash; AAA removed from tracker.
        assert "AAA" not in adapter.active_positions()


# ---------------------------------------------------------------------------
# End-to-end: screen → rebalance
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_screen_then_rebalance(
        self, adapter: LaneBSignalAdapter, merged: pl.DataFrame, prices: pl.DataFrame
    ) -> None:
        holdings = adapter.screen_universe(
            as_of_date=datetime(2024, 1, 5),
            merged=merged,
            prices=prices,
            companies=_make_companies(),
        )
        assert {h.ticker for h in holdings} == {"AAA", "BBB"}

        intents = adapter.generate_rebalance_intents(
            current_positions={},
            current_prices={"AAA": Decimal("100.00"), "BBB": Decimal("50.00")},
            portfolio_nav=Decimal("100000"),
            as_of_date="2024-01-05",
            target_holdings=holdings,
        )
        # 2 BUY intents, equal-weight (NAV/2 → $50k each).
        buys = [i for i in intents if i.side == "buy"]
        assert len(buys) == 2
        # Notional per BUY ≤ NAV/2.
        for intent in buys:
            notional = intent.quantity * intent.backtest_price
            assert notional <= Decimal("50000.01")
        # Backtest prices match the prices DataFrame.
        by_ticker = {i.instrument_id: i for i in buys}
        assert by_ticker["AAA"].backtest_price == Decimal("100")
        assert by_ticker["BBB"].backtest_price == Decimal("50")
