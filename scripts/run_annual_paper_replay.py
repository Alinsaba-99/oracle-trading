#!/usr/bin/env -S uv run --frozen
"""M32a: Independent annual paper-replay windows on ES data.

Loads ES daily (20y) data, runs SMA(5/20) crossover with realistic
broker settings, and reports per-year metrics.

Each year is an independent window — no overlap between years.

Supports exit rules:
  --stop-loss-pct   Flatten when unrealized drawdown from entry exceeds N%
  --max-hold-bars   Flatten after N bars even without reversal signal
  --atr-stop-mult   Place stop at entry +- N x ATR(14)
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
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


def _signal(prices: list[float], fast: int, slow: int) -> str:
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
# ATR helper
# ---------------------------------------------------------------------------


def _compute_atr(closes: list[float], period: int = 14) -> list[float]:
    """Compute ATR(period) from close prices using the Wilder method."""
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


def _compute_adx(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> list[float]:
    """Compute ADX(period) using Wilder's method.

    Returns values 0-100. ADX > 25 = trending, ADX < 20 = ranging.
    """
    n = len(closes)
    if n < period + 2:
        return [0.0] * n
    plus_dm: list[float] = [0.0] * n
    minus_dm: list[float] = [0.0] * n
    tr: list[float] = [0.0] * n
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm[i] = max(up_move, 0.0) if up_move > down_move else 0.0
        minus_dm[i] = max(down_move, 0.0) if down_move > up_move else 0.0
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    # Wilder smoothing
    atr14 = _compute_atr(closes, period)
    plus_di: list[float] = [0.0] * n
    minus_di: list[float] = [0.0] * n
    dx: list[float] = [0.0] * n
    for i in range(period, n):
        pds = sum(plus_dm[i - period + 1 : i + 1])
        mds = sum(minus_dm[i - period + 1 : i + 1])
        atr_val = atr14[i]
        if atr_val > 0:
            plus_di[i] = 100.0 * pds / atr_val / period
            minus_di[i] = 100.0 * mds / atr_val / period
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx[i] = 100.0 * abs(plus_di[i] - minus_di[i]) / di_sum
    # ADX = smoothed DX
    adx: list[float] = [0.0] * n
    if n > period * 2:
        adx[period * 2 - 1] = sum(dx[period : period * 2]) / period
        for i in range(period * 2, n):
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
    return adx


# ---------------------------------------------------------------------------
# Session runner (single year)
# ---------------------------------------------------------------------------


async def _run_one_year(
    year: int,
    closes: list[float],
    highs: list[float] | None,
    lows: list[float] | None,
    timestamps: list[pd.Timestamp],
    fast: int,
    slow: int,
    capital: Decimal,
    point_value: Decimal,
    realistic: bool,
    stop_loss_pct: float = 0.0,
    max_hold_bars: int = 0,
    atr_stop_mult: float = 0.0,
    adx_threshold: float = 0.0,
) -> dict[str, Any]:
    from execution.brokers.config import BrokerConfig
    from execution.brokers.paper import PaperBroker
    from execution.brokers.types import BrokerOrder

    config = BrokerConfig(
        paper_spread_bps=15 if realistic else 0,
        paper_slippage_bps=8 if realistic else 0,
        paper_partial_fill_prob=0.2 if realistic else 0,
        paper_latency_ms=15 if realistic else 0,
        paper_commission_per_contract=0.85 if realistic else 0,
    )
    broker = PaperBroker(config)
    await broker.on_price_update(Decimal(str(closes[0])))

    # Precompute ATR if needed
    atr_vals = _compute_atr(closes) if atr_stop_mult > 0 else []
    # Precompute ADX if needed
    adx_vals: list[float] = []
    if adx_threshold > 0 and highs and lows:
        adx_vals = _compute_adx(highs, lows, closes)
    regime_agrees = True

    position = Decimal("0")
    peak = float(capital)
    max_drawdown = 0.0
    trades: list[dict[str, Any]] = []
    equity_curve: list[float] = [float(capital)]
    realized_pnl = Decimal("0")
    total_commission = Decimal("0")
    entry_price: Decimal | None = None
    entry_bar: int = -1
    stop_price: Decimal | None = None  # ATR stop level
    equity_at_entry: float | None = None  # equity when position opened
    peak_equity_since_entry: float | None = None

    for i in range(1, len(closes)):
        price = closes[i]
        sig = _signal(closes[: i + 1], fast, slow)
        ts = timestamps[i]
        price_decimal = Decimal(str(price))

        await broker.on_price_update(price_decimal)

        # ADX regime filter: check before evaluating signal
        if adx_threshold > 0 and i < len(adx_vals):
            regime_agrees = adx_vals[i] >= adx_threshold
        elif i >= 1 and i < len(adx_vals):
            regime_agrees = True

        # ── Check exit rules ──────────────────────────────────────────
        exit_reason: str | None = None

        if position != 0 and entry_price is not None:
            # Compute unrealized P&L and equity
            direction = Decimal("1") if position > 0 else Decimal("-1")
            unrealized = (price_decimal - entry_price) * direction * abs(position) * point_value
            equity = float(capital + realized_pnl + unrealized - total_commission)

            # Stop loss: N% drawdown from peak equity since entry
            if stop_loss_pct > 0 and equity_at_entry is not None:
                if peak_equity_since_entry is None or equity > peak_equity_since_entry:
                    peak_equity_since_entry = equity
                dd_pct = (peak_equity_since_entry - equity) / peak_equity_since_entry * 100
                if dd_pct > stop_loss_pct:
                    exit_reason = f"stop_loss_{stop_loss_pct}pct"

            # Time exit: max hold bars
            if max_hold_bars > 0 and entry_bar > 0 and i - entry_bar >= max_hold_bars:
                exit_reason = f"time_exit_{max_hold_bars}bars"

            # ATR stop
            if atr_stop_mult > 0 and i < len(atr_vals) and atr_vals[i] > 0:
                if stop_price is not None:
                    hit_stop = (position > 0 and float(price_decimal) <= float(stop_price)) or (
                        position < 0 and float(price_decimal) >= float(stop_price)
                    )
                    if hit_stop:
                        exit_reason = f"atr_stop_{atr_stop_mult}x"
                else:
                    # Set initial stop at entry +/- N x ATR
                    atr_val = Decimal(str(atr_vals[i]))
                    atr_distance = atr_val * abs(position) * Decimal(str(atr_stop_mult))
                    if position > 0:
                        stop_price = entry_price - atr_distance
                    else:
                        stop_price = entry_price + atr_distance

        # ── Flatten if exit triggered ─────────────────────────────────
        if exit_reason and position != 0:
            flat_side = "sell" if position > 0 else "buy"
            qty = abs(position)
            order = BrokerOrder(
                broker_order_id=f"{year}_{i}_exit",
                local_order_id="",
                namespaced_id=f"annual:{year}:{i}:{exit_reason}",
                instrument_id="ES",
                side=flat_side,
                quantity=qty,
                price=price_decimal,
                order_type="market",
                created_at=str(ts),
            )
            fills_before = len(broker._fills)
            await broker.submit_order(order)
            await broker.on_price_update(price_decimal)
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
                    "contracts": float(qty),
                    "position_after": 0.0,
                    "exit_reason": exit_reason,
                }
            )
            position = Decimal("0")
            entry_price = None
            stop_price = None
            equity_at_entry = None
            peak_equity_since_entry = None
            # Re-evaluate signal for fresh entry on the same bar
            sig = _signal(closes[: i + 1], fast, slow)

        # ── Signal-based entry/exit (skip if regime filter active) ─────
        target_pos = position
        if regime_agrees:
            if sig == "BUY" and position <= 0:
                target_pos = Decimal("1")
            elif sig == "SELL" and position >= 0:
                target_pos = Decimal("-1")

        if target_pos != position:
            side = "buy" if target_pos > 0 else "sell"
            contracts = abs(target_pos - position)
            position_before = position
            order = BrokerOrder(
                broker_order_id=f"{year}_{i}",
                local_order_id="",
                namespaced_id=f"annual:{year}:{i}",
                instrument_id="ES",
                side=side,
                quantity=contracts,
                price=price_decimal,
                order_type="market",
                created_at=str(ts),
            )
            fills_before = len(broker._fills)
            await broker.submit_order(order)
            await broker.on_price_update(price_decimal)
            new_fills = broker._fills[fills_before:]

            for fill in new_fills:
                new_pos = position + fill.quantity * (1 if side == "buy" else -1)
                going_against = (position * (1 if side == "buy" else -1)) < 0
                closed_qty = min(abs(position), fill.quantity) if going_against else Decimal("0")
                if closed_qty > 0 and entry_price is not None:
                    pos_dir = Decimal("1") if position > 0 else Decimal("-1")
                    fill_realized = (fill.price - entry_price) * pos_dir * closed_qty * point_value
                    realized_pnl += fill_realized
                else:
                    fill_realized = Decimal("0")
                position = new_pos
                total_commission += fill.commission
                if position == 0:
                    entry_price = None
                    stop_price = None
                    equity_at_entry = None
                    peak_equity_since_entry = None
                elif position_before == 0 or position_before * position < 0 or entry_price is None:
                    entry_price = fill.price
                    entry_bar = i
                    stop_price = None  # reset ATR stop on new entry
                    equity_at_entry = float(capital + realized_pnl - total_commission)
                    peak_equity_since_entry = equity_at_entry

            trade = {
                "bar": i,
                "time": str(ts),
                "price": price,
                "side": side,
                "contracts": float(contracts),
                "position_after": float(position),
            }
            if closed_qty > 0:
                trade["realized_pnl"] = round(float(realized_pnl), 2)
            trades.append(trade)

        # ── Mark-to-market equity ─────────────────────────────────────
        unrealized = Decimal("0")
        if position != 0 and entry_price is not None:
            direction = Decimal("1") if position > 0 else Decimal("-1")
            unrealized = (price_decimal - entry_price) * direction * abs(position) * point_value
        equity = float(capital + realized_pnl + unrealized - total_commission)
        equity_curve.append(round(equity, 2))
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    # Flatten end of year
    if position != 0:
        flat_side = "sell" if position > 0 else "buy"
        qty = abs(position)
        order = BrokerOrder(
            broker_order_id=f"{year}_flat",
            local_order_id="",
            namespaced_id=f"annual:{year}:flat",
            instrument_id="ES",
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

    final_equity = equity_curve[-1]
    total_pnl = final_equity - float(capital)
    max_dd = max_drawdown
    n_bars = len(closes)

    returns = [equity_curve[i] - equity_curve[i - 1] for i in range(1, len(equity_curve))]
    avg_ret = statistics.mean(returns) if returns else 0.0
    std_ret = statistics.stdev(returns) if len(returns) > 1 else 1.0
    annual_factor = math.sqrt(252 * 6.5) if n_bars > 1000 else math.sqrt(252)
    sharpe = (avg_ret / std_ret) * annual_factor if std_ret > 0 else 0.0

    downside = [r for r in returns if r < 0]
    downside_std = statistics.stdev(downside) if len(downside) > 1 else 1.0
    sortino = (avg_ret / downside_std) * annual_factor if downside_std > 0 else 0.0

    return_pct = total_pnl / float(capital) * 100

    hard_incidents: list[str] = []
    if max_dd > float(capital) * 0.05:
        hard_incidents.append(f"max_dd_exceeded: {max_dd:.2f} > 5%")
    if position != 0:
        hard_incidents.append(f"non_flat: {position}")

    return {
        "year": year,
        "n_bars": n_bars,
        "price_first": round(closes[0], 2),
        "price_last": round(closes[-1], 2),
        "n_trades": len(trades),
        "exits_by_stop": sum(1 for t in trades if "stop_loss" in t.get("exit_reason", "")),
        "exits_by_time": sum(1 for t in trades if "time_exit" in t.get("exit_reason", "")),
        "exits_by_atr": sum(1 for t in trades if "atr_stop" in t.get("exit_reason", "")),
        "total_pnl": round(total_pnl, 2),
        "return_pct": round(return_pct, 4),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "max_drawdown_pct": round(max_dd / float(capital) * 100, 4),
        "final_equity": round(final_equity, 2),
        "total_commission": round(float(total_commission), 4),
        "passed": len(hard_incidents) == 0,
        "hard_incidents": hard_incidents,
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_data(path: str) -> pd.DataFrame:
    """Load ES data, return with DatetimeIndex sorted."""
    if str(path).endswith(".parquet"):
        df = pd.read_parquet(path)
    elif str(path).endswith(".csv"):
        df = pd.read_csv(path, parse_dates=["Datetime"])
    else:
        msg = f"Unknown format: {path}"
        raise ValueError(msg)
    if "Datetime" in df.index.name or df.index.name == "Datetime":
        pass
    elif "timestamp" in df.columns:
        df = df.set_index("timestamp")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def _split_into_years(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Split into independent annual windows.

    A year runs from July 1 to June 30.
    Each year is completely independent — no overlapping bars.
    """
    df["year_label"] = df.index.to_series().apply(
        lambda ts: ts.year if ts.month >= 7 else ts.year - 1
    )
    years: list[dict[str, Any]] = []
    for y, group in df.groupby("year_label"):
        if len(group) < 200:
            continue
        years.append(
            {
                "year": int(y),
                "n_bars": len(group),
                "closes": group["Close"].tolist(),
                "highs": group["High"].tolist(),
                "lows": group["Low"].tolist(),
                "timestamps": group.index.tolist(),
            }
        )
    years.sort(key=lambda x: x["year"])
    return years


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------


def _evaluate(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results)
    passed = sum(r["passed"] for r in results)
    incidents = sum(len(r["hard_incidents"]) for r in results)
    pnls = [r["total_pnl"] for r in results]
    shs = [r["sharpe"] for r in results]
    dds = [r["max_drawdown_pct"] for r in results]

    return {
        "years": n,
        "passed": passed,
        "failed": n - passed,
        "hard_incidents": incidents,
        "net_pnl_total": round(sum(pnls), 2),
        "mean_pnl": round(statistics.mean(pnls), 2) if pnls else 0,
        "positive_years": sum(1 for p in pnls if p > 0),
        "mean_sharpe": round(statistics.mean(shs), 4) if shs else 0,
        "mean_drawdown_pct": round(statistics.mean(dds), 4) if dds else 0,
        "max_drawdown_pct": round(max(dds), 4) if dds else 0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Annual paper-replay windows on ES")
    parser.add_argument(
        "--data", type=str, default="data/ohlcv/ES_1d.parquet", help="Data file (Parquet or CSV)"
    )
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--seed", type=int, default=42006)
    parser.add_argument("--realistic", action="store_true", default=True)
    parser.add_argument("--output", type=str, default="logs/annual_paper_replay.json")
    # Exit rules
    parser.add_argument(
        "--stop-loss-pct",
        type=float,
        default=0.0,
        help="Stop loss: flatten when drawdown from entry exceeds N%%",
    )
    parser.add_argument(
        "--max-hold-bars", type=int, default=0, help="Time exit: flatten after N bars"
    )
    parser.add_argument(
        "--atr-stop-mult",
        type=float,
        default=0.0,
        help="ATR stop: place stop at entry +/- N x ATR(14)",
    )
    parser.add_argument(
        "--adx-threshold",
        type=float,
        default=0.0,
        help="ADX filter: only trade when ADX >= threshold (20=weak, 25=trending)",
    )
    args = parser.parse_args()

    df = _load_data(args.data)
    years = _split_into_years(df)

    total_bars = len(df)

    print(f"\n{'=' * 60}")
    print("Independent Annual Paper Replay")
    print(f"  Data: {total_bars} barre from {df.index[0].date()} to {df.index[-1].date()}")
    print(f"  Anni indipendenti: {len(years)}")
    print(f"  Strategia: SMA({args.fast}/{args.slow})")
    print(f"  Capitale: ${args.capital:,.0f}")
    print(f"  Broker realistico: {args.realistic}")
    if args.stop_loss_pct > 0:
        print(f"  Stop loss: {args.stop_loss_pct}% drawdown da entry")
    if args.max_hold_bars > 0:
        print(f"  Time exit: {args.max_hold_bars} barre")
    if args.atr_stop_mult > 0:
        print(f"  ATR stop: {args.atr_stop_mult}x ATR(14)")
    if args.adx_threshold > 0:
        print(f"  ADX filter: only trade when ADX >= {args.adx_threshold}")
    print(f"{'=' * 60}\n")

    point_value = Decimal("50")
    capital_dec = Decimal(str(args.capital))
    all_results: list[dict[str, Any]] = []
    random.seed(args.seed)

    for yr in years:
        start = _time.monotonic()
        result = await _run_one_year(
            year=yr["year"],
            closes=yr["closes"],
            highs=yr.get("highs"),
            lows=yr.get("lows"),
            timestamps=yr["timestamps"],
            fast=args.fast,
            slow=args.slow,
            capital=capital_dec,
            point_value=point_value,
            realistic=args.realistic,
            stop_loss_pct=args.stop_loss_pct,
            max_hold_bars=args.max_hold_bars,
            atr_stop_mult=args.atr_stop_mult,
            adx_threshold=args.adx_threshold,
        )
        elapsed = _time.monotonic() - start
        result["elapsed_seconds"] = round(elapsed, 2)
        all_results.append(result)

        status = "✅" if result["passed"] else "❌"
        extra = f"  ⚠️  {'; '.join(result['hard_incidents'])}" if not result["passed"] else ""
        print(
            f"  [{yr['year']}] {status}  "
            f"P&L=${result['total_pnl']:>+9.2f}  "
            f"R={result['return_pct']:>+6.2f}%  "
            f"S={result['sharpe']:>6.2f}  "
            f"DD={result['max_drawdown_pct']:>5.2f}%  "
            f"T={result['n_trades']:>2d}  "
            f"B={yr['n_bars']:>4d}  "
            f"{elapsed:.1f}s{extra}",
            flush=True,
        )

    gate = _evaluate(all_results)
    total_stops = sum(r.get("exits_by_stop", 0) for r in all_results)
    total_times = sum(r.get("exits_by_time", 0) for r in all_results)
    total_atrs = sum(r.get("exits_by_atr", 0) for r in all_results)

    print(f"\n{'=' * 60}")
    print(f"SUMMARY — {len(years)} Independent Annual Windows")
    print(f"{'=' * 60}")
    print(f"  Anni totali:      {gate['years']}")
    print(f"  Passati:          {gate['passed']}")
    print(f"  Falliti:          {gate['failed']}")
    print(f"  P&L netto totale: ${gate['net_pnl_total']:>+9.2f}")
    print(f"  P&L medio/anno:   ${gate['mean_pnl']:>+9.2f}")
    print(f"  Anni positivi:    {gate['positive_years']}/{gate['years']}")
    print(f"  Sharpe medio:     {gate['mean_sharpe']:>7.4f}")
    print(f"  Drawdown medio:   {gate['mean_drawdown_pct']:>5.2f}%")
    print(f"  Drawdown max:     {gate['max_drawdown_pct']:>5.2f}%")
    print(f"  Hard incidents:   {gate['hard_incidents']}")
    if total_stops > 0:
        print(f"  Exits by stop loss: {total_stops}")
    if total_times > 0:
        print(f"  Exits by time:       {total_times}")
    if total_atrs > 0:
        print(f"  Exits by ATR stop:   {total_atrs}")
    print(f"\n  Gate: {'✅ PASS' if gate['failed'] == 0 else '❌ FAIL'}")
    print(f"{'=' * 60}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "metadata": {
                    "type": "annual_paper_replay",
                    "data_source": args.data,
                    "data_sha256": hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
                    "fast": args.fast,
                    "slow": args.slow,
                    "capital": args.capital,
                    "realistic": args.realistic,
                    "seed": args.seed,
                    "stop_loss_pct": args.stop_loss_pct,
                    "max_hold_bars": args.max_hold_bars,
                    "atr_stop_mult": args.atr_stop_mult,
                    "independent_years": True,
                    "point_value": 50.0,
                    "timestamp": datetime.now().isoformat(),
                },
                "results": all_results,
                "gate": gate,
            },
            f,
            indent=2,
        )
    print(f"\nRisultati salvati in {output_path}")

    if gate["failed"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
