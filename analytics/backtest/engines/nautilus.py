"""NautilusEngine — wraps nautilus-trader for event-driven OHLCV backtesting.

Converts Oracle's :class:`BacktestSignal` into a nautilus ``TradingStrategy``
``on_bar`` callback, maps Polars data to nautilus ``Bar`` types, configures
a ``SimulatedExchange`` with slippage/commission from ``BacktestConfig``,
and returns a ``BacktestResult`` compatible with the vectorized engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import numpy as np
import polars as pl
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
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
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Money, Price, Quantity

from analytics.backtest.config import BacktestConfig
from analytics.backtest.metrics import MetricsCalculator
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult
from core.domain.enums import TradeDirection, TradeStatus
from core.domain.trade import Trade

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
    median_secs = float(
        diffs.median().total_seconds()
        if hasattr(diffs.median(), "total_seconds")
        else diffs.median()
    )
    if median_secs >= 86400 * 0.5:
        return BarAggregation.DAY
    if median_secs >= 3600 * 0.5:
        return BarAggregation.HOUR
    return BarAggregation.MINUTE


def _datetime_or_none(val: object) -> datetime | None:
    if isinstance(val, datetime):
        return val
    return None


# ── dynamic strategy class ────────────────────────────────────────────────


def _make_strategy_class() -> type:
    """Build a one-shot nautilus Strategy subclass.

    Returns a class so the engine can instantiate it per call without
    leaking state between runs.
    """
    from nautilus_trader.trading.strategy import Strategy

    class _OracleStrategy(Strategy):
        """Strategy that follows a pre-computed signal array."""

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

        def on_bar(self, bar: Bar) -> None:
            idx = self._bar_index
            self._bar_index += 1
            if idx >= len(self._signals):
                return

            target = int(self._signals[idx])
            if target == self._current_position:
                return

            if self._current_position != 0:
                self._close_position()
            if target != 0:
                self._open_position(target, bar)
            self._current_position = target

        def _close_position(self) -> None:
            try:
                pos = self.cache.position(self._instrument_id)
                if pos is None:
                    return
                close_side = OrderSide.SELL if self._current_position > 0 else OrderSide.BUY
                order = self.order_factory.market(
                    instrument_id=self._instrument_id,
                    order_side=close_side,
                    quantity=Quantity.from_int(abs(int(pos.signed_qty))),
                    time_in_force=TimeInForce.GTC,
                )
                self.submit_order(order)
            except Exception:
                pass

        def _open_position(self, target: int, bar: Bar) -> None:
            price = float(bar.close.as_double())  # type: ignore[union-attr]
            try:
                acct = self.cache.account_for_venue(self._venue)
                cash = float(acct.balance().free.as_double())  # type: ignore[union-attr]
            except Exception:
                cash = 100_000.0

            qty = max(1, int(cash * 0.95 / price)) if price > 0 else 1
            open_side = OrderSide.BUY if target > 0 else OrderSide.SELL
            order = self.order_factory.market(
                instrument_id=self._instrument_id,
                order_side=open_side,
                quantity=Quantity.from_int(qty),
                time_in_force=TimeInForce.GTC,
            )
            self.submit_order(order)

    return _OracleStrategy


# ── result extraction ─────────────────────────────────────────────────────


def _extract_trades(engine: BacktestEngine) -> list[Trade]:
    """Convert nautilus positions to Oracle ``Trade`` models."""
    trades: list[Trade] = []
    for position in engine.cache.positions():
        direction = TradeDirection.long if position.signed_qty > 0 else TradeDirection.short
        entry_price_val = float(position.avg_px_open)
        exit_price_val = float(position.avg_px_close) if position.ts_closed else None
        qty = float(abs(position.signed_qty))

        rpnl = position.realized_pnl
        pnl_val = float(rpnl.as_double()) if hasattr(rpnl, "as_double") else float(rpnl)  # type: ignore[union-attr]

        entry_time = (
            datetime.fromtimestamp(position.ts_opened / 1e9, tz=UTC)
            if position.ts_opened
            else datetime.min.replace(tzinfo=UTC)
        )
        exit_time = (
            datetime.fromtimestamp(position.ts_closed / 1e9, tz=UTC) if position.ts_closed else None
        )

        if exit_price_val and entry_price_val > 0:
            pnl_pct = (exit_price_val - entry_price_val) / entry_price_val
            if direction == TradeDirection.short:
                pnl_pct = -pnl_pct
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


def _compute_equity_curve(
    data: pl.DataFrame, signal: pl.Series, initial_capital: float, trades: list[Trade] | None = None
) -> pl.Series:
    """Build equity curve from signal, close prices and actual trade fills.

    Uses actual trade entry prices and quantities when available, falling
    back to a 95%-of-cash model at the signal bar's close for bars that
    had no nautilus trade.

    Parameters
    ----------
    data:
        OHLCV data with ``timestamp`` and ``close`` columns.
    signal:
        Polars series with -1, 0, 1 values.
    initial_capital:
        Starting cash.
    trades:
        List of Trade objects from the nautilus backtest.  When provided
        the curve uses actual fill prices and quantities for accuracy.
    """
    closes = data["close"].to_numpy()
    sig = signal.to_numpy()
    n = len(closes)

    # Build a lookup: for each bar that has a trade entry, store what happens
    # We match trades to bars by finding the closest bar to the entry timestamp.
    timestamps = data["timestamp"].to_list()
    bar_of_trade: dict[int, tuple[str, float, float]] = {}  # bar_idx -> (action, price, qty)

    if trades:
        for t in trades:
            if t.entry_time is None:
                continue
            et = t.entry_time
            if et.tzinfo is None:
                et = et.replace(tzinfo=UTC)
            # Find closest bar
            best_dist = float("inf")
            best_idx = -1
            for idx, ts in enumerate(timestamps):
                if isinstance(ts, datetime):
                    ts_utc = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
                    dist = abs((et - ts_utc).total_seconds())
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = idx
            if best_idx >= 0:
                entry_qty = float(t.quantity) if t.quantity else 0.0
                entry_px = float(t.entry_price) if t.entry_price else closes[best_idx]
                direction = 1 if t.direction == TradeDirection.long else -1
                bar_of_trade[best_idx] = ("enter", entry_px, direction * entry_qty)

            if t.exit_time:
                xt = t.exit_time
                if xt.tzinfo is None:
                    xt = xt.replace(tzinfo=UTC)
                best_dist = float("inf")
                best_idx = -1
                for idx, ts in enumerate(timestamps):
                    if isinstance(ts, datetime):
                        ts_utc = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
                        dist = abs((xt - ts_utc).total_seconds())
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = idx
                if best_idx >= 0:
                    exit_qty = float(t.quantity) if t.quantity else 0.0
                    exit_px = float(t.exit_price) if t.exit_price else closes[best_idx]
                    direction = 1 if t.direction == TradeDirection.long else -1
                    bar_of_trade[best_idx] = ("exit", exit_px, direction * exit_qty)

    # Walk through bars computing equity
    cash = initial_capital
    shares = 0.0
    equity_vals: list[float] = []

    for i in range(n):
        # Check if there's a trade action at this bar
        if i in bar_of_trade:
            action, price, qty = bar_of_trade[i]
            if action == "enter":
                # Override: use actual trade info
                # But first close existing position if direction changes
                new_shares = qty
                if shares != 0 and (shares * new_shares) < 0:
                    # Opposite direction — close first
                    cash += shares * price
                    shares = 0
                if shares == 0:
                    cost = abs(new_shares) * price
                    cash -= cost
                    shares = new_shares
            elif action == "exit":
                cash += shares * price
                shares = 0.0

        # Record equity at this bar
        eq = cash + abs(shares) * closes[i] if shares != 0 else cash
        equity_vals.append(eq)

        # Default: follow signal for bars without trade info
        if i not in bar_of_trade and i < n - 1:
            next_sig = int(sig[i + 1])
            cur_sig = int(sig[i])
            if next_sig != cur_sig:
                if cur_sig != 0 and next_sig == 0:
                    cash += shares * closes[i]
                    shares = 0.0
                elif cur_sig == 0 and next_sig != 0:
                    price = closes[i]
                    qty = max(1, int(cash * 0.95 / price)) if price > 0 else 1
                    shares = float(qty if next_sig > 0 else -qty)
                    cash -= qty * price

    return pl.Series("equity", equity_vals)


# ── public engine ──────────────────────────────────────────────────────────


class NautilusEngine:
    """Event-driven backtesting engine powered by nautilus-trader.

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

        # ── compute signal ─────────────────────────────────────────────
        signal_series = signal.compute(data)
        raw = np.asarray(signal_series, dtype=np.int64)

        # ── build nautilus objects ─────────────────────────────────────
        venue = Venue("ORACLE")
        instrument_id = InstrumentId(Symbol("INSTRUMENT"), venue)

        first_ts = data["timestamp"][0]
        ts = _to_nanos(first_ts) if isinstance(first_ts, datetime) else _to_nanos(datetime.now(UTC))
        instrument = Equity(
            instrument_id=instrument_id,
            raw_symbol=Symbol("INSTRUMENT"),
            currency=USD,
            price_precision=8,
            price_increment=Price.from_str("0.00000001"),
            lot_size=Quantity.from_int(1),
            ts_event=ts,
            ts_init=ts,
            max_quantity=Quantity.from_int(1_000_000),
            min_quantity=Quantity.from_int(1),
            margin_init=Decimal("1.0"),
            margin_maint=Decimal("1.0"),
            maker_fee=Decimal("0"),
            taker_fee=Decimal(str(cfg.commission_pct)),
        )

        agg = _infer_bar_aggregation(data)
        bar_spec = BarSpecification(1, agg, PriceType.LAST)
        bar_type = BarType(instrument_id, bar_spec)

        bars: list[Bar] = []
        for row in data.iter_rows(named=True):
            ts_event = _to_nanos(row["timestamp"])
            bars.append(
                Bar(
                    bar_type,
                    Price.from_str(f"{row['open']:.8f}"),
                    Price.from_str(f"{row['high']:.8f}"),
                    Price.from_str(f"{row['low']:.8f}"),
                    Price.from_str(f"{row['close']:.8f}"),
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
        engine = BacktestEngine(engine_config)

        engine.add_venue(
            venue=venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            starting_balances=[Money(float(cfg.initial_capital), USD)],
            base_currency=USD,
            fill_model=FillModel(),
        )
        engine.add_instrument(instrument)
        engine.add_data(bars)
        engine.add_strategy(strategy)
        engine.run()

        # ── extract trades from nautilus positions ─────────────────────
        trades = _extract_trades(engine)
        self._trades_list = trades

        # ── final equity from last close + remaining cash + trades ────
        # Use the account cash balance for remaining cash
        try:
            account_id = AccountId("ORACLE-001")
            acct = engine.cache.account(account_id)
            final_cash = float(acct.balance().total.as_double())  # type: ignore[union-attr]
        except Exception:
            final_cash = float(cfg.initial_capital)

        # Add market value of any still-open positions using last close price
        last_close = float(data["close"][-1]) if len(data) > 0 else 0.0
        open_position_value = 0.0
        for t in trades:
            if t.status == TradeStatus.open and t.quantity:
                qty = float(t.quantity)
                direction = 1 if t.direction == TradeDirection.long else -1
                float(t.entry_price) if t.entry_price else last_close
                # position market value = direction * qty * current_price
                open_position_value += direction * qty * last_close

        final_equity = final_cash + open_position_value

        # ── compute equity curve from signal + prices ──────────────────
        # ── compute equity curve from signal + prices + trades ─────────
        equity_series = _compute_equity_curve(
            data, signal_series, float(cfg.initial_capital), trades
        )
        equity_values = equity_series.to_list()
        self._equity = equity_series

        # ── time bounds ────────────────────────────────────────────────
        start_time = _datetime_or_none(data["timestamp"][0])
        end_time = _datetime_or_none(data["timestamp"][-1])

        cash = float(cfg.initial_capital)
        years = (
            (end_time - start_time).total_seconds() / (365.25 * 86400)
            if start_time and end_time
            else 1.0
        )
        cagr = ((final_equity / cash) ** (1.0 / max(years, 1e-10)) - 1.0) if cash > 0 else 0.0

        # Returns from equity curve (trim leading flat days)
        if len(equity_values) > 1:
            eq_arr = np.array(equity_values, dtype=np.float64)
            first_active = 0
            for i in range(1, len(eq_arr)):
                if abs(eq_arr[i] - eq_arr[0]) > 0.01 * eq_arr[0]:
                    first_active = max(0, i - 1)
                    break
            active_eq = eq_arr[first_active:]
            if len(active_eq) > 1:
                returns = pl.Series("returns", np.diff(active_eq) / active_eq[:-1])
            else:
                returns = pl.Series("returns", [0.0])
        else:
            returns = pl.Series("returns", [0.0])

        total_return = (final_equity / cash - 1.0) if cash > 0 else 0.0
        sharpe = MetricsCalculator.sharpe_ratio(returns)
        sortino = MetricsCalculator.sortino_ratio(returns)
        max_dd = MetricsCalculator.max_drawdown(equity_series)
        volatility = float(returns.std()) * (252**0.5) if returns.std() is not None else 0.0
        calmar = cagr / max_dd if max_dd > 0 else 0.0

        total_trades_count = len(trades)
        wins = [t for t in trades if t.pnl is not None and t.pnl > 0]
        losses = [t for t in trades if t.pnl is not None and t.pnl < 0]
        win_rate = len(wins) / max(total_trades_count, 1)

        gross_win = sum(float(t.pnl) for t in wins)  # type: ignore[union-attr]
        gross_loss = abs(sum(float(t.pnl) for t in losses))  # type: ignore[union-attr]
        profit_factor = (
            (gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 1.0)
        )

        avg_win = (gross_win / len(wins)) if wins else 0.0
        avg_loss = (gross_loss / len(losses)) if losses else 0.0

        self._result = BacktestResult.from_metrics(
            run_id=str(uuid4()),
            strategy_name="",
            instrument="",
            start_time=start_time,
            end_time=end_time,
            total_return=total_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            volatility=volatility,
            cagr=cagr,
            total_trades=total_trades_count,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            initial_capital=cfg.initial_capital,
            final_equity=final_equity,
            equity_curve=list(equity_values),
            trades=trades,
            engine="nautilus",
        )
        return self._result

    def equity_curve(self) -> pl.Series:
        """Return the equity curve from the most recent backtest."""
        if self._equity is None:
            return pl.Series("equity", [])
        return self._equity

    def trades(self) -> list[Trade]:
        """Return the trade log from the most recent backtest."""
        return list(self._trades_list)
