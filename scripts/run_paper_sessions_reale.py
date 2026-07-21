#!/usr/bin/env -S uv run --frozen
"""M32-023: Paper trading sessions — dati reali ES 1h.

Ogni sessione = un giorno di trading su dati storici ES futures (1h).
Pipeline completa:
  load data → reconciliation → signal → order → broker fill → P&L → flatten → report
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
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
    """Run one paper trading session on real ES 1h data for a single day."""
    from execution.brokers.config import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.brokers.types import BrokerOrder

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
        config = BrokerConfig()

    broker = PaperBroker(config)
    await broker.on_price_update(Decimal(str(closes[0])))

    position = 0
    trades: list[dict[str, Any]] = []
    equity = float(capital)
    equity_curve: list[float] = [equity]
    peak = equity
    hard_incidents: list[str] = []
    orders_submitted = 0
    fills_received = 0
    total_commission = 0.0

    # Track entry for P&L
    entry_price: float | None = None
    entry_bar: int | None = None

    for i in range(1, len(closes)):
        price = closes[i]
        sig = _signal(closes[: i + 1], fast, slow)
        ts = timestamps[i]

        # Trading logic: enter on signal, exit when signal reverses
        contracts = 0
        target_pos = position
        if sig == "BUY" and position <= 0:
            target_pos = 1
            contracts = 1 if position == 0 else 2
        elif sig == "SELL" and position >= 0:
            target_pos = -1
            contracts = 1 if position == 0 else 2

        # Execute order
        if contracts > 0:
            side = "buy" if target_pos > 0 else "sell"
            order = BrokerOrder(
                broker_order_id=f"s{session_id}_{i}",
                local_order_id=str(uuid4()),
                namespaced_id=f"session:{session_id}:{i}",
                instrument_id="ES",
                side=side,
                quantity=Decimal(str(contracts)),
                price=Decimal(str(price)),
                order_type="market",
                created_at=str(ts),
            )
            fills_before = len(broker._fills)
            await broker.submit_order(order)
            orders_submitted += 1

            new_fills = broker._fills[fills_before:]
            fills_received += len(new_fills)

            # Advance price for any resting orders
            await broker.on_price_update(Decimal(str(price)))

            # Get position
            positions = await broker.positions()
            pos_qty = sum(int(p.quantity) for p in positions)
            position = pos_qty

            # Record trade
            avg_fill = (
                float(statistics.mean([float(f.price) for f in new_fills])) if new_fills else price
            )
            comm = float(sum(float(f.commission) for f in new_fills))
            total_commission += comm

            trades.append(
                {
                    "bar": i,
                    "time": str(ts),
                    "price": price,
                    "side": side,
                    "contracts": contracts,
                    "fill_qty": sum(int(f.quantity) for f in new_fills),
                    "fill_price": round(avg_fill, 2),
                    "commission": round(comm, 4),
                    "position_after": position,
                }
            )

            if entry_price is None and position != 0:
                entry_price = price
                entry_bar = i
            elif position == 0:
                # Closed trade: record P&L
                if entry_price is not None:
                    trade_pnl = (price - entry_price) * (1 if target_pos > 0 else -1)
                    trades[-1]["trade_pnl"] = round(trade_pnl, 2)
                    trades[-1]["entry_price"] = round(entry_price, 2)
                    trades[-1]["bars_held"] = i - (entry_bar or i)
                entry_price = None
                entry_bar = None
            if position != 0 and entry_price is None:
                entry_price = price
                entry_bar = i

        # Track equity
        if position != 0 and entry_price is not None:
            unrealized = (price - entry_price) * position
            equity = float(capital) + unrealized - total_commission
        equity_curve.append(round(equity, 2))
        peak = max(peak, equity)

    # Flatten at end of session
    if position != 0:
        flat_side = "sell" if position > 0 else "buy"
        qty = abs(position)
        order = BrokerOrder(
            broker_order_id=f"s{session_id}_flat",
            local_order_id=str(uuid4()),
            namespaced_id=f"session:{session_id}:flat",
            instrument_id="ES",
            side=flat_side,
            quantity=Decimal(str(qty)),
            price=Decimal(str(closes[-1])),
            order_type="market",
            created_at=str(timestamps[-1]),
        )
        fills_before = len(broker._fills)
        await broker.submit_order(order)
        new_fills = broker._fills[fills_before:]
        if new_fills:
            fill_price = float(statistics.mean([float(f.price) for f in new_fills]))
            mult = -1 if flat_side == "sell" else 1
            trade_pnl = (fill_price - entry_price) * mult * qty if entry_price else 0
            trades.append(
                {
                    "bar": len(closes) - 1,
                    "time": str(timestamps[-1]),
                    "price": float(closes[-1]),
                    "side": flat_side,
                    "contracts": qty,
                    "fill_qty": sum(int(f.quantity) for f in new_fills),
                    "fill_price": round(fill_price, 2),
                    "commission": round(float(sum(float(f.commission) for f in new_fills)), 4),
                    "position_after": 0,
                    "trade_pnl": round(trade_pnl, 2),
                    "entry_price": round(entry_price, 2) if entry_price else 0,
                    "bars_held": len(closes) - (entry_bar or 0),
                    "flatten": True,
                }
            )
        position = 0
        equity = float(capital) - total_commission
        equity_curve.append(round(equity, 2))

    # ── Compute metrics ──────────────────────────────────────────────
    final_equity = equity_curve[-1] if equity_curve else float(capital)
    total_pnl = final_equity - float(capital)
    max_dd = max(0.0, max(peak - e for e in equity_curve)) if equity_curve else 0.0

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
    if orders_submitted > 0 and fills_received / orders_submitted < 0.5:
        hard_incidents.append(f"low_fill_rate: {fills_received}/{orders_submitted}")

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
        "fill_rate": round(fills_received / max(orders_submitted, 1), 4),
        "n_trades": n_closed,
        "total_commission": round(total_commission, 4),
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
        "final_position": position,
        "final_equity": round(final_equity, 2),
        "hard_incidents": hard_incidents,
        "passed": len(hard_incidents) == 0,
        "trades": trades,
    }


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
    sessions_data: list[dict[str, Any]], fast: int, slow: int, capital: float, realistic: bool
) -> list[dict[str, Any]]:
    """Run paper sessions on real historical data."""
    capital_dec = Decimal(str(capital))
    results: list[dict[str, Any]] = []
    n = min(len(sessions_data), 60) if realistic else min(len(sessions_data), 10)
    start_time = _time.monotonic()

    print(
        f"\nPaper Trading Sessions — {n} sessioni su dati reali ES 1h\n"
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


def _print_summary(results: list[dict[str, Any]]) -> None:
    """Print aggregate summary across all sessions."""
    n = len(results)
    passed = [r for r in results if r["passed"]]
    failed = [r for r in results if not r["passed"]]

    print("=" * 60)
    print("SUMMARY — Paper Trading Sessions (ES 1h)")
    print("=" * 60)
    print(f"\n  Sessioni totali:   {n}")
    print(f"  Passate:           {len(passed)} ({len(passed) / n:.0%})")
    print(f"  Fallite:           {len(failed)}")
    if failed:
        print(f"  Incidenti hard:    {sum(len(r['hard_incidents']) for r in failed)}")

    if passed:
        pnls = [r["total_pnl"] for r in passed]
        dds = [r["max_drawdown_pct"] for r in passed]
        shs = [r["sharpe"] for r in passed]
        sos = [r["sortino"] for r in passed]
        wrs = [r["win_rate"] for r in passed]
        pfs = [r["profit_factor"] for r in passed]
        nts = [r["n_trades"] for r in passed]
        rts = [r["return_pct"] for r in passed]

        print("\n  ─── Performance ───")
        print(f"  P&L totale:        ${sum(pnls):>+10.2f}")
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
        print(f"  Giorni positivi:   {pos} ({pos / len(pnls):.0%})")
        print(f"  Giorni negativi:   {neg} ({neg / len(pnls):.0%})")

        # Best/worst days
        best = max(results, key=lambda r: r["total_pnl"])
        worst = min(results, key=lambda r: r["total_pnl"])
        print("\n  ─── Miglior giornata ───")
        print(
            f"  [{best['session_id']}] {best['date']}  "
            f"P&L=${best['total_pnl']:>+8.2f}  S={best['sharpe']:.2f}  "
            f"WR={best['win_rate']:.0%}  PF={best['profit_factor']:.2f}"
        )
        print("  ─── Peggior giornata ───")
        print(
            f"  [{worst['session_id']}] {worst['date']}  "
            f"P&L=${worst['total_pnl']:>+8.2f}  S={worst['sharpe']:.2f}  "
            f"WR={worst['win_rate']:.0%}  PF={worst['profit_factor']:.2f}"
        )

    # Gate check
    print("\n  ─── Gate Check M32 ───")
    ok = True
    if failed:
        print(f"    ❌ {len(failed)} sessioni con incidenti hard")
        ok = False
    else:
        print("    ✅ 0 incidenti hard")

    if len(passed) / max(n, 1) < 0.9:
        print(f"    ❌ Pass rate {len(passed) / max(n, 1):.0%} < 90%")
        ok = False
    else:
        print(f"    ✅ Pass rate {len(passed) / max(n, 1):.0%}")

    if n < 60:
        print(f"    ⚠️  Solo {n} sessioni (target: 60)")
    else:
        print(f"    ✅ {n}/60 sessioni completate")

    avg_sharpe = statistics.mean([r["sharpe"] for r in passed]) if passed else 0
    if avg_sharpe < -0.5:
        print(f"    ❌ Sharpe medio {avg_sharpe:.2f} < -0.5")
        ok = False
    else:
        print(f"    ✅ Sharpe medio {avg_sharpe:.2f}")

    avg_dd = statistics.mean([r["max_drawdown_pct"] for r in passed]) if passed else 0
    if avg_dd > 3.0:
        print(f"    ❌ Drawdown medio {avg_dd:.2f}% > 3%")
        ok = False
    else:
        print(f"    ✅ Drawdown medio {avg_dd:.2f}%")

    print(f"\n  Gate: {'✅ PASS' if ok else '❌ FAIL'}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Paper trading sessions on real ES 1h data")
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--output", type=str, default="logs/paper_sessions_es1h.json")
    parser.add_argument("--data", type=str, default="data/ohlcv/ES_1h.parquet")
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
        f"{len(sessions_data)} sessioni (finestra 5gg, slide 1gg) "
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
    )

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "metadata": {
                    "data_source": args.data,
                    "sessions": len(sessions_data),
                    "sessions_run": len(results),
                    "fast": args.fast,
                    "slow": args.slow,
                    "capital": args.capital,
                    "realistic": realistic,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "results": [
                    {
                        k: r[k]
                        for k in (
                            "session_id",
                            "date",
                            "n_bars",
                            "total_pnl",
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
                            "passed",
                            "hard_incidents",
                        )
                    }
                    for r in results
                ],
            },
            f,
            indent=2,
        )
    print(f"\nRisultati salvati in {output_path}")

    _print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
