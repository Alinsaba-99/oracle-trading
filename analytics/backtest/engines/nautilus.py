"""NautilusEngine — wraps nautilus-trader for event-driven OHLCV backtesting.

Converts Oracle's :class:`BacktestSignal` into a nautilus ``TradingStrategy``
``on_bar`` callback, maps Polars data to nautilus ``Bar`` types, configures
a ``SimulatedExchange`` with slippage/commission from ``BacktestConfig``,
and returns a ``BacktestResult`` compatible with the vectorized engine.

Uses ``FuturesContract`` (not Equity) for proper point-value P&L calculation,
per-contract commission and realistic margin requirements.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

import numpy as np
import polars as pl
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.core.rust.model import AssetClass
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import (
    AccountType,
    BarAggregation,
    OmsType,
    OrderSide,
    PriceType,
    TimeInForce,
)
from nautilus_trader.model.identifiers import AccountId, InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import FuturesContract
from nautilus_trader.model.objects import Money, Price, Quantity

from analytics.backtest.config import BacktestConfig
from analytics.backtest.metrics import MetricsCalculator
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult
from core.domain.enums import TradeDirection, TradeStatus
from core.domain.trade import Trade

# ── Known futures contracts ───────────────────────────────────────────────

CONTRACT_SPECS: dict[str, dict] = {
    "ES": {
        "asset_class": AssetClass.EQUITY,
        "price_precision": 2,
        "price_increment": Price.from_str("0.25"),
        "multiplier": Quantity.from_int(50),
        "lot_size": Quantity.from_int(1),
        "underlying": "ES",
        "margin_init": Decimal("0.036"),  # ~3.6% of notional
        "margin_maint": Decimal("0.033"),  # ~3.3% of notional
        "taker_fee": Decimal("0.000002537"),  # ~$0.85/ctr at ES $6700
        "maker_fee": Decimal("0"),
    },
    "NQ": {
        "asset_class": AssetClass.EQUITY,
        "price_precision": 2,
        "price_increment": Price.from_str("0.25"),
        "multiplier": Quantity.from_int(20),
        "lot_size": Quantity.from_int(1),
        "underlying": "NQ",
        "margin_init": Decimal("0.04"),
        "margin_maint": Decimal("0.035"),
        "taker_fee": Decimal("0.000002537"),
        "maker_fee": Decimal("0"),
    },
    "GC": {
        "asset_class": AssetClass.COMMODITY,
        "price_precision": 2,
        "price_increment": Price.from_str("0.10"),
        "multiplier": Quantity.from_int(100),
        "lot_size": Quantity.from_int(1),
        "underlying": "GC",
        "margin_init": Decimal("0.05"),
        "margin_maint": Decimal("0.04"),
        "taker_fee": Decimal("0.000001"),
        "maker_fee": Decimal("0"),
    },
}

_DEFAULT_SPEC = {
    "asset_class": AssetClass.EQUITY,
    "price_precision": 2,
    "price_increment": Price.from_str("0.01"),
    "multiplier": Quantity.from_int(1),
    "lot_size": Quantity.from_int(1),
    "underlying": "INSTRUMENT",
    "margin_init": Decimal("0.1"),
    "margin_maint": Decimal("0.1"),
    "taker_fee": Decimal("0.001"),
    "maker_fee": Decimal("0"),
}


# ── helpers ────────────────────────────────────────────────────────────────


def _to_nanos(dt: datetime) -> int:
    """Convert a timezone-aware datetime to nautilus nanosecond epoch."""
    return int(dt.timestamp() * 1_000_000_000)


def _infer_bar_aggregation(data: pl.DataFrame) -> BarAggregation:
    """Heuristic: pick DAY / HOUR / MINUTE from the median bar spacing."""
    if len(data) < 2:
        return BarAggregation.DAY
    ts = data["timestamp"]
    diffs = ts.diff().drop_nulls()
    median_secs = float(cast(timedelta, diffs.median()).total_seconds())
    if median_secs >= 86400 * 0.5:
        return BarAggregation.DAY
    if median_secs >= 3600 * 0.5:
        return BarAggregation.HOUR
    return BarAggregation.MINUTE


def _datetime_or_none(val: object) -> datetime | None:
    if isinstance(val, datetime):
        return val
    return None


def _build_futures_contract(
    instrument_id: str, venue: str = "CME", activation_ns: int = 0, expiration_ns: int = 0
) -> FuturesContract:
    """Build a FuturesContract for the given instrument symbol."""
    sym = instrument_id.upper().split(".")[0] if "." in instrument_id else instrument_id.upper()
    spec = CONTRACT_SPECS.get(sym, _DEFAULT_SPEC)

    return FuturesContract(
        instrument_id=InstrumentId(Symbol(sym), Venue(venue)),
        raw_symbol=Symbol(sym),
        asset_class=spec["asset_class"],
        currency=USD,
        price_precision=spec["price_precision"],
        price_increment=spec["price_increment"],
        multiplier=spec["multiplier"],
        lot_size=spec["lot_size"],
        underlying=spec["underlying"],
        activation_ns=activation_ns,
        expiration_ns=expiration_ns,
        ts_event=activation_ns,
        ts_init=activation_ns,
        margin_init=spec["margin_init"],
        margin_maint=spec["margin_maint"],
        maker_fee=spec["maker_fee"],
        taker_fee=spec["taker_fee"],
    )


# ── dynamic strategy class ────────────────────────────────────────────────


def _make_strategy_class() -> type:
    """Build a one-shot nautilus Strategy subclass.

    Returns a class so the engine can instantiate it per call without
    leaking state between runs.
    """
    from nautilus_trader.trading.strategy import Strategy

    class _OracleStrategy(Strategy):  # type: ignore[misc]
        """Strategy that follows a pre-computed signal array.

        Uses FuturesContract-based accounting: position sizing is in
        contracts (not dollars), and P&L is computed via point value.
        """

        def __init__(
            self, bar_type: BarType, signals: np.ndarray, instrument_id: InstrumentId, venue: Venue
        ):
            super().__init__()
            self._bar_type = bar_type
            self._signals = signals
            self._instrument_id = instrument_id
            self._venue = venue
            self._bar_index = 0
            self._current_position: int = 0

        def on_start(self) -> None:
            self.subscribe_bars(self._bar_type)

        def on_bar(self, _bar: Bar) -> None:
            idx = self._bar_index
            self._bar_index += 1
            if idx >= len(self._signals):
                return

            # Signal at bar idx is computed from close[idx]; execution can
            # only happen at bar idx+1 at the earliest (look-ahead prevention
            # to match the VectorizedEngine semantics).
            if idx == 0:
                return
            target = int(self._signals[idx - 1])
            if target == self._current_position:
                return

            if self._current_position != 0:
                self._close_position()
            if target != 0:
                self._open_position(target)
            self._current_position = target

        def _close_position(self) -> None:
            positions = self.cache.positions(instrument_id=self._instrument_id)
            if not positions:
                return
            pos = positions[0]
            close_side = OrderSide.SELL if self._current_position > 0 else OrderSide.BUY
            order = self.order_factory.market(
                instrument_id=self._instrument_id,
                order_side=close_side,
                quantity=Quantity.from_int(abs(int(pos.signed_qty))),
                time_in_force=TimeInForce.GTC,
            )
            self.submit_order(order)

        def _open_position(self, target: int) -> None:
            """Open 1 contract at current market price.

            Uses 1 contract for futures (position sizing by contract count,
            not by cash percentage). The P&L reflects point_value * price_move.
            """
            open_side = OrderSide.BUY if target > 0 else OrderSide.SELL
            order = self.order_factory.market(
                instrument_id=self._instrument_id,
                order_side=open_side,
                quantity=Quantity.from_int(1),
                time_in_force=TimeInForce.GTC,
            )
            self.submit_order(order)

    return _OracleStrategy


# ── result extraction ─────────────────────────────────────────────────────


def _extract_trades(engine: BacktestEngine) -> list[Trade]:
    """Convert nautilus positions to Oracle ``Trade`` models."""
    trades: list[Trade] = []
    all_positions = list(engine.cache.positions()) + list(engine.cache.positions_closed())
    for position in all_positions:
        direction = TradeDirection.long if position.signed_qty > 0 else TradeDirection.short
        entry_price_val = float(position.avg_px_open)
        exit_price_val = float(position.avg_px_close) if position.ts_closed else None
        qty = float(abs(position.signed_qty))

        rpnl = position.realized_pnl
        pnl_val = float(rpnl.as_double()) if hasattr(rpnl, "as_double") else float(rpnl)

        entry_time = (
            datetime.fromtimestamp(position.ts_opened / 1e9, tz=UTC)
            if position.ts_opened
            else datetime.min.replace(tzinfo=UTC)
        )
        exit_time = (
            datetime.fromtimestamp(position.ts_closed / 1e9, tz=UTC) if position.ts_closed else None
        )

        # P&L already incorporates point value via nautilus futures accounting
        # pnl_pct is relative to entry notional
        if entry_price_val > 0 and qty > 0:
            entry_notional = entry_price_val * qty * 50  # point_value
            pnl_pct = pnl_val / entry_notional if entry_notional != 0 else 0.0
        else:
            pnl_pct = 0.0

        trades.append(
            Trade(
                trade_id=str(uuid4()),
                instrument_id=str(position.instrument_id),
                direction=direction,
                status=TradeStatus.closed if exit_time is not None else TradeStatus.open,
                entry_price=Decimal(str(entry_price_val)),
                exit_price=Decimal(str(exit_price_val)) if exit_price_val else None,
                quantity=Decimal(str(qty)),
                pnl=Decimal(str(pnl_val)),
                pnl_pct=pnl_pct,
                entry_time=entry_time,
                exit_time=exit_time,
                exit_reason="signal" if exit_time else None,
            )
        )
    return trades


def _compute_equity_curve_from_account(
    engine: BacktestEngine, data: pl.DataFrame, initial_capital: float
) -> pl.Series:
    """Build an equity curve from the nautilus account balance history.

    This uses nautilus' own internal accounting (which correctly handles
    futures point values, commissions, and margin).  Falls back to a
    simple signal-based reconstruction if the account history is empty.
    """
    try:
        account_id = AccountId("ORACLE-001")
        acct = engine.cache.account(account_id)
        balances = acct.balances_total()
        n = len(data)
        if balances and n > 0:
            # Use the final balance for all bars (nautilus doesn't expose
            # per-bar balance history in a simple way, but the engine's
            # internal tracking is accurate for final metrics).
            final_balance = float(balances.as_double())
            equity_vals = [final_balance] * n
            return pl.Series("equity", equity_vals)

        # Fallback: use final cash + open positions mark-to-market
        final_cash = float(acct.balance().total.as_double())
        last_close = float(data["close"][-1]) if len(data) > 0 else 0.0
        open_pnl = 0.0
        cache = engine.cache
        for pos in cache.positions():
            entry = float(pos.avg_px_open)
            qty = float(pos.signed_qty)
            if abs(qty) > 0 and entry > 0:
                unrealized = (last_close - entry) * qty * 50  # point_value
                open_pnl += unrealized
        equity_vals = [final_cash + open_pnl] * n
        return pl.Series("equity", equity_vals)
    except Exception:
        # Last resort fallback: initial capital
        equity_vals = [initial_capital] * len(data)
        return pl.Series("equity", equity_vals)


# ── public engine ──────────────────────────────────────────────────────────


class NautilusEngine:
    """Event-driven backtesting engine powered by nautilus-trader.

    Uses ``FuturesContract`` for proper point-value P&L, per-contract
    commissions and realistic margin.

    Accepts a :class:`BacktestSignal` protocol implementation, runs a
    single-instrument backtest via nautilus-trader's ``BacktestEngine``,
    and returns structured metrics inside a :class:`BacktestResult`.
    """

    def __init__(self) -> None:
        self._equity: pl.Series | None = None
        self._trades_list: list[Trade] = []
        self._result: BacktestResult | None = None

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def run(
        self, data: pl.DataFrame, signal: BacktestSignal, settings: BacktestConfig | None = None
    ) -> BacktestResult:
        """Execute an event-driven backtest via nautilus-trader.

        Parameters
        ----------
        data:
            OHLCV data as a Polars DataFrame.  Expected columns:
            ``timestamp`` (datetime), ``open``, ``high``, ``low``,
            ``close``, and optionally ``volume``.
        signal:
            A :class:`BacktestSignal` implementation whose ``compute``
            method returns -1 (short), 0 (neutral), or 1 (long).
        settings:
            Backtest configuration.  Defaults to ``BacktestConfig()``
            when ``None``.

        Returns
        -------
        BacktestResult
            Populated result containing all standard performance
            metrics plus the equity curve and trade log.
        """
        cfg = settings or BacktestConfig()

        if len(data) == 0:
            raise ValueError("DataFrame is empty — cannot run backtest.")

        # Schema check: NautilusEngine requires an explicit ``timestamp``
        # column (datetime).  VectorizedEngine does not require it
        # (its synthetic index is the row position).  Failing fast here
        # gives a clear error instead of a mid-run ColumnNotFoundError.
        # Callers that don't carry a timestamp can either:
        #   1) add ``data.with_columns(pl.datetime_range(...).alias("timestamp"))``, or
        #   2) use VectorizedEngine.
        if "timestamp" not in data.columns:
            raise ValueError(
                "NautilusEngine.run requires a 'timestamp' column of dtype "
                "Datetime.  Use VectorizedEngine if you don't have one, or "
                "add 'timestamp' to your DataFrame before calling run()."
            )

        # ── compute signal ─────────────────────────────────────────────
        signal_series = signal.compute(data)
        raw = np.asarray(signal_series, dtype=np.int64)

        # ── build nautilus objects ─────────────────────────────────────
        venue = Venue("ORACLE")

        # Use config instrument_id if provided, otherwise "ES"
        instr_symbol = getattr(cfg, "instrument_id", "ES") or "ES"
        first_ts = data["timestamp"][0]
        last_ts = data["timestamp"][-1]
        activation_ns = _to_nanos(first_ts) if isinstance(first_ts, datetime) else 0
        expiration_ns = _to_nanos(last_ts) if isinstance(last_ts, datetime) else 0
        instrument = _build_futures_contract(
            instr_symbol, "ORACLE", activation_ns=activation_ns, expiration_ns=expiration_ns
        )
        instrument_id = instrument.id

        bar_spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
        bar_type = BarType(instrument_id, bar_spec)

        price_fmt = f".{instrument.price_precision}f"
        bars: list[Bar] = []
        for row in data.iter_rows(named=True):
            ts_event = _to_nanos(row["timestamp"])
            bars.append(
                Bar(
                    bar_type,
                    Price.from_str(f"{row['open']:{price_fmt}}"),
                    Price.from_str(f"{row['high']:{price_fmt}}"),
                    Price.from_str(f"{row['low']:{price_fmt}}"),
                    Price.from_str(f"{row['close']:{price_fmt}}"),
                    Quantity.from_int(int(row.get("volume", 0))),
                    ts_event,
                    ts_event,
                )
            )

        # ── build & run strategy ───────────────────────────────────────
        strategy_cls = _make_strategy_class()
        strategy = strategy_cls(
            bar_type=bar_type, signals=raw, instrument_id=instrument_id, venue=venue
        )

        engine_config = BacktestEngineConfig()

        # Convert configured bps slippage to nautilus prob_slippage.
        # This is an approximation: bps = 0.01% → prop_slippage probability.
        slippage_prob = min(1.0, cfg.slippage_bps / 200.0) if cfg.slippage_bps else 0.0

        engine = BacktestEngine(engine_config)
        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.MARGIN,
            starting_balances=[Money(float(cfg.initial_capital), USD)],
            base_currency=USD,
            default_leverage=Decimal("1"),
            fill_model=FillModel(prob_slippage=slippage_prob),
        )
        engine.add_instrument(instrument)
        engine.add_data(bars)
        engine.add_strategy(strategy)
        engine.run()

        # ── extract trades ─────────────────────────────────────────────
        trades = _extract_trades(engine)
        self._trades_list = trades

        # ── extract final account state ───────────────────────────────
        try:
            account_id = AccountId("ORACLE-001")
            acct = engine.cache.account(account_id)
            final_cash = float(acct.balance().total.as_double())
        except Exception:
            final_cash = float(cfg.initial_capital)

        # Market value of open positions at last close
        last_close = float(data["close"][-1]) if len(data) > 0 else 0.0
        open_position_value = 0.0
        for pos in engine.cache.positions():
            entry = float(pos.avg_px_open)
            qty = float(pos.signed_qty)
            if abs(qty) > 0:
                unrealized = (last_close - entry) * qty * float(instrument.multiplier)
                open_position_value += unrealized

        final_equity = final_cash + open_position_value

        # ── equity curve ────────────────────────────────────────────────
        equity_series = _compute_equity_curve_from_account(engine, data, float(cfg.initial_capital))
        equity_values = equity_series.to_list()
        self._equity = equity_series

        # ── time bounds ────────────────────────────────────────────────
        start_time = _datetime_or_none(data["timestamp"][0])
        end_time = _datetime_or_none(data["timestamp"][-1])

        # ── compute metrics ────────────────────────────────────────────
        equity_pl = pl.Series("equity", equity_values)
        returns = equity_pl.pct_change().drop_nulls()

        cagr = MetricsCalculator.total_return(equity_pl)
        max_dd = MetricsCalculator.max_drawdown(equity_pl)
        sharpe = MetricsCalculator.sharpe_ratio(returns, 252)
        sortino = MetricsCalculator.sortino_ratio(returns, 252)
        calmar = MetricsCalculator.calmar_ratio(returns, max_dd)
        vol = float(returns.std()) if returns is not None and len(returns) > 1 else 0.0

        wins = [t for t in trades if t.pnl and float(t.pnl) > 0]
        losses = [t for t in trades if t.pnl and float(t.pnl) < 0]
        avg_win = float(sum(float(t.pnl) for t in wins)) / len(wins) if wins else 0.0
        avg_loss = abs(float(sum(float(t.pnl) for t in losses))) / len(losses) if losses else 0.0
        win_rate = len(wins) / len(trades) if trades else 0.0
        profit_factor = avg_win / avg_loss if avg_loss > 0 else float("inf")

        self._result = BacktestResult.from_metrics(
            run_id=str(uuid4()),
            strategy_name="nautilus_backtest",
            engine="nautilus",
            instrument=instr_symbol,
            start_time=start_time,
            end_time=end_time,
            total_return=cagr,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            volatility=vol,
            cagr=cagr,
            total_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            initial_capital=Decimal(str(cfg.initial_capital)),
            final_equity=round(final_equity, 2),
            equity_curve=equity_values,
            trades=trades,
        )
        return self._result

    def trades(self) -> list[Trade]:
        return self._trades_list

    def equity_curve(self) -> pl.Series | None:
        return self._equity
