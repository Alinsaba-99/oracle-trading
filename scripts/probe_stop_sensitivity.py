"""BL-023 P1a — Stop sensitivity probe on the ES 1d lake.

Measures how the stop-loss rule affects qualification metrics before any
G5 verdict. Runs the event-driven runner over the SAME replay periods
(5 non-macro regimes) with several stop configurations:

- fixed points: 5 / 15 / 30 / 60
- ATR multiple: 1x / 2x / 3x (point-in-time, period=14)

Output: comparative table + JSON in docs/reports/m31-rerun/stop-probe.json.
The macro regime is NOT covered here (P1d handles macro feasibility); the
probe deliberately skips the macro blocker so stop sensitivity can be
measured on the regimes that exist in the lake.

Usage:
    uv run --frozen python scripts/probe_stop_sensitivity.py
    uv run --frozen python scripts/probe_stop_sensitivity.py --quantities 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

from analytics.backtest.providers import read_from_lake
from analytics.qualification.execution import EventDrivenQualificationRunner
from analytics.qualification.intelligence import build_offline_intelligence_artifact
from analytics.qualification.models import ReplayObservation, ReplayVariant
from analytics.qualification.periods import select_replay_periods, slice_period
from analytics.strategy.lorentzian import LorentzianKNN
from analytics.strategy.regime_ensemble import RegimeAwareEnsemble, SpecialistId
from analytics.strategy.signals import DonchianBreakout, RocMomentum, RsiReversion
from market.contracts import MES
from policy.prop_firm.fixtures import TOPSTEP_TC_50K

EXPECTED_ROWS = 6522  # ES|1d lake pin (BL-023 F-07)

FIXED_STOPS: tuple[float, ...] = (5.0, 15.0, 30.0, 60.0)
ATR_MULTIPLES: tuple[float, ...] = (1.0, 2.0, 3.0)


def _signal() -> RegimeAwareEnsemble:
    """Reference signal for the stop probe — RocMomentum(12) wrapped in the
    ensemble scaffold.

    NOTE (finding BL-023 P1a): the default ensemble v2 (min_confidence=0.5)
    produces ZERO targets inside the selected replay windows (all signal
    activity falls in the warmup), so it cannot be used to measure stop
    sensitivity — the run would be 0 trades, Sharpe 0 (same as the BL-024
    "30/30" run). The probe isolates the STOP effect, so it uses a signal
    that actually trades in every window; the ensemble's zero-trade
    behaviour is a separate finding for the G5 decision point.
    """
    return RegimeAwareEnsemble(
        specialists={
            SpecialistId.TREND: RocMomentum(period=12),
            SpecialistId.MEAN_REVERSION: RsiReversion(period=14),
            SpecialistId.BREAKOUT: DonchianBreakout(period=10),
            SpecialistId.LORENTZIAN: LorentzianKNN(
                k=4, lookahead=4, max_bars_back=80, feature_count=3
            ),
        },
        min_confidence=0.5,
    )


def _label(mode: str, value: float) -> str:
    return f"{mode}:{value:g}" if mode == "fixed" else f"atr:{value:g}x"


async def _run_config(
    runner: EventDrivenQualificationRunner,
    data: pl.DataFrame,
    periods: list[Any],
    quantities: list[int],
) -> dict[str, Any]:
    observations: list[ReplayObservation] = []
    skipped = 0
    risk_rejections = 0
    fills = 0
    for period in periods:
        period_data = slice_period(data, period, warmup_bars=100)
        for variant in (ReplayVariant.control(),):
            for qty in quantities:
                artifact = build_offline_intelligence_artifact(period, variant)
                try:
                    obs = await runner.run(
                        period_data, period, variant, intelligence_artifact=artifact
                    )
                    observations.append(obs)
                    if obs.execution_evidence is not None:
                        risk_rejections += obs.execution_evidence.risk_rejections
                        fills += obs.execution_evidence.fills_recorded
                except (RuntimeError, ValueError) as exc:
                    skipped += 1
                    print(f"    skip {period.name}/qty{qty}: {exc}")
    sharpes = [o.metrics.sharpe_ratio for o in observations if o.metrics.sharpe_ratio is not None]
    dds = [o.metrics.max_drawdown for o in observations if o.metrics.max_drawdown is not None]
    breaches = sum(o.metrics.hard_breaches for o in observations)
    liquidated = sum(1 for o in observations if o.metrics.liquidated)
    return {
        "observations": len(observations),
        "skipped": skipped,
        "median_sharpe": round(statistics.median(sharpes), 4) if sharpes else None,
        "worst_dd": round(max(dds), 4) if dds else None,
        "total_breaches": int(breaches),
        "liquidated": int(liquidated),
        "risk_rejections": int(risk_rejections),
        "fills": int(fills),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quantities", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--periods-slice", type=int, default=5)
    parser.add_argument(
        "--json-output", type=Path, default=Path("docs/reports/m31-rerun/stop-probe.json")
    )
    args = parser.parse_args()

    data = read_from_lake("ES", "1d")
    if data is None:
        print("FATAL: ES 1d not in lake")
        return 2
    if data.height != EXPECTED_ROWS:
        print(f"FATAL: lake ES|1d row-count {data.height} != pinned {EXPECTED_ROWS}")
        return 2

    # Non-macro regimes only: the macro blocker is a P1d concern, not a
    # stop-sensitivity concern. We select periods and drop the macro one.
    selection = select_replay_periods(data, window_bars=40)
    periods = [p for p in selection.periods if p.regime.value != "macro_surprise"][
        : args.periods_slice
    ]
    print(f"Dataset: ES 1d lake ({data.height} bars)")
    print(f"Periods: {[p.name for p in periods]}")
    print(f"Quantities: {args.quantities}")
    print()

    signal = _signal()
    results: dict[str, dict[str, Any]] = {}
    for mode, values in (("fixed", FIXED_STOPS), ("atr", ATR_MULTIPLES)):
        for value in values:
            label = _label(mode, value)
            kwargs: dict[str, Any] = (
                {"stop_distance_points": Decimal(str(value))}
                if mode == "fixed"
                else {
                    "stop_mode": "atr",
                    "atr_multiple": value,
                    "stop_distance_points": Decimal("5"),
                }
            )
            runner = EventDrivenQualificationRunner(
                signal=signal,
                contract=MES,
                initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
                prop_profile=TOPSTEP_TC_50K,
                profile_certified=True,
                periods_per_year=252,
                liquidate_on_hard_breach=True,
                **kwargs,
            )
            print(f"[{label}] running {len(periods) * len(args.quantities)} observations...")
            results[label] = asyncio.run(_run_config(runner, data, periods, args.quantities))

    print()
    print(
        f"{'stop':<12} {'obs':>4} {'medianSh':>9} {'worstDD':>8} {'breaches':>8} "
        f"{'liq':>4} {'fills':>6} {'riskRej':>7}"
    )
    for label, r in results.items():
        print(
            f"{label:<12} {r['observations']:>4} "
            f"{r['median_sharpe']!s:>9} {r['worst_dd']!s:>8} "
            f"{r['total_breaches']:>8} {r['liquidated']:>4} "
            f"{r['fills']:>6} {r['risk_rejections']:>7}"
        )

    payload = {
        "title": "BL-023 P1a — stop sensitivity probe (ES 1d lake)",
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset": f"lake:ES:1d ({data.height} bars)",
        "periods": [p.name for p in periods],
        "quantities": args.quantities,
        "results": results,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2))
    print(f"\nJSON: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
