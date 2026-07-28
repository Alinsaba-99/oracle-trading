"""Smoke test: evaluate a handful of specs end-to-end against the real lake."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.backtest.providers import DataRegistry
from analytics.strategy.evaluator import evaluate_spec
from analytics.strategy.fitness import EvalMode
from analytics.strategy.spec import ENTRY_TYPES, INSTRUMENTS, StrategySpec

_ROOT = Path(__file__).parent.parent


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    registry = DataRegistry(root=_ROOT / "data" / "ohlcv")

    print(f"search space: {len(INSTRUMENTS)} instruments x {len(ENTRY_TYPES)} entry types")

    probes = [
        ("supertrend", "GOLD", "1d"),
        ("regime_switch", "EURUSD", "4h"),
        ("golden_cross", "GBPJPY", "1d"),
        ("liquidity_sweep", "BTC", "4h"),
        ("donchian_breakout", "GOLD", "1d"),
    ]

    ok = 0
    for entry, instrument, tf in probes:
        spec = StrategySpec(
            name=f"probe_{entry}_{instrument}",
            instrument=instrument,
            entry=entry,
            timeframe=tf,
            regime="sized",
        )
        try:
            report = evaluate_spec(spec, registry, EvalMode.FIRM)
        except Exception as exc:
            print(f"  FAIL {entry:<22} {instrument:<8} {tf:<3} -> {type(exc).__name__}: {exc}")
            continue
        ok += 1
        print(
            f"  ok   {entry:<22} {instrument:<8} {tf:<3} "
            f"fit={report.fitness:>7.4f} mc={report.mc_pass_rate * 100:>5.1f}% "
            f"sharpe={report.sharpe:>6.2f} dd={abs(report.max_drawdown) * 100:>5.1f}% "
            f"trades={report.total_trades}"
        )

    print(f"\n{ok}/{len(probes)} probes evaluated")
    return 0 if ok == len(probes) else 1


if __name__ == "__main__":
    sys.exit(main())
