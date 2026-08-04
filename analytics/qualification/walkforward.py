"""BL-023 Fase 2 — multi-asset walk-forward for the trend-family candidates.

Tests whether the real-but-insufficient edge of the trend/breakout family
(donchian_breakout, trend_filtered_breakout, ema_trend — luck p<=0.012 on ES,
but Sharpe < 0.5) SURVIVES out-of-sample on other assets.

Method — signal-level (scale-free, no broker/prop-firm economics):
  - load ES, SPY, BTCUSDT 1d from the lake (same source as the M31 gate)
  - compute the candidate signal over the FULL series (point-in-time: the
    signal classes only use past bars, so direction[t] is known at close[t])
  - strategy returns: direction shifted by one bar x asset pct-change
    (position taken at next close — no lookahead)
  - split: train < 2023-01-01, TEST >= 2023-01-01 (same convention as
    probe_signal_candidates.py; the M31 gate windows all sit in 2023+,
    so the test period here is a walk-forward proxy of the gate)
  - metrics on TEST ONLY: annualized Sharpe, max drawdown, hit rate,
    bars in position, pooled luck p (bootstrap_luck_p_value), buy&hold
    Sharpe for comparison (does the signal beat just holding the asset?)

Verdict rule (documented, no tuning):
  A signal "confirms the edge" on an asset when TEST Sharpe >= 0.3 AND
  luck p < 0.1 AND TEST Sharpe BEATS the buy&hold Sharpe (S_test > BH_S).
  The buy&hold comparison is the anti-beta guard: a near-always-long
  signal on a bull market shows a high Sharpe that is pure beta, not
  alpha — it must at least beat just holding the asset. The signal
  survives multi-asset when >= 2/3 assets confirm (majority,
  anti-overfit: one lucky asset is noise).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from analytics.backtest.providers import read_from_lake
from analytics.qualification.statistics import bootstrap_luck_p_value, factor_attribution
from analytics.strategy.signals import DonchianBreakout, EmaTrend, TrendFilteredBreakout

#: Lake row pins (BL-023 F-07 convention: the pin IS the provenance check;
#: the lake is live — bump when it grows). Verified 2026-08-04:
#: ES 6523, SPY 6679, BTCUSDT 3275 rows.
EXPECTED_ROWS: dict[str, int] = {"ES": 6523, "SPY": 6679, "BTCUSDT": 3275}

TRAIN_CUTOFF = datetime(2023, 1, 1)
REPORT_DIR = Path("docs/reports/multiasset")
PERIODS_PER_YEAR = 252

#: Winning trend-family candidates from the Fase 5c sweep (8/8 REJECTED in the
#: gate, but luck p<=0.012 = real edge, insufficient). Identical constructors
#: to the probe / gate factory (train pre-2023 derivation).
SIGNAL_FACTORY: dict[str, type[Any]] = {
    "donchian_breakout": DonchianBreakout,
    "trend_filtered_breakout": TrendFilteredBreakout,
    "ema_trend": EmaTrend,
}


def load_frame(symbol: str) -> pl.DataFrame:
    frame = read_from_lake(symbol, "1d")
    expected = EXPECTED_ROWS[symbol]
    if frame is None or frame.height != expected:
        rows = frame.height if frame is not None else 0
        raise ValueError(
            f"Lake {symbol}|1d row-count mismatch: got {rows}, expected {expected} (pin stale?)"
        )
    return frame.with_columns(pl.col("timestamp").dt.replace_time_zone(None))


def strategy_returns(directions: np.ndarray, closes: np.ndarray) -> np.ndarray:
    """Long/flat strategy returns: position taken at NEXT close (no lookahead).

    direction[t] is known at close[t] (point-in-time signal), so the position
    earns return[t+1] = close[t+1]/close[t] - 1.
    """
    n_returns = min(len(directions), len(closes) - 1)
    if n_returns < 1:
        return np.asarray([], dtype=float)
    rets = closes[1 : n_returns + 1] / closes[:n_returns] - 1.0
    pos = directions[:n_returns].astype(float)
    strategy = pos * rets
    clean: np.ndarray = strategy[np.isfinite(strategy)]
    return clean


def max_drawdown(returns: np.ndarray) -> float:
    if returns.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    drawdowns = 1.0 - equity / np.where(peak > 0, peak, 1.0)
    return float(np.max(drawdowns)) if drawdowns.size else 0.0


def sharpe(returns: np.ndarray) -> float:
    if returns.size < 2:
        return 0.0
    std = float(np.std(returns, ddof=1))
    if std <= 0:
        return 0.0
    mean: float = float(np.mean(returns))
    result: float = mean / std * float(np.sqrt(PERIODS_PER_YEAR))
    return result


def evaluate(symbol: str, signal_name: str, df: pl.DataFrame) -> dict[str, Any]:
    closes = df["close"].to_numpy().astype(np.float64)
    timestamps = df["timestamp"].to_list()

    signal = SIGNAL_FACTORY[signal_name]()
    series = signal.compute(df)
    if series is None or series.len() != df.height:
        raise ValueError(f"{signal_name} on {symbol}: signal series mismatch")
    directions = np.asarray(series.to_list(), dtype=np.float64)

    full_returns = strategy_returns(directions, closes)
    test_returns = np.asarray([], dtype=float)
    train_returns = np.asarray([], dtype=float)
    for i in range(1, len(closes)):
        ret = closes[i] / closes[i - 1] - 1.0
        if timestamps[i] >= TRAIN_CUTOFF:
            test_returns = np.append(test_returns, ret * directions[i - 1])
        else:
            train_returns = np.append(train_returns, ret * directions[i - 1])
    test_returns = test_returns[np.isfinite(test_returns)]
    buy_hold_test = np.asarray(
        [
            closes[i] / closes[i - 1] - 1.0
            for i in range(1, len(closes))
            if timestamps[i] >= TRAIN_CUTOFF
        ],
        dtype=float,
    )
    buy_hold_test = buy_hold_test[np.isfinite(buy_hold_test)]

    in_position = int(np.count_nonzero(directions[1:]))
    hit_rate = float(np.mean(test_returns > 0)) if test_returns.size else 0.0
    luck_p = bootstrap_luck_p_value(test_returns)
    sharpe_test = sharpe(test_returns)
    dd_test = max_drawdown(test_returns)
    bh_sharpe = sharpe(buy_hold_test)
    bh_dd = max_drawdown(buy_hold_test)
    # Anti-beta guard: alpha of the signal vs the buy&hold benchmark on the
    # test period. A near-always-long signal on a bull market has high Sharpe
    # that is pure beta — factor_attribution isolates the annualized alpha.
    attribution = factor_attribution(test_returns, buy_hold_test)
    alpha_test = float(attribution.get("annualized_alpha", 0.0))
    confirmed = (
        sharpe_test >= 0.3 and luck_p is not None and luck_p < 0.1 and sharpe_test > bh_sharpe
    )

    return {
        "symbol": symbol,
        "signal": signal_name,
        "bars": int(df.height),
        "bars_in_position": in_position,
        "test_bars": int(test_returns.size),
        "train_bars": int(train_returns.size),
        "sharpe_train": round(sharpe(train_returns), 4),
        "sharpe_test": round(sharpe_test, 4),
        "max_drawdown_test": round(dd_test, 4),
        "hit_rate_test": round(hit_rate, 4),
        "luck_p_test": None if luck_p is None else round(float(luck_p), 4),
        "buy_hold_sharpe_test": round(bh_sharpe, 4),
        "buy_hold_dd_test": round(bh_dd, 4),
        "alpha_test": round(alpha_test, 4),
        "edge_confirmed": bool(confirmed),
        "full_returns_sharpe": round(sharpe(full_returns), 4),
    }


def format_row(result: dict[str, Any]) -> str:
    luck = "n/a" if result["luck_p_test"] is None else f"{result['luck_p_test']:.3f}"
    mark = "✅" if result["edge_confirmed"] else "❌"
    return (
        f"  {result['symbol']:<8s} {result['signal']:<24s} {mark} "
        f"S_test={result['sharpe_test']:>+7.3f} alpha={result['alpha_test']:>+7.3f} "
        f"DD={result['max_drawdown_test'] * 100:>5.1f}% hit={result['hit_rate_test'] * 100:>4.0f}% "
        f"luck={luck:<6s} BH_S={result['buy_hold_sharpe_test']:>+6.2f} "
        f"bars={result['bars_in_position']:>5d}"
    )


def format_markdown(report: dict[str, Any]) -> str:
    """Human-readable markdown summary (same content as the JSON report)."""
    lines: list[str] = [
        "# Walk-forward multi-asset — family trend/breakout (BL-023 Fase 2)",
        "",
        f"- Metodo: {report['method']}",
        f"- Train cutoff: `{report['train_cutoff']}` — test: `{report['test_period']}`",
        f"- Regola verdetto: `{report['verdict_rule']}`",
        f"- Asset: {', '.join(report['assets'])} — Segnali: {', '.join(report['signals'])}",
        "",
        "## Risultati per asset × segnale (test period)",
        "",
        "| Asset | Segnale | S_test | alpha (annuo) | DD | hit | luck p | BH_S | esito |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for result in report["results"]:
        luck = "n/a" if result["luck_p_test"] is None else f"{result['luck_p_test']:.3f}"
        mark = "✅ confermato" if result["edge_confirmed"] else "❌ non batte BH"
        lines.append(
            f"| {result['symbol']} | {result['signal']} | {result['sharpe_test']:+.3f} "
            f"| {result['alpha_test']:+.3f} | {result['max_drawdown_test'] * 100:.1f}% "
            f"| {result['hit_rate_test'] * 100:.0f}% | {luck} "
            f"| {result['buy_hold_sharpe_test']:+.2f} | {mark} |"
        )
    lines.append("")
    lines.append("## Verdetto multi-asset (sopravvive = ≥2/3 asset confermati)")
    lines.append("")
    for signal_name, verdict in report["verdicts"].items():
        confirmed = ", ".join(verdict["assets_confirmed"]) or "nessuno"
        state = "✅ SOPRAVVIVE" if verdict["survives_multiasset"] else "❌ NON SOPRAVVIVE"
        lines.append(
            f"- **{signal_name}**: {state} ({len(verdict['assets_confirmed'])}/3: {confirmed})"
            f" — mean S_test {verdict['mean_sharpe_test']:+.3f}"
        )
    lines.append("")
    overall = report["overall"]["any_signal_survives"]
    if overall:
        lines.append("**Verdetto complessivo**: ✅ qualche segnale sopravvive")
    else:
        lines.append("**Verdetto complessivo**: ❌ nessun segnale sopravvive fuori campione")
    lines.append("")
    lines.append("> Nota anti-beta: un segnale quasi-sempre-long su mercato rialzista")
    lines.append("> mostra Sharpe alto (beta). La conferma richiede S_test > Sharpe del")
    lines.append("> buy&hold: l'alpha, non il beta.")
    return "\n".join(lines) + "\n"
