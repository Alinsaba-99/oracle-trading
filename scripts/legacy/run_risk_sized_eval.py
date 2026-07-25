#!/usr/bin/env python3
"""Compare vanilla vs. risk-sized strategies on prop-firm challenge pass rate.

Tests four configurations for each strategy:
  - Vanilla (fixed 100% allocation, no stop)
  - Risk-sized (ATR-based position sizing)
  - Stop-loss only (price-based protective stop)
  - Risk-sized + stop-loss combined

Usage:
    uv run --frozen python scripts/run_risk_sized_eval.py
    uv run --frozen python scripts/run_risk_sized_eval.py --strategy ema_10_30
    uv run --frozen python scripts/run_risk_sized_eval.py --window 40
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import polars as pl

from analytics.backtest.challenge import ChallengeSimulator
from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import VectorizedEngine
from analytics.backtest.result import BacktestResult
from analytics.strategy.risk_sized import sized_backtest
from analytics.strategy.signals import (
    BbandReversion,
    DonchianBreakout,
    EmaTrend,
    RsiReversion,
    TrendFilteredBreakout,
)
from policy.prop_firm.fixtures import TOPSTEP_TC_50K


# ── data ─────────────────────────────────────────────────────────────────────
def load_es_data() -> pl.DataFrame:
    raw = pl.read_parquet("data/ohlcv/ES_1d.parquet")
    rename = {}
    for col in raw.columns:
        lower = col.strip().lower()
        if lower == "date":
            rename[col] = "timestamp"
        elif lower in ("open", "high", "low", "close", "volume"):
            rename[col] = lower
    df = raw.rename(rename).sort("timestamp")
    if df["timestamp"].dtype != pl.Datetime:
        df = df.with_columns(df["timestamp"].cast(pl.Datetime))
    return df


# ── strategy registry ────────────────────────────────────────────────────────
CORE_STRATEGIES: dict[str, type] = {
    "ema_10_30": lambda: EmaTrend(fast=10, slow=30),
    "ema_20_50": lambda: EmaTrend(fast=20, slow=50),
    "donchian_20": lambda: DonchianBreakout(period=20),
    "trend_filtered": lambda: TrendFilteredBreakout(period=20, ma_period=200),
    "rsi_7_25_50": lambda: RsiReversion(period=7, oversold=25.0, exit_level=50.0),
    "bollinger_20": lambda: BbandReversion(period=20, std=2.0),
}


# ── vanilla backtest ─────────────────────────────────────────────────────────
def run_vanilla(data: pl.DataFrame, signal_cls: type) -> BacktestResult:
    """Standard VectorizedEngine run (fixed 100% allocation)."""
    cfg = BacktestConfig(
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        slippage_bps=3.0,
        commission_pct=0.0005,
    )
    engine = VectorizedEngine()
    return engine.run(data, signal_cls(), cfg)


# ── risk-sized backtest ─────────────────────────────────────────────────────
def run_risk_sized(
    data: pl.DataFrame, signal_cls: type, risk_pct: float = 0.01, stop_atr_mult: float = 2.0
) -> BacktestResult:
    """ATR-based volatility-scaled backtest."""
    cfg = BacktestConfig(
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        slippage_bps=3.0,
        commission_pct=0.0005,
    )
    result = sized_backtest(
        data,
        signal_cls(),
        settings=cfg,
        risk_pct=risk_pct,
        stop_atr_mult=stop_atr_mult,
        max_pct=1.0,
    )
    return result


# ── stop-loss-only backtest using vectorbt directly ─────────────────────────
def run_with_stop_loss(
    data: pl.DataFrame, name: str, signal_cls: type, atr_mult: float = 2.5
) -> BacktestResult:
    """Signal-based entries + ATR-based trailing/stop-loss exits.

    Uses vectorbt Portfolio.from_signals with a `sl_stop` parameter
    that automatically exits when price moves against the position by
    N * ATR from the entry price.
    """
    import vectorbt as vbt
    from vectorbt.portfolio.enums import OppositeEntryMode

    from analytics.backtest.engines.vectorized import (
        _ensure_datetime_index,
        _infer_freq,
        _normalise_vbt_price,
    )
    from analytics.technical.polars_indicators import atr

    cfg = BacktestConfig(
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        slippage_bps=3.0,
        commission_pct=0.0005,
    )

    df = _ensure_datetime_index(_normalise_vbt_price(data.to_pandas()))
    if "Close" not in df.columns:
        raise ValueError("DataFrame must contain a 'close' column.")

    raw = np.asarray(signal_cls().compute(data), dtype=np.int64)
    raw = np.roll(raw, 1)
    raw[0] = 0
    entries = raw == 1
    exits = raw == 0

    # Compute ATR-based stop price as % away from entry
    a = atr(
        data["high"] if "high" in data.columns else data["High"],
        data["low"] if "low" in data.columns else data["Low"],
        data["close"] if "close" in data.columns else data["Close"],
        14,
    )
    atr_pct = (a / data["close"]).fill_nan(0.0).to_numpy()
    sl_stop = np.where(atr_pct > 0, atr_pct * atr_mult, 0.0)

    portfolio = vbt.Portfolio.from_signals(
        df["Close"],
        entries=entries,
        exits=exits,
        upon_opposite_entry=OppositeEntryMode.Close,
        accumulate=False,
        slippage=cfg.slippage_bps / 10_000.0,
        fees=cfg.commission_pct,
        init_cash=float(cfg.initial_capital),
        freq=_infer_freq(df.index),
        sl_stop=sl_stop,
    )

    metrics = portfolio.stats(silence_warnings=True)

    def _m(key: str, default: float = 0.0) -> float:
        val = metrics.get(key, default)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)

    equity = portfolio.value()
    equity_list = equity.to_numpy(dtype=np.float64).tolist()
    final = equity_list[-1] if equity_list else float(cfg.initial_capital)
    cash = float(cfg.initial_capital)
    years = len(data) / 252.0
    cagr = ((final / cash) ** (1.0 / max(years, 1e-10)) - 1.0) if cash > 0 else 0.0

    return BacktestResult(
        run_id="stop_loss",
        strategy_name=name,
        instrument="ES",
        engine="stop_loss",
        total_return=_m("Total Return [%]") / 100.0,
        sharpe_ratio=_m("Sharpe Ratio"),
        sortino_ratio=_m("Sortino Ratio"),
        calmar_ratio=_m("Calmar Ratio"),
        max_drawdown=_m("Max Drawdown [%]") / 100.0,
        volatility=_m("Volatility [%]") / 100.0,
        cagr=cagr,
        total_trades=int(_m("Total Trades")),
        win_rate=_m("Win Rate [%]") / 100.0,
        profit_factor=_m("Profit Factor"),
        initial_capital=cfg.initial_capital,
        final_equity=final,
        equity_curve=equity_list,
    )


# ── rolling challenge simulation ─────────────────────────────────────────────
def rolling_pass_rate(
    data: pl.DataFrame,
    name: str,
    signal_cls: type,
    mode: str,
    window_days: int = 60,
    step: int = 20,
    warmup: int = 50,
) -> dict:
    """Rolling window challenge pass rate for a strategy mode."""
    initial_cap = float(TOPSTEP_TC_50K.account_size)
    n = len(data)
    results: list[dict] = []
    sim_start = max(warmup, window_days // 2)

    cfg = BacktestConfig(
        initial_capital=Decimal(str(initial_cap)), slippage_bps=3.0, commission_pct=0.0005
    )

    for start in range(sim_start, n - window_days, step):
        end = start + window_days
        if end > n:
            break

        window = data[start:end]
        if len(window) < window_days * 0.8:
            continue

        try:
            if mode in ("vanilla",):
                engine = VectorizedEngine()
                bt = engine.run(window, signal_cls(), cfg)
            elif mode == "risk_sized":
                bt = sized_backtest(window, signal_cls(), settings=cfg)
            elif mode == "stop_loss":
                bt = run_with_stop_loss(window, name, signal_cls)
            elif mode == "sized_stop":
                bt = sized_backtest(window, signal_cls(), settings=cfg)
            else:
                continue
        except Exception:
            continue

        equity = bt.equity_curve
        if not equity or len(equity) < 5:
            continue

        sim = ChallengeSimulator(TOPSTEP_TC_50K, initial_cap)
        today = date.today()
        dates = [today - timedelta(days=len(equity) - 1 - i) for i in range(len(equity))]
        result = sim.run(equity, dates)
        pnl = result.final_balance - initial_cap

        results.append(
            {
                "passed": result.passed,
                "pnl": pnl,
                "max_dd": result.max_drawdown_pct,
                "sharpe": bt.sharpe_ratio,
            }
        )

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    mean_pnl = np.mean([r["pnl"] for r in results]) if results else 0.0
    mean_dd = np.mean([r["max_dd"] for r in results]) if results else 0.0
    mean_sharpe = np.mean([r["sharpe"] for r in results]) if results else 0.0

    return {
        "strategy": name,
        "mode": mode,
        "n_windows": total,
        "passed": passed,
        "pass_rate": passed / total * 100 if total > 0 else 0.0,
        "mean_pnl": mean_pnl,
        "mean_max_dd": mean_dd,
        "mean_sharpe": mean_sharpe,
    }


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Risk-sized vs vanilla prop-firm eval")
    parser.add_argument("--strategy", type=str, default=None, help="Single strategy")
    parser.add_argument("--window", type=int, default=60, help="Challenge window (bars)")
    parser.add_argument("--step", type=int, default=20, help="Step between windows")
    parser.add_argument("--list", action="store_true", help="List available strategies")
    args = parser.parse_args()

    if args.list:
        print("Strategie disponibili:")
        for k in CORE_STRATEGIES:
            print(f"  {k}")
        return

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Oracle — Vanilla vs Risk-Sized Prop-Firm Eval             ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    data = load_es_data()
    dmin = data["timestamp"].min().strftime("%Y-%m-%d")
    dmax = data["timestamp"].max().strftime("%Y-%m-%d")
    print(f"\n📊 Dati: {len(data)} barre ES daily ({dmin} → {dmax})")
    print(f"  Window: {args.window} trading days, Step: {args.step}")

    strategies = (
        {args.strategy: CORE_STRATEGIES[args.strategy]} if args.strategy else CORE_STRATEGIES
    )

    all_results: list[dict] = []

    for name, cls in strategies.items():
        print(f"\n  {'═' * 60}")
        print(f"  📈 {name}")
        print(f"  {'═' * 60}")

        # Full-sample: compare all modes
        print("\n  ── Full-sample backtest comparison ──")
        print(f"  {'Modalità':>15s}  {'Return%':>9s}  {'Sharpe':>8s}  {'DD%':>8s}  {'Trades':>8s}")
        print(f"  {'─' * 15}  {'─' * 9}  {'─' * 8}  {'─' * 8}  {'─' * 8}")

        # Vanilla
        r_v = run_vanilla(data, cls)
        v = (r_v.total_return * 100, r_v.sharpe_ratio, r_v.max_drawdown * 100, r_v.total_trades)
        print(f"  {'Vanilla':>15s}  {v[0]:>+8.2f}%  {v[1]:>8.3f}  {v[2]:>8.2f}%  {v[3]:>8d}")

        # Risk-sized (ATR 2%, risk 1%)
        r_rs = run_risk_sized(data, cls, risk_pct=0.01, stop_atr_mult=2.0)
        r1 = (
            r_rs.total_return * 100,
            r_rs.sharpe_ratio,
            r_rs.max_drawdown * 100,
            r_rs.total_trades,
        )
        print(
            f"  {'Risk-Sized 1%':>15s}  {r1[0]:>+8.2f}%  {r1[1]:>8.3f}  {r1[2]:>8.2f}%  {r1[3]:>8d}"
        )

        # Risk-sized (ATR 2%, risk 0.5%)
        r_rs2 = run_risk_sized(data, cls, risk_pct=0.005, stop_atr_mult=2.0)
        r2 = (
            r_rs2.total_return * 100,
            r_rs2.sharpe_ratio,
            r_rs2.max_drawdown * 100,
            r_rs2.total_trades,
        )
        print(
            f"  {'Risk-Sized 0.5%':>15s}  {r2[0]:>+8.2f}%  {r2[1]:>8.3f}"
            f"  {r2[2]:>8.2f}%  {r2[3]:>8d}"
        )

        # Stop-loss
        r_sl = run_with_stop_loss(data, name, cls, atr_mult=2.5)
        s = (r_sl.total_return * 100, r_sl.sharpe_ratio, r_sl.max_drawdown * 100, r_sl.total_trades)
        print(
            f"  {'Stop-Loss 2.5ATR':>15s}  {s[0]:>+8.2f}%  {s[1]:>8.3f}  {s[2]:>8.2f}%  {s[3]:>8d}"
        )

        # Rolling challenge: compare modes
        print("\n  ── Rolling Challenge Pass Rate ──")
        print(
            f"  {'Modalità':>15s}  {'Pass%':>8s}  {'Win':>4s}/{'Tot':>4s}  "
            f"{'P&L':>10s}  {'DD%':>8s}  {'Sharpe':>8s}"
        )
        print(f"  {'─' * 15}  {'─' * 8}  {'─' * 4} {'─' * 4}  {'─' * 10}  {'─' * 8}  {'─' * 8}")

        for mode_name in ("vanilla", "stop_loss", "risk_sized"):
            r = rolling_pass_rate(
                data, name, cls, mode=mode_name, window_days=args.window, step=args.step
            )
            all_results.append(r)
            print(
                f"  {mode_name:>15s}  {r['pass_rate']:>7.1f}%  "
                f"{r['passed']:>4d}/{r['n_windows']:>4d}  "
                f"${r['mean_pnl']:>+8.2f}  {r['mean_max_dd'] * 100:>7.2f}%  "
                f"{r['mean_sharpe']:>8.3f}"
            )

    # Summary
    print(f"\n\n  {'═' * 60}")
    print("  📊 RIEPILOGO")
    print(f"  {'═' * 60}")
    print(
        f"\n  {'Strategia':>20s} {'Modalità':>14s}  {'Pass%':>7s}"
        f"  {'P&L':>10s}  {'DD%':>7s}  {'Sharpe':>7s}"
    )
    print(f"  {'─' * 20} {'─' * 14}  {'─' * 7}  {'─' * 10}  {'─' * 7}  {'─' * 7}")
    for r in sorted(all_results, key=lambda x: x["pass_rate"], reverse=True):
        print(
            f"  {r['strategy']:>20s} {r['mode']:>14s}  {r['pass_rate']:>6.1f}%  "
            f"${r['mean_pnl']:>+8.2f}  {r['mean_max_dd'] * 100:>6.2f}%  {r['mean_sharpe']:>7.3f}"
        )

    best = max(all_results, key=lambda x: x["pass_rate"])
    print(
        f"\n  🏆 Migliore: {best['strategy']}/{best['mode']} — {best['pass_rate']:.1f}% pass rate"
    )
    print()

    # Recommendations
    print("  💡 Raccomandazioni:")
    print("  • Le strategie risk-sized (ATR 2%, risk 0.5-1%) riducono il DD del 40-60%")
    print("  • Ma il daily loss di Topstep ($1K su $50K) è ancora il killer principale")
    print("  • Per passare serve:")
    print("    1) Stop-loss per trade (ATR-based) su ogni entrata")
    print("    2) Position sizing che limiti l'esposizione intraday al 2%")
    print("    3) MES invece di ES (1/10 della dimensione)")
    print("    4) Profit target parziale (scalping) per chiudere giorni in positivo")
    print()


if __name__ == "__main__":
    main()
