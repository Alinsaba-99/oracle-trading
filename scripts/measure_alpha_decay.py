#!/usr/bin/env -S uv run --frozen
"""M32-022: Alpha decay measurement.

Runs a strategy walk-forward across sequential time windows and measures
how performance degrades over time. A strategy with high alpha decay loses
predictive power quickly; one with low decay maintains consistent returns.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


def _signal(prices: list[float], fast: int, slow: int) -> str:
    """SMA crossover signal: BUY, SELL, or HOLD."""
    if len(prices) < slow + 1:
        return "HOLD"
    f = sum(prices[-fast:]) / fast
    s = sum(prices[-slow:]) / slow
    if len(prices) < slow + 2:
        return "HOLD"
    pf = sum(prices[-(fast + 1) : -1]) / fast
    ps = sum(prices[-(slow + 1) : -1]) / slow
    if pf <= ps and f > s:
        return "BUY"
    if pf >= ps and f < s:
        return "SELL"
    return "HOLD"


# ---------------------------------------------------------------------------
# Walk-forward backtest
# ---------------------------------------------------------------------------


def _run_window(prices: list[float], fast: int, slow: int) -> dict[str, Any]:
    """Run a simple backtest on a price window and return performance metrics.

    Uses 1-contract positions with SMA crossover signals.
    """
    position = 0
    entry_price = 0.0
    trades: list[dict[str, Any]] = []
    equity: list[float] = [0.0]  # running P&L

    for i in range(1, len(prices)):
        sig = _signal(prices[: i + 1], fast, slow)

        # Exit logic
        if position != 0 and ((position > 0 and sig != "BUY") or (position < 0 and sig != "SELL")):
            exit_price = prices[i]
            pnl = (exit_price - entry_price) * position
            trades.append(
                {
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "position": position,
                    "pnl": pnl,
                    "bars_held": i,
                }
            )
            position = 0
            equity.append(equity[-1] + pnl)

        # Entry logic
        if position == 0 and sig == "BUY":
            position = 1
            entry_price = prices[i]
        elif position == 0 and sig == "SELL":
            position = -1
            entry_price = prices[i]

        if position == 0:
            equity.append(equity[-1])

    # Close any open position at the last price
    if position != 0:
        exit_price = prices[-1]
        pnl = (exit_price - entry_price) * position
        trades.append(
            {
                "entry_price": entry_price,
                "exit_price": exit_price,
                "position": position,
                "pnl": pnl,
                "bars_held": len(prices),
            }
        )
        equity.append(equity[-1] + pnl)

    return _compute_metrics(trades, equity)


def _compute_metrics(trades: list[dict[str, Any]], equity: list[float]) -> dict[str, Any]:
    """Compute performance metrics from a list of trades and equity curve."""
    n_trades = len(trades)
    if n_trades == 0:
        return {
            "n_trades": 0,
            "total_return": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
        }

    total_return = equity[-1] if equity else 0.0
    winners = [t for t in trades if t["pnl"] > 0]
    losers = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(winners) / n_trades if n_trades > 0 else 0.0
    avg_win = statistics.mean([t["pnl"] for t in winners]) if winners else 0.0
    avg_loss = statistics.mean([t["pnl"] for t in losers]) if losers else 0.0

    # Equity curve metrics
    peak = equity[0]
    max_dd = 0.0
    returns: list[float] = []
    for i in range(1, len(equity)):
        returns.append(equity[i] - equity[i - 1])
        peak = max(peak, equity[i])
        dd = peak - equity[i]
        max_dd = max(max_dd, dd)

    avg_return = statistics.mean(returns) if returns else 0.0
    std_return = statistics.stdev(returns) if len(returns) > 1 else 1.0
    sharpe = (avg_return / std_return) * math.sqrt(252) if std_return > 0 else 0.0

    gross_profit = sum(t["pnl"] for t in winners)
    gross_loss = abs(sum(t["pnl"] for t in losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    return {
        "n_trades": n_trades,
        "total_return": round(total_return, 2),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 2),
        "profit_factor": round(profit_factor, 4),
    }


# ---------------------------------------------------------------------------
# Walk-forward analysis
# ---------------------------------------------------------------------------


def _walk_forward(
    prices: list[float], fast: int, slow: int, window_size: int, step: int
) -> list[dict[str, Any]]:
    """Run walk-forward analysis, returning per-window metrics."""
    windows: list[dict[str, Any]] = []
    for start in range(0, len(prices) - window_size + 1, step):
        end = start + window_size
        window_prices = prices[start:end]
        metrics = _run_window(window_prices, fast, slow)
        metrics["window_start"] = start
        metrics["window_end"] = end
        windows.append(metrics)
    return windows


# ---------------------------------------------------------------------------
# Alpha decay metrics
# ---------------------------------------------------------------------------


def _compute_alpha_decay(windows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute alpha decay metrics from walk-forward windows."""
    if len(windows) < 2:
        return {"decay_detected": False, "note": "need at least 2 windows"}

    sharpe_series = [w["sharpe"] for w in windows]
    return_series = [w["total_return"] for w in windows]
    win_rate_series = [w["win_rate"] for w in windows]
    n_windows = len(windows)

    # Linear regression slope for Sharpe over windows
    x = list(range(n_windows))
    n = n_windows

    def _slope(y: list[float]) -> float:
        """Simple linear slope (least squares)."""
        if n < 2 or all(v == y[0] for v in y):
            return 0.0
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        num = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        den = sum((x[i] - x_mean) ** 2 for i in range(n))
        return num / den if den != 0 else 0.0

    sharpe_slope = _slope(sharpe_series)
    return_slope = _slope(return_series)
    win_rate_slope = _slope(win_rate_series)

    # Sharpe decay: how many windows until Sharpe < 0
    half_life: int | None = None
    sh = sharpe_series[0]
    for i in range(1, n_windows):
        if sharpe_slope < 0 and sh > 0:
            sh += sharpe_slope
            if sh <= 0:
                half_life = i
                break

    # Consistency: fraction of windows with positive Sharpe
    positive_sharpe = sum(1 for s in sharpe_series if s > 0)

    return {
        "n_windows": n_windows,
        "sharpe_slope": round(sharpe_slope, 6),
        "return_slope": round(return_slope, 6),
        "win_rate_slope": round(win_rate_slope, 6),
        "sharpe_first": round(sharpe_series[0], 4),
        "sharpe_last": round(sharpe_series[-1], 4),
        "sharpe_min": round(min(sharpe_series), 4),
        "sharpe_max": round(max(sharpe_series), 4),
        "sharpe_volatility": round(statistics.stdev(sharpe_series), 4),
        "half_life_windows": half_life,
        "consistency": round(positive_sharpe / n_windows, 4),
        "decay_detected": sharpe_slope < -0.001,
        "decay_severity": (
            "high"
            if sharpe_slope < -0.1
            else "moderate"
            if sharpe_slope < -0.05
            else "low"
            if sharpe_slope < -0.001
            else "none"
        ),
    }


# ---------------------------------------------------------------------------
# Price generators
# ---------------------------------------------------------------------------


def _regime_series(n: int) -> list[float]:
    """Generate a price series with three regimes: trend, mean-reverting,
    then volatile, to simulate alpha decay."""
    import random as _random

    rng = _random.Random(42)
    prices: list[float] = []
    p = 5000.0

    for i in range(n):
        if i < n // 3:
            # Strong uptrend (easy alpha)
            p *= 1 + rng.gauss(0.001, 0.003)
        elif i < 2 * n // 3:
            # Mean reversion / choppy (harder alpha)
            p += rng.uniform(-5, 5)
        else:
            # High volatility (decaying alpha)
            p *= 1 + rng.gauss(0.0, 0.008)
        prices.append(round(max(p, 1.0), 2))

    return prices


def _sawtooth(n: int, start: float = 4500.0) -> list[float]:
    """Sawtooth pattern with varying amplitude to test alpha decay."""
    prices: list[float] = []
    for i in range(n):
        cycle = (i % 30) / 30.0
        amp = 0.03 * (1 - i / (2 * n))  # amplitude decays
        if (i // 30) % 2 == 0:
            prices.append(round(start * (1 + cycle * amp), 2))
        else:
            prices.append(round(start * (1 + (1 - cycle) * amp), 2))
    return prices


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _print_window_table(windows: list[dict[str, Any]]) -> None:
    """Print a compact per-window results table."""
    print(
        f"  {'Win':>4s} {'Trades':>6s} {'Return':>8s} {'WinRate':>7s} "
        f"{'Sharpe':>7s} {'MaxDD':>8s} {'ProfFact':>8s}"
    )
    for i, w in enumerate(windows):
        print(
            f"  {i:>4d} {w['n_trades']:>6d} {w['total_return']:>8.1f} "
            f"{w['win_rate']:>7.2%} {w['sharpe']:>7.2f} {w['max_drawdown']:>8.1f} "
            f"{w['profit_factor']:>8.2f}"
        )


def _print_decay_report(decay: dict[str, Any]) -> None:
    """Print formatted alpha decay report."""
    print(f"\n  Windows:                {decay['n_windows']}")
    print(
        f"  Sharpe slope:           {decay['sharpe_slope']:.4f} "
        f"(first={decay['sharpe_first']:.2f}, last={decay['sharpe_last']:.2f})"
    )
    print(f"  Return slope:           {decay['return_slope']:.4f}")
    print(f"  Win-rate slope:         {decay['win_rate_slope']:.4f}")
    print(f"  Sharpe range:           [{decay['sharpe_min']:.2f}, {decay['sharpe_max']:.2f}]")
    print(f"  Sharpe volatility:      {decay['sharpe_volatility']:.4f}")
    print(f"  Consistency:            {decay['consistency']:.2%}")
    if decay["half_life_windows"] is not None:
        print(f"  Sharpe half-life:       {decay['half_life_windows']} windows")
    else:
        print(f"  Sharpe half-life:       > {decay['n_windows']} windows (no decay detected)")
    print(f"  Decay detected:         {decay['decay_detected']}")
    print(f"  Decay severity:         {decay['decay_severity']}")


def _check_thresholds(decay: dict[str, Any], label: str) -> bool:
    """Check alpha decay against paper-gate thresholds."""
    ok = True
    print(f"\n  Thresholds ({label}):")

    if decay["decay_detected"] and decay["decay_severity"] in ("high", "moderate"):
        print(f"    FAIL decay_severity = {decay['decay_severity']}")
        ok = False
    else:
        print(f"    PASS decay_severity = {decay['decay_severity']}")

    if decay["sharpe_slope"] < -0.05:
        print(f"    FAIL sharpe_slope = {decay['sharpe_slope']:.4f} (< -0.05)")
        ok = False
    else:
        print(f"    PASS sharpe_slope = {decay['sharpe_slope']:.4f}")

    if decay["consistency"] < 0.5:
        print(f"    FAIL consistency = {decay['consistency']:.2%} (< 50%)")
        ok = False
    else:
        print(f"    PASS consistency = {decay['consistency']:.2%}")

    print(f"  Overall: {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Measure alpha decay")
    parser.add_argument("--fast", type=int, default=10)
    parser.add_argument("--slow", type=int, default=30)
    parser.add_argument("--bars", type=int, default=900)
    parser.add_argument("--window", type=int, default=200)
    parser.add_argument("--step", type=int, default=50)
    parser.add_argument("--pattern", choices=["regime", "sawtooth"], default="regime")
    args = parser.parse_args()

    print(f"Alpha Decay - SMA({args.fast}/{args.slow})")
    print(f"Pattern: {args.pattern}, Bars: {args.bars}, Window: {args.window}, Step: {args.step}")

    # Generate price data
    prices = _sawtooth(args.bars) if args.pattern == "sawtooth" else _regime_series(args.bars)
    print(f"  Prices: {len(prices)} bars  [{min(prices):.2f} - {max(prices):.2f}]")

    # Full-run reference
    ref = _run_window(prices, args.fast, args.slow)
    print("\n  Full-run reference:")
    print(
        f"    Trades: {ref['n_trades']}, Return: {ref['total_return']:.1f}, "
        f"Sharpe: {ref['sharpe']:.2f}"
    )

    # Walk-forward analysis
    windows = _walk_forward(prices, args.fast, args.slow, args.window, args.step)
    print(f"\n  Walk-forward windows: {len(windows)}")
    _print_window_table(windows)

    # Alpha decay
    decay = _compute_alpha_decay(windows)
    print("\n--- Alpha Decay Report ---")
    _print_decay_report(decay)

    # Thresholds
    _check_thresholds(decay, args.pattern)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
