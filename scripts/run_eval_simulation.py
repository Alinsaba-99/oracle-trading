"""S0.2 (BL-094) — p(pass) EMPIRICO dell'eval prop-firm su dati reali (replay).

Simula il percorso eval bar-by-bar sui dati reali del lake (ES 1d/1h):
profit target 6%, trailing max loss 4% EOD (ratchet), daily loss opzionale
(Topstep), consistency rule 50%, costi per round-trip — con il sizing bridge
pre-registrato (piano S1.4): 1 contratto ES per unità di segnale su $50K.

La p(pass) qui è MISURATA sulle regole reali e sulle code reali del lake —
non sulla gaussiana sintetica del MC (`scripts/run_eval_economics.py`).
Ogni "attempt" parte flat alla close del bar di warmup e corre finché:
target hit (+6%) con consistency ok → PASS; trailing breach (−4% dal massimo)
o daily loss → FAIL; max_bars scaduti → TIMEOUT; zero trade → NO_TRADES.

Convenzioni (pre-registrate, riportate nel JSON):
- posizione al close[t] secondo direction[t] (point-in-time, no lookahead,
  stessa convenzione di analytics/qualification/walkforward.py)
- sizing: 1 contratto x multiplier ($50 ES) su account $50K → leva = prezzo/1000
- costi: half cost_per_rt su ogni entry e exit (RT totale = cost_per_rt);
  posizione aperta a inizio attempt e non chiusa a timeout senza addebito
- consistency: giorno migliore (netto, con costi) <= frac x P&L totale al
  momento del touch del target; se violata l'attempt CONTINUA (diluizione)
- daily loss: disabilitato di default (piani MFF correnti); Topstep 2% via flag

Uso:
    uv run python scripts/run_eval_simulation.py [--timeframe 1d]
        [--signals donchian_breakout buy_hold]
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from analytics.backtest.providers import read_from_lake
from analytics.qualification.walkforward import SIGNAL_FACTORY

OUTCOME_PASS = "pass"
OUTCOME_BREACH = "breach"
OUTCOME_DAILY_LOSS = "daily_loss"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_NO_TRADES = "no_trades"

DEFAULT_SIGNALS = (*tuple(SIGNAL_FACTORY), "buy_hold")

#: Convenzioni pre-registrate (piano S1.4 sizing bridge)
ACCOUNT_SIZE_USD = 50_000
TARGET_FRAC = 0.06
MAX_LOSS_FRAC = 0.04
DAILY_LOSS_FRAC = 0.0  # piani MFF correnti: assente; Topstep 2% con --daily-loss-frac 0.02
CONSISTENCY_FRAC = 0.5  # MFF eval; Topstep Consistency path 0.4
COST_PER_RT_USD = 8.4  # ES 1 contratto all-in (commissioni+exchange ~$4.2/lato)
CONTRACTS = 1
MULTIPLIER_ES_USD = 50.0

WARMUP_BARS = 250
STEP_BARS = 63
MAX_BARS = 750
MIN_BARS = 60


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervallo di confidenza Wilson 95% su una proporzione."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def eval_day_pnl(
    dirs: np.ndarray,
    closes_diff: np.ndarray,
    *,
    multiplier: float = MULTIPLIER_ES_USD,
    contracts: int = CONTRACTS,
    cost_per_rt_usd: float = COST_PER_RT_USD,
) -> np.ndarray:
    """P&L netto giornaliero di un attempt (punti x moltiplicatore - costi).

    dirs[k] = posizione durante il giorno k (nota alla close precedente);
    costi: entry dell'account a inizio attempt se long, half RT per cambio
    di direzione; nessun addebito per posizione aperta a timeout.
    """
    pnl_raw = dirs * closes_diff * multiplier * contracts
    cost = np.zeros_like(pnl_raw)
    cost[0] = -(cost_per_rt_usd / 2.0) * dirs[0]
    if len(cost) > 1:
        change = np.abs(np.diff(dirs)) > 0
        cost[1:] -= (cost_per_rt_usd / 2.0) * change
    out: np.ndarray = pnl_raw + cost
    return out


def simulate_eval_attempt(
    directions: np.ndarray,
    closes: np.ndarray,
    start: int,
    *,
    account_size: float = ACCOUNT_SIZE_USD,
    target_frac: float = TARGET_FRAC,
    max_loss_frac: float = MAX_LOSS_FRAC,
    daily_loss_frac: float = DAILY_LOSS_FRAC,
    consistency_frac: float = CONSISTENCY_FRAC,
    cost_per_rt_usd: float = COST_PER_RT_USD,
    contracts: int = CONTRACTS,
    multiplier: float = MULTIPLIER_ES_USD,
    max_bars: int = MAX_BARS,
) -> dict[str, Any]:
    """Esito di un singolo attempt eval su dati reali.

    L'account parte FLAT alla close del bar (start-1) e prende la posizione
    direction[start-1] (no lookahead: il segnale è noto a quella close).
    """
    target_usd = target_frac * account_size
    max_loss_usd = max_loss_frac * account_size
    daily_loss_usd = daily_loss_frac * account_size

    end = min(start + max_bars, len(closes))
    bars_avail = end - start
    if bars_avail < 2:
        return {"outcome": OUTCOME_TIMEOUT, "days": 0}

    # Posizione che guadagna nel giorno i (i = start..end-1): direction[i-1]
    dirs = directions[start - 1 : end - 1].astype(np.float64)
    closes_diff = np.diff(closes[start - 1 : end])
    day_pnl = eval_day_pnl(
        dirs,
        closes_diff,
        multiplier=multiplier,
        contracts=contracts,
        cost_per_rt_usd=cost_per_rt_usd,
    )
    if not np.any(dirs):
        return {"outcome": OUTCOME_NO_TRADES, "days": 0}

    total = np.cumsum(day_pnl)
    hwm = np.maximum.accumulate(total)
    best_day = np.maximum.accumulate(day_pnl)

    breach = total < hwm - max_loss_usd
    target = total >= target_usd
    daily = day_pnl < -daily_loss_usd if daily_loss_usd > 0 else np.zeros_like(total, dtype=bool)

    # Target: il primo giorno con total >= target E consistency soddisfatta.
    # La consistency si valuta sul P&L del giorno di touch (diluizione).
    consistent = best_day <= consistency_frac * total
    passable = target & consistent
    first_pass = int(np.argmax(passable)) if np.any(passable) else None
    first_breach = int(np.argmax(breach)) if np.any(breach) else None
    first_daily = int(np.argmax(daily)) if np.any(daily) else None

    # Primo evento tra i candidati; in caso di stesso giorno, la daily loss è
    # la regola piu' specifica (precedenza: pass, daily_loss, breach).
    candidates: list[tuple[int, str]] = []
    if first_pass is not None:
        candidates.append((first_pass, OUTCOME_PASS))
    if first_daily is not None:
        candidates.append((first_daily, OUTCOME_DAILY_LOSS))
    if first_breach is not None:
        candidates.append((first_breach, OUTCOME_BREACH))
    if not candidates:
        return {"outcome": OUTCOME_TIMEOUT, "days": bars_avail}
    precedence = {OUTCOME_PASS: 0, OUTCOME_DAILY_LOSS: 1, OUTCOME_BREACH: 2}
    first_idx, outcome = min(candidates, key=lambda c: (c[0], precedence[c[1]]))

    result: dict[str, Any] = {"outcome": outcome, "days": first_idx + 1}
    if outcome == OUTCOME_PASS:
        result["blocked_before"] = bool(np.any(target[:first_idx] & ~consistent[:first_idx]))
    return result


def generate_attempt_starts(
    n_bars: int, *, warmup: int = WARMUP_BARS, step: int = STEP_BARS, min_bars: int = MIN_BARS
) -> list[int]:
    """Start degli attempt walk-forward: ogni step bars, con warmup e margine."""
    return list(range(warmup, n_bars - min_bars, step))


def run_signal_eval(
    directions: np.ndarray, closes: np.ndarray, *, max_bars: int = MAX_BARS, **attempt_kwargs: Any
) -> dict[str, Any]:
    """Tutti gli attempt walk-forward per un segnale: aggregazione con CI."""
    starts = generate_attempt_starts(len(closes))
    outcomes: list[str] = []
    days_to_pass: list[int] = []
    blocked = 0
    for start in starts:
        res = simulate_eval_attempt(directions, closes, start, max_bars=max_bars, **attempt_kwargs)
        outcomes.append(res["outcome"])
        if res["outcome"] == OUTCOME_PASS:
            days_to_pass.append(int(res["days"]))
            blocked += int(res.get("blocked_before", False))

    n = len(outcomes)
    k = outcomes.count(OUTCOME_PASS)
    lo, hi = wilson_ci(k, n)
    agg: dict[str, Any] = {
        "attempts": n,
        "p_pass": round(k / n, 4) if n else 0.0,
        "wilson_95_ci": [round(lo, 4), round(hi, 4)],
        "n_pass": k,
        "n_breach": outcomes.count(OUTCOME_BREACH),
        "n_daily_loss": outcomes.count(OUTCOME_DAILY_LOSS),
        "n_timeout": outcomes.count(OUTCOME_TIMEOUT),
        "n_no_trades": outcomes.count(OUTCOME_NO_TRADES),
        "passes_consistency_blocked": blocked,
    }
    if days_to_pass:
        arr = np.asarray(days_to_pass, dtype=float)
        agg["mean_days_to_pass"] = round(float(arr.mean()), 1)
        agg["median_days_to_pass"] = round(float(np.median(arr)), 1)
        agg["p90_days_to_pass"] = round(float(np.percentile(arr, 90)), 1)
    return agg


def _directions_for(signal_name: str, df: Any) -> np.ndarray:
    if signal_name == "buy_hold":
        return np.ones(df.height, dtype=np.float64)
    signal = SIGNAL_FACTORY[signal_name]()
    series = signal.compute(df)
    if series is None or series.len() != df.height:
        raise ValueError(f"{signal_name}: signal series mismatch")
    return np.asarray(series.to_list(), dtype=np.float64)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="ES")
    parser.add_argument("--timeframe", default="1d", choices=["1d", "1h"])
    parser.add_argument("--signals", nargs="+", default=list(DEFAULT_SIGNALS))
    parser.add_argument("--account-size", type=float, default=ACCOUNT_SIZE_USD)
    parser.add_argument("--daily-loss-frac", type=float, default=DAILY_LOSS_FRAC)
    parser.add_argument("--consistency-frac", type=float, default=CONSISTENCY_FRAC)
    parser.add_argument("--cost-per-rt-usd", type=float, default=COST_PER_RT_USD)
    parser.add_argument("--contracts", type=int, default=CONTRACTS)
    parser.add_argument("--multiplier", type=float, default=MULTIPLIER_ES_USD)
    parser.add_argument("--max-bars", type=int, default=MAX_BARS)
    parser.add_argument("--step", type=int, default=STEP_BARS)
    parser.add_argument("--out", default="docs/reports/s0-2/eval_simulation.json")
    args = parser.parse_args(argv)

    df = read_from_lake(args.symbol, args.timeframe)
    if df is None:
        print(f"FATAL: lake has no {args.symbol}|{args.timeframe}")
        return 2
    closes = df["close"].to_numpy().astype(np.float64)

    results: dict[str, Any] = {}
    for signal_name in args.signals:
        if signal_name != "buy_hold" and signal_name not in SIGNAL_FACTORY:
            print(f"FATAL: unknown signal {signal_name!r}")
            return 2
        directions = _directions_for(signal_name, df)
        agg = run_signal_eval(
            directions,
            closes,
            max_bars=args.max_bars,
            account_size=args.account_size,
            daily_loss_frac=args.daily_loss_frac,
            consistency_frac=args.consistency_frac,
            cost_per_rt_usd=args.cost_per_rt_usd,
            contracts=args.contracts,
            multiplier=args.multiplier,
        )
        in_position = int(np.count_nonzero(directions))
        agg["bars"] = int(df.height)
        agg["bars_in_position"] = in_position
        agg["position_share"] = round(in_position / df.height, 4)
        mean_price = float(np.mean(closes))
        notional = args.multiplier * args.contracts * mean_price
        agg["mean_leverage"] = round(notional / args.account_size, 2)
        results[signal_name] = agg
        ci = agg["wilson_95_ci"]
        print(
            f"{signal_name:<24s} p_pass={agg['p_pass']:.1%} CI95=[{ci[0]:.1%},{ci[1]:.1%}] "
            f"N={agg['attempts']} pass={agg['n_pass']} breach={agg['n_breach']} "
            f"timeout={agg['n_timeout']} no_trade={agg['n_no_trades']} "
            f"med={agg.get('median_days_to_pass', float('nan'))}d "
            f"blocked={agg['passes_consistency_blocked']}"
        )

    report: dict[str, Any] = {
        "schema": "s0-2-eval-simulation-v1",
        "generated_by": "scripts/run_eval_simulation.py",
        "date": date.today().isoformat(),
        "method": (
            "replay bar-by-bar su dati reali lake; eval 6%/4% EOD trailing ratchet; "
            "sizing 1 contratto ES/$50K (pre-registrato S1.4); daily loss e consistency "
            "opzionali; attempts walk-forward step=" + str(args.step)
        ),
        "params": {
            "symbol": args.symbol,
            "timeframe": args.timeframe,
            "rows": int(df.height),
            "account_size_usd": args.account_size,
            "target_frac": TARGET_FRAC,
            "max_loss_frac": MAX_LOSS_FRAC,
            "daily_loss_frac": args.daily_loss_frac,
            "consistency_frac": args.consistency_frac,
            "cost_per_rt_usd": args.cost_per_rt_usd,
            "contracts": args.contracts,
            "multiplier_usd_per_pt": args.multiplier,
            "warmup_bars": WARMUP_BARS,
            "step_bars": args.step,
            "max_bars": args.max_bars,
            "min_bars": MIN_BARS,
        },
        "results": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nJSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
