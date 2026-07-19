#!/usr/bin/env python3
"""Complete live simulation: real data → strategy → paper execution → P&L.

Tests the full Oracle pipeline with real market data:
1. Fetch ES futures daily data via yfinance
2. Run SMA crossover strategy (20/50)
3. Execute paper trades through realistic fill engine
4. Track P&L through the ledger
5. Report detailed results

Usage::

    uv run --frozen python scripts/run_simulation.py
    uv run --frozen python scripts/run_simulation.py --symbol NQ --fast 10 --slow 30
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Ensure we can import Oracle modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_simulation(
    symbol: str = "ES",
    fast_ma: int = 20,
    slow_ma: int = 50,
    period: str = "1y",
    interval: str = "1d",
    initial_capital: Decimal = Decimal("100000"),
    commission_per_contract: Decimal = Decimal("2.50"),
    verbose: bool = True,
) -> dict:
    """Run a complete trading simulation.

    Args:
        symbol: Futures symbol (ES, NQ, GC, CL).
        fast_ma: Fast moving average period.
        slow_ma: Slow moving average period.
        period: yfinance data period.
        interval: yfinance data interval.
        initial_capital: Starting account balance.
        commission_per_contract: Commission per contract.
        verbose: Print detailed output.

    Returns:
        Dict with simulation results.
    """
    import pandas as pd
    import yfinance as yf
    from market.contracts import get_contract
    from core.ledger import InMemoryLedger
    from execution.brokers.paper_engine import RealisticPaperFillEngine

    # 1. Fetch real data
    ticker = f"{symbol}=F"
    if verbose:
        print(f"\n{'='*60}")
        print(f"📊 ORACLE TRADING SIMULATION")
        print(f"{'='*60}")
        print(f"Symbol:    {symbol} ({ticker})")
        print(f"Strategy:  SMA({fast_ma}/{slow_ma}) crossover")
        print(f"Period:    {period} ({interval})")
        print(f"Capital:   ${initial_capital:,.2f}")
        print(f"{'='*60}\n")

    print(f"🔄 Downloading {ticker} data...")
    df = yf.download(ticker, period=period, interval=interval)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    print(f"   ✅ {len(df)} bars from {df.index[0].date()} to {df.index[-1].date()}")

    # 2. Get contract spec
    spec = get_contract(symbol)
    if verbose:
        print(f"   Contract: {symbol} (multiplier={spec.multiplier}, tick=${spec.tick_value})")

    # 3. Setup paper engine + ledger
    engine = RealisticPaperFillEngine(seed=42)
    ledger = InMemoryLedger()
    acct = ledger.create_account(
        account_type="paper",
        initial_balance=initial_capital,
    )

    # 4. Run strategy
    close = df["Close"]
    sma_fast = close.rolling(fast_ma).mean()
    sma_slow = close.rolling(slow_ma).mean()

    position = 0  # 0 flat, 1 long, -1 short
    entry_price = Decimal("0")
    trades: list[dict] = []
    equity_curve: list[dict] = []

    for i in range(slow_ma, len(close)):
        date_val = df.index[i]
        price_val = float(close.iloc[i])
        price_dec = Decimal(str(round(price_val, 2)))

        # Generate signal
        prev_fast = sma_fast.iloc[i - 1]
        prev_slow = sma_slow.iloc[i - 1]
        cur_fast = sma_fast.iloc[i]
        cur_slow = sma_slow.iloc[i]

        signal = 0
        if prev_fast <= prev_slow and cur_fast > cur_slow:
            signal = 1  # Buy
        elif prev_fast >= prev_slow and cur_fast < cur_slow:
            signal = -1  # Sell

        # Execute trade
        if signal != 0 and signal != position:
            # Close existing position
            if position != 0:
                result = engine.simulate_fill(
                    symbol, price_val, abs(position), "market",
                    side="sell" if position > 0 else "buy",
                )
                if result.filled:
                    pnl = (price_dec - entry_price) * spec.point_value * Decimal(str(position))
                    net_pnl = pnl - result.commission
                    ledger.record_fill(
                        account_id=acct.account_id,
                        order_id=f"close-{date_val.date()}",
                        fill_id=f"fill-close-{i}",
                        quantity=result.fill_quantity,
                        price=result.fill_price,
                        commission=result.commission,
                        realized_pnl=net_pnl,
                    )
                    trades.append({
                        "date": date_val,
                        "action": "close",
                        "side": "short" if position > 0 else "cover",
                        "qty": abs(position),
                        "price": float(result.fill_price),
                        "pnl": float(net_pnl),
                        "commission": float(result.commission),
                    })

            # Open new position
            qty = 2  # Fixed 2 contracts for simplicity
            result = engine.simulate_fill(
                symbol, price_val, qty, "market",
                side="buy" if signal > 0 else "sell",
            )
            if result.filled:
                position = signal * qty
                entry_price = result.fill_price
                trades.append({
                    "date": date_val,
                    "action": "open",
                    "side": "long" if signal > 0 else "short",
                    "qty": qty,
                    "price": float(result.fill_price),
                    "pnl": 0,
                    "commission": float(result.commission),
                })

        # Record equity
        open_pnl = 0
        if position != 0:
            open_pnl = float((price_dec - entry_price) * spec.point_value * Decimal(str(position)))
        equity_curve.append({
            "date": date_val,
            "balance": float(ledger.get_balance(acct.account_id)),
            "open_pnl": open_pnl,
            "equity": float(ledger.get_balance(acct.account_id)) + open_pnl,
            "position": position,
            "price": price_val,
        })

    # Close any remaining position
    if position != 0:
        price_val = float(close.iloc[-1])
        price_dec = Decimal(str(round(price_val, 2)))
        result = engine.simulate_fill(
            symbol, price_val, abs(position), "market",
            side="sell" if position > 0 else "buy",
        )
        if result.filled:
            pnl = (price_dec - entry_price) * spec.point_value * Decimal(str(position))
            net_pnl = pnl - result.commission
            ledger.record_fill(
                account_id=acct.account_id,
                order_id="close-final",
                fill_id="fill-final",
                quantity=result.fill_quantity,
                price=result.fill_price,
                commission=result.commission,
                realized_pnl=net_pnl,
            )
            trades.append({
                "date": df.index[-1],
                "action": "close",
                "side": "short" if position > 0 else "cover",
                "qty": abs(position),
                "price": float(result.fill_price),
                "pnl": float(net_pnl),
                "commission": float(result.commission),
            })
            position = 0

    # 5. Compute results
    final_balance = float(ledger.get_balance(acct.account_id))
    total_pnl = final_balance - float(initial_capital)
    total_return_pct = (total_pnl / float(initial_capital)) * 100

    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
    losing_trades = [t for t in trades if t.get("pnl", 0) < 0]
    closed_trades = [t for t in trades if t["action"] == "close"]
    total_closed_pnl = sum(t["pnl"] for t in closed_trades)
    total_commission = sum(t["commission"] for t in trades)

    # Compute Sharpe (simplified, using daily returns)
    if len(equity_curve) > 1:
        eq_df = pd.DataFrame(equity_curve).set_index("date")
        returns = eq_df["equity"].pct_change().dropna()
        sharpe = float(returns.mean() / returns.std() * (252 ** 0.5)) if returns.std() > 0 else 0
        max_dd = _max_drawdown(eq_df["equity"].values)
    else:
        sharpe = 0
        max_dd = 0

    # 6. Print results
    print(f"\n{'='*60}")
    print(f"📈 RESULTS")
    print(f"{'='*60}")
    print(f"Initial capital:  ${float(initial_capital):,.2f}")
    print(f"Final balance:    ${final_balance:,.2f}")
    print(f"Total P&L:        ${total_pnl:,.2f} ({total_return_pct:+.2f}%)")
    print(f"Total trades:     {len(closed_trades)}")
    print(f"Winners:          {len(winning_trades)}")
    print(f"Losers:           {len(losing_trades)}")
    win_rate = len(winning_trades) / max(len(closed_trades), 1) * 100
    print(f"Win rate:         {win_rate:.1f}%")
    print(f"Total comm.:      ${total_commission:,.2f}")
    print(f"Sharpe (daily):   {sharpe:.2f}")
    print(f"Max drawdown:     {max_dd:.1f}%")
    print(f"Contract:         {symbol} (${spec.tick_value}/tick)")
    print(f"{'='*60}\n")

    return {
        "symbol": symbol,
        "initial_capital": float(initial_capital),
        "final_balance": final_balance,
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "total_trades": len(closed_trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate_pct": win_rate,
        "total_commission": total_commission,
        "sharpe": sharpe,
        "max_drawdown_pct": max_dd,
        "num_bars": len(df),
        "start_date": str(df.index[0].date()),
        "end_date": str(df.index[-1].date()),
    }


def _max_drawdown(values: list[float]) -> float:
    """Compute maximum drawdown percentage from an equity curve."""
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Oracle trading simulation")
    parser.add_argument("--symbol", default="ES", help="Futures symbol (ES, NQ, GC, CL)")
    parser.add_argument("--fast", type=int, default=20, help="Fast MA period")
    parser.add_argument("--slow", type=int, default=50, help="Slow MA period")
    parser.add_argument("--period", default="1y", help="Data period")
    parser.add_argument("--capital", type=float, default=100000, help="Initial capital")
    args = parser.parse_args()

    result = run_simulation(
        symbol=args.symbol.upper(),
        fast_ma=args.fast,
        slow_ma=args.slow,
        period=args.period,
        initial_capital=Decimal(str(args.capital)),
    )
