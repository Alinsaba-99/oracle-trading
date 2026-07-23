#!/usr/bin/env -S uv run --frozen
"""M32 diagnostic: rolling historical paper-replay windows on real ES 1h data.

Each observation is a five-trading-day rolling window. Adjacent windows overlap
and are not independent live paper sessions.
Pipeline completa:
  load data → signal → order → broker fill → P&L → flatten → report
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import random
import statistics
import sys
import time as _time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


def _signal(prices: list[float], fast: int, slow: int) -> str:
    """SMA crossover: BUY when fast crosses above slow, SELL on cross below."""
    if len(prices) < slow + 2:
        return "HOLD"
    f = sum(prices[-fast:]) / fast
    s = sum(prices[-slow:]) / slow
    pf = sum(prices[-(fast + 1) : -1]) / fast
    ps = sum(prices[-(slow + 1) : -1]) / slow
    if pf <= ps and f > s:
        return "BUY"
    if pf >= ps and f < s:
        return "SELL"
    return "HOLD"


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------


async def _run_one_session(
    session_id: int,
    trading_date: date,
    closes: list[float],
    timestamps: list[pd.Timestamp],
    fast: int,
    slow: int,
    capital: Decimal,
    realistic: bool,
) -> dict[str, Any]:
    """Run one five-day paper replay window on real ES 1h data."""
    from execution.brokers.config import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.brokers.types import BrokerOrder
    from market.contracts import ES

    # Broker config
    if realistic:
        config = BrokerConfig(
            paper_spread_bps=15,
            paper_slippage_bps=8,
            paper_partial_fill_prob=0.2,
            paper_latency_ms=15,
            paper_commission_per_contract=0.85,
        )
    else:
        config = BrokerConfig(
            paper_spread_bps=0,
            paper_slippage_bps=0,
            paper_partial_fill_prob=0,
            paper_latency_ms=0,
            paper_commission_per_contract=0,
        )

    broker = PaperBroker(config)
    await broker.on_price_update(Decimal(str(closes[0])))

    position = Decimal("0")
    trades: list[dict[str, Any]] = []
    equity = float(capital)
    equity_curve: list[float] = [equity]
    peak = equity
    max_drawdown = 0.0
    hard_incidents: list[str] = []
    orders_submitted = 0
    fills_received = 0
    quantity_submitted = Decimal("0")
    quantity_filled = Decimal("0")
    total_commission = Decimal("0")
    realized_pnl = Decimal("0")
    point_value = ES.point_value

    # Track entry for P&L
    entry_price: Decimal | None = None
    entry_bar: int | None = None

    for i in range(1, len(closes)):
        price = closes[i]
        sig = _signal(closes[: i + 1], fast, slow)
        ts = timestamps[i]
        price_decimal = Decimal(str(price))

        # The synthetic broker price must advance on every bar, not only when
        # an order is submitted. Otherwise the end-of-window flatten uses a
        # stale price and the resulting P&L is not economically meaningful.
        await broker.on_price_update(price_decimal)

        # Trading logic: enter on signal, exit when signal reverses
        contracts = Decimal("0")
        target_pos = position
        if sig == "BUY" and position <= 0:
            target_pos = Decimal("1")
            contracts = abs(target_pos - position)
        elif sig == "SELL" and position >= 0:
            target_pos = Decimal("-1")
            contracts = abs(target_pos - position)

        # Execute order
        if contracts > Decimal("0"):
            side = "buy" if target_pos > 0 else "sell"
            position_before = position
            order = BrokerOrder(
                broker_order_id=f"s{session_id}_{i}",
                local_order_id=str(uuid4()),
                namespaced_id=f"session:{session_id}:{i}",
                instrument_id="ES",
                side=side,
                quantity=contracts,
                price=Decimal(str(price)),
                order_type="market",
                created_at=str(ts),
            )
            fills_before = len(broker._fills)
            await broker.submit_order(order)
            orders_submitted += 1
            quantity_submitted += contracts

            # A partial market fill leaves the remainder submitted. Replaying
            # the same market tick consumes that remainder and lets us account
            # for every fill produced by the order.
            await broker.on_price_update(price_decimal)
            new_fills = broker._fills[fills_before:]
            fills_received += len(new_fills)
            filled_qty = sum((fill.quantity for fill in new_fills), Decimal("0"))
            quantity_filled += filled_qty

            order_realized = Decimal("0")
            order_closed_qty = Decimal("0")
            for fill in new_fills:
                position, entry_price, fill_realized, fill_closed_qty = _apply_fill(
                    position=position,
                    entry_price=entry_price,
                    side=side,
                    quantity=fill.quantity,
                    fill_price=fill.price,
                    point_value=point_value,
                )
                order_realized += fill_realized
                order_closed_qty += fill_closed_qty
                total_commission += fill.commission
            realized_pnl += order_realized

            # Record trade
            avg_fill = (
                float(statistics.mean([float(f.price) for f in new_fills])) if new_fills else price
            )
            comm = sum((fill.commission for fill in new_fills), Decimal("0"))

            trade: dict[str, Any] = {
                "bar": i,
                "time": str(ts),
                "price": price,
                "side": side,
                "contracts": float(contracts),
                "fill_qty": float(filled_qty),
                "fill_price": round(avg_fill, 2),
                "commission": round(float(comm), 4),
                "position_after": float(position),
            }
            if order_closed_qty > Decimal("0"):
                trade["trade_pnl"] = round(float(order_realized), 2)
                trade["closed_qty"] = float(order_closed_qty)
                trade["bars_held"] = i - (entry_bar if entry_bar is not None else i)
            trades.append(trade)

            if position == Decimal("0"):
                entry_bar = None
            elif position_before == Decimal("0") or position_before * position < 0:
                entry_bar = i

        # Track equity
        unrealized = _unrealized_pnl(position, entry_price, price_decimal, point_value)
        equity = float(capital + realized_pnl + unrealized - total_commission)
        equity_curve.append(round(equity, 2))
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    # Flatten at end of session
    if position != Decimal("0"):
        flat_side = "sell" if position > 0 else "buy"
        qty = abs(position)
        order = BrokerOrder(
            broker_order_id=f"s{session_id}_flat",
            local_order_id=str(uuid4()),
            namespaced_id=f"session:{session_id}:flat",
            instrument_id="ES",
            side=flat_side,
            quantity=qty,
            price=Decimal(str(closes[-1])),
            order_type="market",
            created_at=str(timestamps[-1]),
        )
        fills_before = len(broker._fills)
        await broker.submit_order(order)
        orders_submitted += 1
        quantity_submitted += qty
        await broker.on_price_update(Decimal(str(closes[-1])))
        new_fills = broker._fills[fills_before:]
        fills_received += len(new_fills)
        filled_qty = sum((fill.quantity for fill in new_fills), Decimal("0"))
        quantity_filled += filled_qty
        if new_fills:
            fill_price = float(statistics.mean([float(f.price) for f in new_fills]))
            flatten_realized = Decimal("0")
            flatten_closed_qty = Decimal("0")
            flatten_commission = Decimal("0")
            for fill in new_fills:
                position, entry_price, fill_realized, fill_closed_qty = _apply_fill(
                    position=position,
                    entry_price=entry_price,
                    side=flat_side,
                    quantity=fill.quantity,
                    fill_price=fill.price,
                    point_value=point_value,
                )
                flatten_realized += fill_realized
                flatten_closed_qty += fill_closed_qty
                flatten_commission += fill.commission
            realized_pnl += flatten_realized
            total_commission += flatten_commission
            trades.append(
                {
                    "bar": len(closes) - 1,
                    "time": str(timestamps[-1]),
                    "price": float(closes[-1]),
                    "side": flat_side,
                    "contracts": float(qty),
                    "fill_qty": float(filled_qty),
                    "fill_price": round(fill_price, 2),
                    "commission": round(float(flatten_commission), 4),
                    "position_after": float(position),
                    "trade_pnl": round(float(flatten_realized), 2),
                    "closed_qty": float(flatten_closed_qty),
                    "bars_held": len(closes) - (entry_bar or 0),
                    "flatten": True,
                }
            )
        equity = float(capital + realized_pnl - total_commission)
        equity_curve.append(round(equity, 2))
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    # ── Compute metrics ──────────────────────────────────────────────
    final_equity = equity_curve[-1] if equity_curve else float(capital)
    total_pnl = final_equity - float(capital)
    max_dd = max_drawdown

    # Trade metrics (closed trades only)
    closed = [t for t in trades if t.get("trade_pnl") is not None]
    n_closed = len(closed)
    winners = [t for t in closed if t["trade_pnl"] > 0]
    losers = [t for t in closed if t["trade_pnl"] <= 0]
    win_rate = len(winners) / n_closed if n_closed > 0 else 0.0

    avg_win = statistics.mean([t["trade_pnl"] for t in winners]) if winners else 0.0
    avg_loss = statistics.mean([t["trade_pnl"] for t in losers]) if losers else 0.0
    gross_profit = sum(t["trade_pnl"] for t in winners)
    gross_loss = abs(sum(t["trade_pnl"] for t in losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    # Sharpe (daily approximation using bar returns)
    returns = [equity_curve[i] - equity_curve[i - 1] for i in range(1, len(equity_curve))]
    avg_ret = statistics.mean(returns) if returns else 0.0
    std_ret = statistics.stdev(returns) if len(returns) > 1 else 1.0
    sharpe = (avg_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0.0

    # Sortino (downside deviation only)
    downside = [r for r in returns if r < 0]
    downside_std = statistics.stdev(downside) if len(downside) > 1 else 1.0
    sortino = (avg_ret / downside_std) * math.sqrt(252) if downside_std > 0 else 0.0

    # Hard incidents
    if max_dd > float(capital) * 0.05:
        hard_incidents.append(f"max_dd_exceeded: {max_dd:.2f} > 5% capital")
    if fills_received == 0 and orders_submitted > 0:
        hard_incidents.append("zero_fills_with_orders")
    fill_rate = quantity_filled / quantity_submitted if quantity_submitted > 0 else Decimal("1")
    if fill_rate < Decimal("0.5"):
        hard_incidents.append(f"low_fill_rate: {quantity_filled}/{quantity_submitted}")
    if position != Decimal("0"):
        hard_incidents.append(f"non_flat_end_state: {position}")

    return {
        "session_id": session_id,
        "date": str(trading_date),
        "n_bars": len(closes),
        "price_first": round(closes[0], 2),
        "price_last": round(closes[-1], 2),
        "price_min": round(min(closes), 2),
        "price_max": round(max(closes), 2),
        "orders_submitted": orders_submitted,
        "fills_received": fills_received,
        "quantity_submitted": float(quantity_submitted),
        "quantity_filled": float(quantity_filled),
        "fill_rate": round(float(fill_rate), 4),
        "n_trades": n_closed,
        "gross_realized_pnl": round(float(realized_pnl), 2),
        "total_commission": round(float(total_commission), 4),
        "total_pnl": round(total_pnl, 2),
        "return_pct": round(total_pnl / float(capital) * 100, 4),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd / float(capital) * 100, 4),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 4),
        "final_position": float(position),
        "final_equity": round(final_equity, 2),
        "hard_incidents": hard_incidents,
        "passed": len(hard_incidents) == 0,
        "trades": trades,
    }


def _apply_fill(
    *,
    position: Decimal,
    entry_price: Decimal | None,
    side: str,
    quantity: Decimal,
    fill_price: Decimal,
    point_value: Decimal,
) -> tuple[Decimal, Decimal | None, Decimal, Decimal]:
    """Apply one fill to single-instrument position accounting.

    Returns ``(new_position, new_entry_price, realized_pnl, closed_quantity)``.
    The helper supports entry, scale-in, partial close and reversal.
    """
    if quantity <= 0:
        return position, entry_price, Decimal("0"), Decimal("0")

    signed_quantity = quantity if side == "buy" else -quantity
    new_position = position + signed_quantity

    if position == 0 or position * signed_quantity > 0:
        previous_notional = (entry_price or fill_price) * abs(position)
        combined_quantity = abs(position) + quantity
        new_entry = (previous_notional + fill_price * quantity) / combined_quantity
        return new_position, new_entry, Decimal("0"), Decimal("0")

    if entry_price is None:
        raise ValueError("entry_price is required when closing an open position")

    closed_quantity = min(abs(position), quantity)
    direction = Decimal("1") if position > 0 else Decimal("-1")
    realized_pnl = (fill_price - entry_price) * direction * closed_quantity * point_value

    if new_position == 0:
        new_entry = None
    elif position * new_position < 0:
        new_entry = fill_price
    else:
        new_entry = entry_price
    return new_position, new_entry, realized_pnl, closed_quantity


def _unrealized_pnl(
    position: Decimal, entry_price: Decimal | None, current_price: Decimal, point_value: Decimal
) -> Decimal:
    """Return mark-to-market P&L for the current ES position."""
    if position == 0 or entry_price is None:
        return Decimal("0")
    direction = Decimal("1") if position > 0 else Decimal("-1")
    return (current_price - entry_price) * direction * abs(position) * point_value


# ---------------------------------------------------------------------------
# Load real ES 1h data
# ---------------------------------------------------------------------------


def _load_es_data(path: str = "data/ohlcv/ES_1h.parquet") -> pd.DataFrame:
    """Load ES 1h OHLCV data, return with DatetimeIndex."""
    df = pd.read_parquet(path)
    if "Datetime" in df.index.name or df.index.name == "Datetime":
        pass  # already indexed by datetime
    elif "timestamp" in df.columns:
        df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df


def _split_into_sessions(
    df: pd.DataFrame, window_days: int = 5, slide_days: int = 1
) -> list[dict[str, Any]]:
    """Split dataframe into multi-day sessions con finestra mobile.

    Ogni sessione copre ``window_days`` giorni, scorrendo di
    ``slide_days`` alla volta. Con 124 giorni da' ~120 sessioni.
    """
    df = df.copy()
    df["date"] = df.index.date
    unique_days = sorted(df["date"].unique())
    sessions: list[dict[str, Any]] = []

    for i in range(0, len(unique_days) - window_days + 1, slide_days):
        batch = unique_days[i : i + window_days]
        batch_df = df[df["date"].isin(batch)]
        if len(batch_df) < 20:
            continue
        sessions.append(
            {
                "date_start": batch[0],
                "date_end": batch[-1],
                "n_days": len(batch),
                "n_bars": len(batch_df),
                "closes": batch_df["Close"].tolist(),
                "timestamps": batch_df.index.tolist(),
            }
        )
    return sessions


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_sessions(
    sessions_data: list[dict[str, Any]],
    fast: int,
    slow: int,
    capital: float,
    realistic: bool,
    seed: int,
) -> list[dict[str, Any]]:
    """Run paper sessions on real historical data."""
    random.seed(seed)
    capital_dec = Decimal(str(capital))
    results: list[dict[str, Any]] = []
    n = min(len(sessions_data), 60) if realistic else min(len(sessions_data), 10)
    start_time = _time.monotonic()

    print(
        f"\nPaper Replay Diagnostics — {n} finestre mobili su dati reali ES 1h\n"
        f"  Periodo: {sessions_data[0]['date_start']} → {sessions_data[n - 1]['date_start']}\n"
        f"  Strategia: SMA({fast}/{slow})\n"
        f"  Capitale: ${capital:,.0f}\n"
        f"  Broker realistico: {realistic}\n"
    )

    for idx in range(n):
        sd = sessions_data[idx]
        sess_start = _time.monotonic()

        result = await _run_one_session(
            session_id=idx + 1,
            trading_date=sd["date_start"],
            closes=sd["closes"],
            timestamps=sd["timestamps"],
            fast=fast,
            slow=slow,
            capital=capital_dec,
            realistic=realistic,
        )
        elapsed = _time.monotonic() - sess_start
        result["elapsed_seconds"] = round(elapsed, 2)
        results.append(result)

        status = "✅" if result["passed"] else "❌"
        extra = ""
        if not result["passed"]:
            extra = f"  ⚠️  {'; '.join(result['hard_incidents'])}"
        print(
            f"  [{idx + 1:>3d}/{n}] {status}  "
            f"{sd['date_start']}  "
            f"P&L=${result['total_pnl']:>+8.2f}  "
            f"R={result['return_pct']:>+6.2f}%  "
            f"S={result['sharpe']:>6.2f}  "
            f"WR={result['win_rate']:.0%}  "
            f"PF={result['profit_factor']:.2f}  "
            f"DD={result['max_drawdown_pct']:>5.2f}%  "
            f"T={result['n_trades']:>2d}  "
            f"{elapsed:>4.1f}s{extra}",
            flush=True,
        )

    total_elapsed = _time.monotonic() - start_time
    print(f"\n  Tempo totale: {total_elapsed:.1f}s  ({total_elapsed / max(n, 1):.1f}s/sessione)\n")

    return results


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def _evaluate_gate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate the M32 diagnostic gate across every replay window."""
    n = len(results)
    passed_windows = sum(bool(result["passed"]) for result in results)
    hard_incidents = sum(len(result["hard_incidents"]) for result in results)
    pass_rate = passed_windows / n if n else 0.0
    average_sharpe = statistics.mean(result["sharpe"] for result in results) if results else 0.0
    average_drawdown = (
        statistics.mean(result["max_drawdown_pct"] for result in results) if results else 0.0
    )
    checks = {
        "minimum_windows": n >= 60,
        "zero_hard_incidents": hard_incidents == 0,
        "minimum_pass_rate": pass_rate >= 0.90,
        "minimum_average_sharpe": average_sharpe >= -0.5,
        "maximum_average_drawdown": average_drawdown <= 3.0,
    }
    return {
        "decision": "approved" if all(checks.values()) else "rejected",
        "checks": checks,
        "windows": n,
        "passed_windows": passed_windows,
        "failed_windows": n - passed_windows,
        "hard_incidents": hard_incidents,
        "pass_rate": round(pass_rate, 4),
        "average_sharpe": round(average_sharpe, 4),
        "average_drawdown_pct": round(average_drawdown, 4),
    }


def _print_summary(results: list[dict[str, Any]], gate: dict[str, Any]) -> None:
    """Print aggregate summary across all sessions."""
    n = len(results)
    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]

    print("=" * 60)
    print("SUMMARY — Rolling Historical Paper Replay (ES 1h)")
    print("=" * 60)
    print(f"\n  Sessioni totali:   {n}")
    print(f"  Passate:           {len(passed)} ({len(passed) / n:.0%})")
    print(f"  Fallite:           {len(failed)}")
    if failed:
        print(f"  Incidenti hard:    {sum(len(r['hard_incidents']) for r in failed)}")

    if results:
        pnls = [r["total_pnl"] for r in results]
        dds = [r["max_drawdown_pct"] for r in results]
        shs = [r["sharpe"] for r in results]
        sos = [r["sortino"] for r in results]
        wrs = [r["win_rate"] for r in results]
        pfs = [r["profit_factor"] for r in results]
        nts = [r["n_trades"] for r in results]
        rts = [r["return_pct"] for r in results]

        print("\n  ─── Performance ───")
        print(f"  Somma P&L finestre:${sum(pnls):>+10.2f}  (non portfolio additivo)")
        print(
            f"  P&L medio:         ${statistics.mean(pnls):>+10.2f}  "
            f"(std=${statistics.stdev(pnls):.2f})"
        )
        print(f"  P&L mediano:       ${sorted(pnls)[len(pnls) // 2]:>+10.2f}")
        print(f"  Return medio:      {statistics.mean(rts):>+8.2f}%")
        print(
            f"  Sharpe medio:      {statistics.mean(shs):>8.4f}  (std={statistics.stdev(shs):.4f})"
        )
        print(f"  Sortino medio:     {statistics.mean(sos):>8.4f}")
        print(f"  Win rate medio:    {statistics.mean(wrs):>8.2%}")
        print(f"  Profit factor med: {statistics.mean(pfs):>8.2f}")

        print("\n  ─── Rischio ───")
        print(f"  Drawdown medio:    {statistics.mean(dds):>8.2f}%  (max: {max(dds):.2f}%)")
        print(f"  Trades medi/sess:  {statistics.mean(nts):>8.1f}")

        print("\n  ─── Distribuzione P&L ───")
        pos = sum(1 for p in pnls if p > 0)
        neg = sum(1 for p in pnls if p <= 0)
        print(f"  Finestre positive: {pos} ({pos / len(pnls):.0%})")
        print(f"  Finestre negative: {neg} ({neg / len(pnls):.0%})")

        # Best/worst days
        best = max(results, key=lambda r: r["total_pnl"])
        worst = min(results, key=lambda r: r["total_pnl"])
        print("\n  ─── Migliore finestra ───")
        print(
            f"  [{best['session_id']}] {best['date']}  "
            f"P&L=${best['total_pnl']:>+8.2f}  S={best['sharpe']:.2f}  "
            f"WR={best['win_rate']:.0%}  PF={best['profit_factor']:.2f}"
        )
        print("  ─── Peggiore finestra ───")
        print(
            f"  [{worst['session_id']}] {worst['date']}  "
            f"P&L=${worst['total_pnl']:>+8.2f}  S={worst['sharpe']:.2f}  "
            f"WR={worst['win_rate']:.0%}  PF={worst['profit_factor']:.2f}"
        )

    # Gate check — all windows count, including failed windows.
    print("\n  ─── Gate Check M32 ───")
    if gate["checks"]["zero_hard_incidents"]:
        print("    ✅ 0 incidenti hard")
    else:
        print(f"    ❌ {gate['hard_incidents']} incidenti hard")

    if gate["checks"]["minimum_pass_rate"]:
        print(f"    ✅ Pass rate {gate['pass_rate']:.0%}")
    else:
        print(f"    ❌ Pass rate {gate['pass_rate']:.0%} < 90%")

    if gate["checks"]["minimum_windows"]:
        print(f"    ✅ {n}/60 finestre completate")
    else:
        print(f"    ⚠️  Solo {n} sessioni (target: 60)")

    if gate["checks"]["minimum_average_sharpe"]:
        print(f"    ✅ Sharpe medio {gate['average_sharpe']:.2f}")
    else:
        print(f"    ❌ Sharpe medio {gate['average_sharpe']:.2f} < -0.5")

    if gate["checks"]["maximum_average_drawdown"]:
        print(f"    ✅ Drawdown medio {gate['average_drawdown_pct']:.2f}%")
    else:
        print(f"    ❌ Drawdown medio {gate['average_drawdown_pct']:.2f}% > 3%")

    print(f"\n  Gate: {'✅ PASS' if gate['decision'] == 'approved' else '❌ FAIL'}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rolling historical paper-replay diagnostics on real ES 1h data"
    )
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--output", type=str, default="logs/paper_sessions_es1h.json")
    parser.add_argument("--data", type=str, default="data/ohlcv/ES_1h.parquet")
    parser.add_argument("--seed", type=int, default=32023)
    parser.add_argument(
        "--realistic",
        action="store_true",
        default=True,
        help="Use realistic broker settings (default: True)",
    )
    parser.add_argument(
        "--dry", action="store_true", help="Dry-run with realistic=False for comparison"
    )
    args = parser.parse_args()

    realistic = args.realistic and not args.dry

    # Load real data
    df = _load_es_data(args.data)
    sessions_data = _split_into_sessions(df, window_days=5, slide_days=1)
    print(
        f"Caricati {len(df)} barre ES 1h | "
        f"{len(sessions_data)} finestre mobili (5gg, slide 1gg) "
        f"da {sessions_data[0]['date_start']} "
        f"a {sessions_data[-1]['date_start']}"
    )

    # Run sessions
    results = await run_sessions(
        sessions_data=sessions_data,
        fast=args.fast,
        slow=args.slow,
        capital=args.capital,
        realistic=realistic,
        seed=args.seed,
    )
    gate = _evaluate_gate(results)

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "metadata": {
                    "schema_version": "m32-paper-v2",
                    "observation_kind": "rolling_historical_paper_replay_window",
                    "live_market_data": False,
                    "independent_sessions": False,
                    "gate_scope": "diagnostic_only",
                    "data_source": args.data,
                    "data_sha256": hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
                    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "sessions": len(sessions_data),
                    "sessions_run": len(results),
                    "fast": args.fast,
                    "slow": args.slow,
                    "capital": args.capital,
                    "realistic": realistic,
                    "seed": args.seed,
                    "window_days": 5,
                    "slide_days": 1,
                    "point_value": 50.0,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "results": [
                    {
                        k: r[k]
                        for k in (
                            "session_id",
                            "date",
                            "n_bars",
                            "price_first",
                            "price_last",
                            "price_min",
                            "price_max",
                            "orders_submitted",
                            "fills_received",
                            "quantity_submitted",
                            "quantity_filled",
                            "total_pnl",
                            "gross_realized_pnl",
                            "return_pct",
                            "sharpe",
                            "sortino",
                            "win_rate",
                            "profit_factor",
                            "max_drawdown_pct",
                            "n_trades",
                            "fill_rate",
                            "total_commission",
                            "final_position",
                            "final_equity",
                            "passed",
                            "hard_incidents",
                        )
                    }
                    for r in results
                ],
                "gate": gate,
            },
            f,
            indent=2,
        )
    print(f"\nRisultati salvati in {output_path}")

    _print_summary(results, gate)
    if gate["decision"] != "approved":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
