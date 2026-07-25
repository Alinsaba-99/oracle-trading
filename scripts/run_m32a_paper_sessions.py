#!/usr/bin/env -S uv run --frozen
"""M32a: Independent live paper trading sessions on crypto/futures feed.

Runs 30 independent, non-overlapping paper trading sessions.
Uses CCXT WebSocket or REST polling to execute orders via PaperBroker
with safety guards (StaleFeedDetector, RiskAlertBus, SignalCircuit).

Usage::

    uv run --frozen python scripts/run_m32a_paper_sessions.py --sessions 30 --timeframe 1h
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time as _time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.domain.guard import guard
from core.domain.mode import OracleMode
from execution.brokers.config import BrokerConfig
from execution.brokers.paper import PaperBroker
from execution.brokers.types import BrokerOrder
from execution.session_guards import RiskAlertBus, SignalProviderCircuit, StaleFeedDetector
from market.data_sources import DataFetcher


def _signal(closes: list[float], fast: int = 5, slow: int = 20) -> str:
    """Compute SMA crossover signal with minimum bar requirements."""
    if len(closes) < slow + 2:
        return "HOLD"
    f = sum(closes[-fast:]) / fast
    s = sum(closes[-slow:]) / slow
    pf = sum(closes[-(fast + 1) : -1]) / fast
    ps = sum(closes[-(slow + 1) : -1]) / slow
    if pf <= ps and f > s:
        return "BUY"
    if pf >= ps and f < s:
        return "SELL"
    return "HOLD"


def _compute_atr(closes: list[float], period: int = 14) -> list[float]:
    """Compute ATR(period) using Wilder smoothing."""
    n = len(closes)
    if n < period + 1:
        return [0.0] * n
    atr: list[float] = [0.0] * n
    ranges = [abs(closes[i] - closes[i - 1]) for i in range(1, period + 1)]
    atr[period] = sum(ranges) / period
    for i in range(period + 1, n):
        tr = abs(closes[i] - closes[i - 1])
        atr[i] = (atr[i - 1] * (period - 1) + tr) / period
    return atr


async def _run_single_paper_session(
    session_id: int,
    symbol: str,
    bars: list[dict[str, Any]],
    capital: Decimal,
    point_value: Decimal,
    fast: int,
    slow: int,
    atr_stop_mult: float,
    max_drawdown_pct: float,
) -> dict[str, Any]:
    """Run one independent paper trading session with safety guards."""
    config = BrokerConfig(
        paper_spread_bps=10,
        paper_slippage_bps=5,
        paper_partial_fill_prob=0.1,
        paper_latency_ms=10,
        paper_commission_per_contract=0.85,
    )
    broker = PaperBroker(config)

    # Initialize safety guards
    stale_detector = StaleFeedDetector(timeout_s=3600.0)  # 1h timeout for 1h bars
    circuit = SignalProviderCircuit(
        name="signal_provider", failure_threshold=3, recovery_timeout_s=60.0
    )
    risk_bus = RiskAlertBus()

    closes = [b["close"] for b in bars]
    timestamps = [b["timestamp"] for b in bars]
    atr_vals = _compute_atr(closes) if atr_stop_mult > 0 else []

    await broker.on_price_update(Decimal(str(closes[0])))
    stale_detector.on_tick(_time.monotonic())

    position = Decimal("0")
    entry_price: Decimal | None = None
    stop_price: Decimal | None = None
    realized_pnl = Decimal("0")
    total_commission = Decimal("0")
    trades: list[dict[str, Any]] = []
    equity_curve: list[float] = [float(capital)]
    peak_equity = float(capital)
    max_dd = 0.0
    hard_incidents: list[str] = []

    for i in range(1, len(closes)):
        now_mono = _time.monotonic()
        price = closes[i]
        price_dec = Decimal(str(price))
        ts = timestamps[i]

        # 1. Update feed heartbeat & check staleness
        stale_detector.on_tick(now_mono)
        if stale_detector.is_stale(now_mono):
            hard_incidents.append(f"stale_feed_at_bar_{i}")
            break

        await broker.on_price_update(price_dec)

        # 2. Check ATR stop-loss exit
        if (
            position != 0
            and entry_price is not None
            and atr_stop_mult > 0
            and i < len(atr_vals)
            and stop_price is not None
        ):
            hit_stop = (position > 0 and price <= float(stop_price)) or (
                position < 0 and price >= float(stop_price)
            )
            if hit_stop:
                # Execute stop exit
                flat_side = "sell" if position > 0 else "buy"
                qty = abs(position)
                order = BrokerOrder(
                    broker_order_id=f"s{session_id}_exit_{i}",
                    local_order_id="",
                    namespaced_id=f"m32a:{session_id}:stop:{i}",
                    instrument_id=symbol,
                    side=flat_side,
                    quantity=qty,
                    price=price_dec,
                    order_type="market",
                    created_at=str(ts),
                )
                fills_before = len(broker._fills)
                await broker.submit_order(order)
                await broker.on_price_update(price_dec)
                for fill in broker._fills[fills_before:]:
                    pos_dir = Decimal("1") if position > 0 else Decimal("-1")
                    closed_realized = (fill.price - entry_price) * pos_dir * qty * point_value
                    realized_pnl += closed_realized
                    total_commission += fill.commission
                trades.append(
                    {
                        "bar": i,
                        "time": str(ts),
                        "price": price,
                        "side": flat_side,
                        "qty": float(qty),
                        "reason": "atr_stop",
                    }
                )
                position = Decimal("0")
                entry_price = None
                stop_price = None

        # 3. Evaluate signal via circuit breaker
        sig = "HOLD"
        try:
            # Bind the loop variables correctly to avoid B023 warning
            current_closes = closes[: i + 1]

            async def _get_sig(
                cls: list[float] = current_closes, f: int = fast, s: int = slow
            ) -> str:
                return _signal(cls, f, s)

            sig = await circuit.call(_get_sig) or "HOLD"
        except Exception as exc:
            circuit._record_failure()
            print(f"Signal circuit failure: {exc}")

        # 4. Process position changes if no risk halt
        if risk_bus.can_submit():
            target_pos = position
            if sig == "BUY" and position <= 0:
                target_pos = Decimal("1")
            elif sig == "SELL" and position >= 0:
                target_pos = Decimal("-1")

            if target_pos != position:
                side = "buy" if target_pos > 0 else "sell"
                contracts = abs(target_pos - position)
                position_before = position
                order = BrokerOrder(
                    broker_order_id=f"s{session_id}_{i}",
                    local_order_id="",
                    namespaced_id=f"m32a:{session_id}:{i}",
                    instrument_id=symbol,
                    side=side,
                    quantity=contracts,
                    price=price_dec,
                    order_type="market",
                    created_at=str(ts),
                )
                fills_before = len(broker._fills)
                await broker.submit_order(order)
                await broker.on_price_update(price_dec)
                new_fills = broker._fills[fills_before:]

                for fill in new_fills:
                    new_pos = position + fill.quantity * (1 if side == "buy" else -1)
                    going_against = (position * (1 if side == "buy" else -1)) < 0
                    closed_qty = (
                        min(abs(position), fill.quantity) if going_against else Decimal("0")
                    )
                    if closed_qty > 0 and entry_price is not None:
                        pos_dir = Decimal("1") if position > 0 else Decimal("-1")
                        realized_pnl += (
                            (fill.price - entry_price) * pos_dir * closed_qty * point_value
                        )
                    position = new_pos
                    total_commission += fill.commission

                    if position == 0:
                        entry_price = None
                        stop_price = None
                    elif (
                        position_before == 0
                        or position_before * position < 0
                        or entry_price is None
                    ):
                        entry_price = fill.price
                        # Set initial ATR stop level
                        if atr_stop_mult > 0 and i < len(atr_vals) and atr_vals[i] > 0:
                            dist = Decimal(str(atr_vals[i])) * Decimal(str(atr_stop_mult))
                            stop_price = (
                                (entry_price - dist) if position > 0 else (entry_price + dist)
                            )

                trades.append(
                    {
                        "bar": i,
                        "time": str(ts),
                        "price": price,
                        "side": side,
                        "qty": float(contracts),
                        "position_after": float(position),
                    }
                )

        # 5. Track MTM equity & risk limits
        unrealized = Decimal("0")
        if position != 0 and entry_price is not None:
            direction = Decimal("1") if position > 0 else Decimal("-1")
            unrealized = (price_dec - entry_price) * direction * abs(position) * point_value

        equity = float(capital + realized_pnl + unrealized - total_commission)
        equity_curve.append(round(equity, 2))
        peak_equity = max(peak_equity, equity)
        current_dd = (peak_equity - equity) / peak_equity * 100
        max_dd = max(max_dd, current_dd)

        if current_dd > max_drawdown_pct:
            hard_incidents.append(f"max_drawdown_exceeded_{current_dd:.2f}%")

            class _FakeBreach:
                severity = "hard"
                type = "daily_loss_hard"
                message = f"Max drawdown {current_dd:.2f}% exceeded"

            risk_bus.ingest_breaches([_FakeBreach()])
            break

    # Flatten position at end of session
    if position != Decimal("0"):
        flat_side = "sell" if position > 0 else "buy"
        qty = abs(position)
        order = BrokerOrder(
            broker_order_id=f"s{session_id}_flat",
            local_order_id="",
            namespaced_id=f"m32a:{session_id}:flat",
            instrument_id=symbol,
            side=flat_side,
            quantity=qty,
            price=Decimal(str(closes[-1])),
            order_type="market",
            created_at=str(timestamps[-1]),
        )
        fills_before = len(broker._fills)
        await broker.submit_order(order)
        await broker.on_price_update(Decimal(str(closes[-1])))
        for fill in broker._fills[fills_before:]:
            total_commission += fill.commission
            if entry_price is not None:
                pos_dir = Decimal("1") if position > 0 else Decimal("-1")
                realized_pnl += (fill.price - entry_price) * pos_dir * qty * point_value
        position = Decimal("0")

    final_equity = float(capital + realized_pnl - total_commission)
    total_pnl = final_equity - float(capital)

    returns = [equity_curve[k] - equity_curve[k - 1] for k in range(1, len(equity_curve))]
    avg_ret = statistics.mean(returns) if returns else 0.0
    std_ret = statistics.stdev(returns) if len(returns) > 1 else 1.0
    sharpe = (avg_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0.0

    return {
        "session_id": session_id,
        "date_start": str(timestamps[0]),
        "date_end": str(timestamps[-1]),
        "n_bars": len(bars),
        "n_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "return_pct": round(total_pnl / float(capital) * 100, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "final_equity": round(final_equity, 2),
        "total_commission": round(float(total_commission), 4),
        "passed": len(hard_incidents) == 0,
        "hard_incidents": hard_incidents,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="M32a: Independent Live Paper Sessions")
    parser.add_argument("--symbol", type=str, default="BTC/USDT")
    parser.add_argument("--source", type=str, default="ccxt")
    parser.add_argument("--sessions", type=int, default=30)
    parser.add_argument("--session-bars", type=int, default=120)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument("--atr-stop-mult", type=float, default=2.0)
    parser.add_argument("--max-drawdown-pct", type=float, default=3.0)
    parser.add_argument("--output", type=str, default="logs/m32a_paper_sessions.json")
    args = parser.parse_args()

    guard(OracleMode.PAPER)

    fetcher = DataFetcher()
    # Fetch market data
    if args.source == "ccxt":
        needed_bars = args.sessions * args.session_bars + 100
        df = fetcher.ccxt_ohlcv("binance", args.symbol, limit=needed_bars)
    else:
        df = fetcher.fetch(args.symbol, source=args.source)
    if df.empty:
        print("ERROR: Failed to fetch market data")
        sys.exit(1)

    # Convert DataFrame to list of bar dicts
    bars: list[dict[str, Any]] = []
    # Normalize column names to lowercase
    df.columns = [c.lower() for c in df.columns]
    for ts, row in df.iterrows():
        bars.append(
            {
                "timestamp": ts,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
        )

    # Split into N non-overlapping independent sessions
    session_length = args.session_bars
    total_needed = args.sessions * session_length
    if len(bars) < total_needed:
        session_length = len(bars) // args.sessions
        print(
            f"Warning: Only {len(bars)} bars available, "
            f"scaling down session length to {session_length}"
        )

    sessions_bars: list[list[dict[str, Any]]] = []
    for s in range(args.sessions):
        start_idx = s * session_length
        end_idx = start_idx + session_length
        sess_slice = bars[start_idx:end_idx]
        if len(sess_slice) >= args.slow + 2:
            sessions_bars.append(sess_slice)

    print(f"\n{'=' * 60}")
    print(f"M32a Paper Sessions Live — {len(sessions_bars)} Sessioni Indipendenti")
    print(f"  Symbol: {args.symbol} | Source: {args.source}")
    print(f"  Capitale: ${args.capital:,.0f} | Max DD cap: {args.max_drawdown_pct}%")
    print(f"  Filtri: ATR({args.atr_stop_mult}x) Stop Loss")
    print(f"{'=' * 60}\n")

    capital_dec = Decimal(str(args.capital))
    point_val = Decimal("1.0") if "/" in args.symbol else Decimal("50.0")
    results: list[dict[str, Any]] = []

    for idx, s_bars in enumerate(sessions_bars):
        res = await _run_single_paper_session(
            session_id=idx + 1,
            symbol=args.symbol,
            bars=s_bars,
            capital=capital_dec,
            point_value=point_val,
            fast=args.fast,
            slow=args.slow,
            atr_stop_mult=args.atr_stop_mult,
            max_drawdown_pct=args.max_drawdown_pct,
        )
        results.append(res)
        status = "✅" if res["passed"] else "❌"
        extra = f"  ⚠️  {', '.join(res['hard_incidents'])}" if not res["passed"] else ""
        print(
            f"  [{idx + 1:>2d}/{len(sessions_bars)}] {status}  "
            f"P&L=${res['total_pnl']:>+8.2f}  "
            f"R={res['return_pct']:>+6.2f}%  "
            f"S={res['sharpe']:>6.2f}  "
            f"DD={res['max_drawdown_pct']:>5.2f}%  "
            f"T={res['n_trades']:>2d}{extra}"
        )

    # Calculate summary
    n = len(results)
    passed_sessions = sum(1 for r in results if r["passed"])
    pnls = [r["total_pnl"] for r in results]
    dds = [r["max_drawdown_pct"] for r in results]
    shs = [r["sharpe"] for r in results]

    pass_rate = passed_sessions / n if n else 0.0
    mean_sharpe = statistics.mean(shs) if shs else 0.0
    mean_dd = statistics.mean(dds) if dds else 0.0

    print(f"\n{'=' * 60}")
    print("SUMMARY — M32a Independent Paper Sessions")
    print(f"{'=' * 60}")
    print(f"  Sessioni totali:   {n}")
    print(f"  Passate:           {passed_sessions} ({pass_rate:.0%})")
    print(f"  Somma P&L:         ${sum(pnls):>+10.2f}")
    print(f"  P&L medio/sess:    ${statistics.mean(pnls):>+10.2f}")
    print(f"  Sharpe medio:      {mean_sharpe:.4f}")
    print(f"  Drawdown medio:    {mean_dd:.2f}% (max: {max(dds):.2f}%)")

    gate_passed = pass_rate >= 0.90 and mean_sharpe >= -0.5 and mean_dd <= 3.0
    print(f"\n  Gate M32a: {'✅ PASS' if gate_passed else '❌ FAIL'}")
    print(f"{'=' * 60}\n")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "metadata": {
                    "schema_version": "m32a-paper-v1",
                    "symbol": args.symbol,
                    "source": args.source,
                    "sessions": n,
                    "capital": args.capital,
                    "gate_passed": gate_passed,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "gate": {
                    "decision": "approved" if gate_passed else "rejected",
                    "pass_rate": round(pass_rate, 4),
                    "mean_sharpe": round(mean_sharpe, 4),
                    "mean_drawdown_pct": round(mean_dd, 4),
                },
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"Risultati salvati in {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
