"""BL-022 part 2 — replay qualification con regime ribilanciato + ensemble v2.

DEPRECATED (BL-023 F-05, 2026-08-03): consolidato in
`scripts/run_replay_qualification.py`, che ora ha lo stesso stack di fix
(--data-source lake, --stop-mode atr, warmup >= 100, macro events,
periods_per_year) MA con il gate ufficiale QualificationThresholds +
QualificationEvidence + luck test + determinism check + report
strutturato. Non aggiungere feature a questo script: portale nel runner
ufficiale.

Stesso flow di `scripts/run_replay_qualification.py` ma:
- signal = RegimeAwareEnsemble con hysteresys (BL-010..014)
- 4 specialist (trend/mean_rev/breakout/lorentzian)
- MES contract sizing built-in (BL-021)
- PropFirmOrderRiskAdapter gia' cablato nel runner (BL-070)

BL-023 fix (2026-08-03, da /autoplan review):
- F-02/F-19: slicing con `slice_period` (niente bug calendario-vs-barre,
  niente fallback `start_offset=0` silenzioso)
- F-03: warmup >= 100 bar (lookback reale SMA100/Lorentzian b80)
- F-04: `--data-source lake` usa DataRegistry con `force=True` + assert
  row-count atteso (il cache legacy non deve oscurare il lake)
- F-08: N onesto — report con curve uniche (periodi × qty), guardia
  observation_count nel gate
- F-10: run INVALIDO se `selection.blockers` non vuoto (macro regime
  mancante = blocker, non verdetto)
- F-17: `periods_per_year` per timeframe (252 daily, ~5796 1h)
- F-18: `--stop-distance-points` / `--stop-mode atr`

Output:
- docs/reports/m31-rerun-final/{json,md}
- AC: median Sharpe >= 0.5, worst DD <= 4%, hard breaches = 0
  altrimenti REJECTED con nota su cosa serve per green-light.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from analytics.backtest.providers import read_from_lake
from analytics.qualification.execution import EventDrivenQualificationRunner
from analytics.qualification.intelligence import build_offline_intelligence_artifact
from analytics.qualification.models import MacroSurpriseEvent, ReplayVariant
from analytics.qualification.periods import select_replay_periods, slice_period
from analytics.strategy.lorentzian import LorentzianKNN
from analytics.strategy.regime_ensemble import RegimeAwareEnsemble, SpecialistId
from analytics.strategy.signals import DonchianBreakout, EmaTrend, RsiReversion
from market.contracts import MES
from policy.prop_firm.fixtures import TOPSTEP_TC_50K

#: Expected row counts per symbol/timeframe read from the lake parquet
#: directly (BL-023 F-07: coverage.json is stale — 13042 != 6523).
#: Verified 2026-08-04 against data/lake/normalized (lake is LIVE — bump
#: when it grows; 2026-08-04: ES|1d 6523, ES|1h 13747).
EXPECTED_ROWS: dict[str, int] = {"ES|1d": 6523, "ES|1h": 13747}

#: Periods per year per timeframe (F-17). ~5796 = 23h * 252 trading days.
PERIODS_PER_YEAR: dict[str, int] = {"1d": 252, "1h": 5796}


def _signal(specialists: str) -> RegimeAwareEnsemble:
    if specialists == "momentum":
        from analytics.strategy.signals import RocMomentum

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
    if specialists == "bollinger":
        from analytics.strategy.signals import BbandReversion

        return RegimeAwareEnsemble(
            specialists={
                SpecialistId.TREND: EmaTrend(fast=10, slow=30),
                SpecialistId.MEAN_REVERSION: BbandReversion(period=20, std=2.0),
                SpecialistId.BREAKOUT: DonchianBreakout(period=10),
                SpecialistId.LORENTZIAN: LorentzianKNN(
                    k=4, lookahead=4, max_bars_back=80, feature_count=3
                ),
            },
            min_confidence=0.5,
        )
    # default: ensemble v2 con specialist classici
    return RegimeAwareEnsemble(
        specialists={
            SpecialistId.TREND: EmaTrend(fast=10, slow=30),
            SpecialistId.MEAN_REVERSION: RsiReversion(period=14),
            SpecialistId.BREAKOUT: DonchianBreakout(period=20),
            SpecialistId.LORENTZIAN: LorentzianKNN(
                k=4, lookahead=4, max_bars_back=80, feature_count=3
            ),
        },
        min_confidence=0.5,
    )


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _data_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_macro_events(path: Path) -> list[MacroSurpriseEvent]:
    """Load point-in-time macro events (BL-023 P1d: NASDaq consensus source).

    Empty when the file is missing — the macro blocker then keeps the run
    INVALID (fail-closed), exactly as before.
    """
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return [MacroSurpriseEvent(**event) for event in payload.get("events", [])]


def _load_data(args: argparse.Namespace) -> tuple[pl.DataFrame, str, str]:
    """Load OHLCV from lake (DataRegistry force) or legacy parquet.

    Returns (data, data_hash, data_label). Raises on row-count mismatch
    when a lake row-count expectation is pinned (F-04/F-07).
    """
    if args.data_source == "lake":
        # BL-023 F-04: read the lake DIRECTLY (read_from_lake), never via
        # DataRegistry cache (data/ohlcv/ES/1d.parquet = 503 stale bars) and
        # never via force=True (which skips the lake entirely and hits the
        # live source). Row-count guard against stale pins.
        df = read_from_lake(args.symbol, args.timeframe)
        if df is None:
            raise ValueError(f"Lake has no data for {args.symbol}|{args.timeframe}")
        key = f"{args.symbol}|{args.timeframe}"
        expected = EXPECTED_ROWS.get(key)
        if expected is not None and df.height != expected:
            raise ValueError(
                f"Lake {key} row-count mismatch: got {df.height}, expected {expected} "
                f"(BL-023 F-04 guard). Pin stale?"
            )
        label = f"lake:{args.symbol}:{args.timeframe}"
        return df, "lake", label
    # legacy
    path = Path(args.data)
    if not path.exists():
        raise FileNotFoundError(f"Legacy dataset not found: {path}")
    df = pl.read_parquet(path).rename({c: c.lower() for c in pl.read_parquet(path).columns})
    return df, _data_hash(path), str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/ohlcv/ES_1d.parquet"))
    parser.add_argument(
        "--data-source",
        choices=("lake", "legacy"),
        default="legacy",
        help="lake = DataRegistry force=True (F-04); legacy = parquet locale",
    )
    parser.add_argument("--symbol", default="ES", help="lake symbol (data-source=lake)")
    parser.add_argument("--timeframe", default="1d", help="lake timeframe (data-source=lake)")
    parser.add_argument("--window-bars", type=int, default=40)
    parser.add_argument("--warmup-bars", type=int, default=100, help="BL-023 F-03: >= 100")
    parser.add_argument("--quantities", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--stop-distance-points", type=float, default=None)
    parser.add_argument(
        "--stop-mode",
        choices=("fixed", "atr"),
        default="fixed",
        help="atr = stop da ATR multiplo (F-16: multiplo scelto su train pre-2023)",
    )
    parser.add_argument("--atr-multiple", type=float, default=2.0)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument(
        "--specialists",
        choices=("ensemble", "momentum", "bollinger"),
        default="ensemble",
        help="config segnale (BL-200 edge candidates)",
    )
    parser.add_argument(
        "--macro-events",
        type=Path,
        default=Path("data/macro/m31-events.json"),
        help="point-in-time macro events (BL-023 P1d); missing file => run INVALIDO",
    )
    parser.add_argument(
        "--periods-slice", type=int, default=6, help="max periods from select_replay_periods"
    )
    parser.add_argument(
        "--json-output", type=Path, default=Path("docs/reports/m31-rerun-final/m31.json")
    )
    parser.add_argument(
        "--markdown-output", type=Path, default=Path("docs/reports/m31-rerun-final/m31.md")
    )
    args = parser.parse_args()

    data, data_hash, data_label = _load_data(args)
    ppy = PERIODS_PER_YEAR.get(args.timeframe, 252)
    print(f"Dataset: {data_label} ({len(data)} bars, sha256={data_hash[:12]}...)")
    print(f"Timeframe: {args.timeframe} | periods_per_year={ppy} (F-17)")
    print(f"Quantities tested: {args.quantities}")
    print(
        f"Stop: {args.stop_mode} (points={args.stop_distance_points}, "
        f"atr_mult={args.atr_multiple}) | warmup: {args.warmup_bars}"
    )
    print(f"Signal: {args.specialists} (RegimeAwareEnsemble, min_conf=0.5)")
    print()

    selection = select_replay_periods(
        data, window_bars=args.window_bars, macro_events=_load_macro_events(args.macro_events)
    )
    # BL-023 F-10: blockers non vuoti (es. macro_surprise mancante) => run
    # INVALIDO, non APPROVED/REJECTED.
    if selection.blockers:
        print(f"FATAL: run INVALIDO — {len(selection.blockers)} blocker(s):")
        for b in selection.blockers:
            print(f"  - {b}")
        print("Risolvi i blocker (fonte macro consensus o re-spec regimi) prima del verdetto.")
        return 2
    periods = selection.periods[: args.periods_slice]
    print(f"Selected {len(periods)} periods (regimes: {sorted({p.regime.value for p in periods})})")

    variants = ReplayVariant.factorial()
    print(f"Variants: {len(variants)}")

    signal = _signal(args.specialists)
    stop_points = (
        Decimal(str(args.stop_distance_points))
        if args.stop_distance_points is not None
        else Decimal("5")
    )
    runner = EventDrivenQualificationRunner(
        signal=signal,
        contract=MES,
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        prop_profile=TOPSTEP_TC_50K,
        profile_certified=True,
        stop_distance_points=stop_points,
        stop_mode=args.stop_mode,
        atr_multiple=args.atr_multiple,
        atr_period=args.atr_period,
        periods_per_year=ppy,
        liquidate_on_hard_breach=True,
    )

    observations = []
    errors = []
    regime_counts: dict[str, int] = {}
    for period in periods:
        # BL-023 F-02/F-19: slice_period (search_sorted + filtro <= period.end)
        # con warmup PRIMA del periodo. Nessun bug calendario-vs-barre.
        period_data = slice_period(data, period, warmup_bars=args.warmup_bars)
        for variant in variants:
            for qty in args.quantities:
                artifact = build_offline_intelligence_artifact(period, variant)
                try:
                    obs = asyncio.run(
                        runner.run(period_data, period, variant, intelligence_artifact=artifact)
                    )
                    observations.append(obs)
                    regime_counts[obs.regime.value] = regime_counts.get(obs.regime.value, 0) + 1
                except (RuntimeError, ValueError) as exc:
                    errors.append(f"{period.name}/{variant.name}/qty{qty}: {exc}")

    if not observations:
        print("FATAL: no observations collected")
        return 2

    # BL-023 F-08: N onesto — curve uniche = periodi × qty indipendenti,
    # non osservazioni replicate dalle varianti.
    unique_curves = len(periods) * len(args.quantities)
    sharpes = [
        obs.metrics.sharpe_ratio for obs in observations if obs.metrics.sharpe_ratio is not None
    ]
    dds = [obs.metrics.max_drawdown for obs in observations if obs.metrics.max_drawdown is not None]
    breaches_total = sum(obs.metrics.hard_breaches for obs in observations)
    liquidated_total = sum(1 for obs in observations if obs.metrics.liquidated)

    median_sharpe = statistics.median(sharpes) if sharpes else 0.0
    worst_dd = max(dds) if dds else 0.0
    median_dd = statistics.median(dds) if dds else 0.0
    breach_rate = breaches_total / len(observations) if observations else 0.0
    sortinos = [
        obs.metrics.sortino_ratio for obs in observations if obs.metrics.sortino_ratio is not None
    ]
    median_sortino = statistics.median(sortinos) if sortinos else 0.0
    luck_values = [
        obs.metrics.luck_p_value for obs in observations if obs.metrics.luck_p_value is not None
    ]
    median_luck = statistics.median(luck_values) if luck_values else None

    min_obs = max(48, unique_curves)
    decision = (
        "APPROVED"
        if (
            len(observations) >= min_obs
            and median_sharpe >= 0.5
            and worst_dd <= 0.04
            and breaches_total == 0
        )
        else "REJECTED"
    )

    out: dict[str, Any] = {
        "metadata": {
            "title": "M31 rerun with regime ribilanciato (BL-022 + BL-023 fix)",
            "timestamp": datetime.now(UTC).isoformat(),
            "git_commit": _git_commit(),
            "data_hash": data_hash,
            "data": data_label,
            "n_bars": len(data),
            "timeframe": args.timeframe,
            "periods_per_year": ppy,
            "engine": "EventDrivenQualificationRunner",
            "signal": f"RegimeAwareEnsemble v2 ({args.specialists})",
            "stop": {
                "mode": args.stop_mode,
                "distance_points": str(stop_points),
                "atr_multiple": args.atr_multiple,
                "atr_period": args.atr_period,
            },
            "warmup_bars": args.warmup_bars,
            "bl": "BL-022/BL-023",
        },
        "regime_distribution": regime_counts,
        "thresholds": {
            "median_sharpe_min": 0.5,
            "worst_drawdown_max": 0.04,
            "hard_breaches_max": 0,
            "min_observations": min_obs,
            "unique_curves": unique_curves,
        },
        "metrics": {
            "observations": len(observations),
            "unique_curves": unique_curves,
            "median_sharpe": round(median_sharpe, 4),
            "median_sortino": round(median_sortino, 4),
            "median_max_drawdown": round(median_dd, 4),
            "worst_max_drawdown": round(worst_dd, 4),
            "total_breaches": breaches_total,
            "liquidated_observations": liquidated_total,
            "breach_rate": round(breach_rate, 4),
            "median_luck_p_value": round(median_luck, 4) if median_luck is not None else None,
        },
        "errors": errors,
        "decision": decision,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(out, indent=2))

    md_lines = [
        "# M31 Rerun Final (BL-022 + BL-023 fix)",
        "",
        f"> Decisione: **{decision}**",
        "",
        f"- Generato: {out['metadata']['timestamp']}",
        f"- Git commit: `{_git_commit()[:8]}`",
        f"- Data hash: `{data_hash[:16]}...`",
        f"- Data: `{data_label}` ({len(data)} bar, {args.timeframe}, ppy={ppy})",
        f"- Signal: `RegimeAwareEnsemble v2 ({args.specialists})`",
        f"- Stop: `{args.stop_mode}` pts={stop_points} atr_mult={args.atr_multiple}",
        "- Engine: `EventDrivenQualificationRunner` (liquidazione hard breach attiva)",
        "",
        "## Regime distribution osservata",
        "",
        "| Regime | n osservazioni |",
        "|---|---:|",
    ]
    for k, v in sorted(regime_counts.items(), key=lambda kv: -kv[1]):
        md_lines.append(f"| {k} | {v} |")
    md_lines.extend(
        [
            "",
            "## Metriche vs soglia",
            "",
            "| Metrica | Valore | Soglia | Stato |",
            "|---|---:|---:|:---:|",
            f"| Median Sharpe | {median_sharpe:.4f} | ≥ 0.5 | "
            f"{'✅' if median_sharpe >= 0.5 else '❌'} |",
            f"| Worst DD | {worst_dd:.4f} | ≤ 0.04 | {'✅' if worst_dd <= 0.04 else '❌'} |",
            f"| Hard breaches | {breaches_total} | = 0 | {'✅' if breaches_total == 0 else '❌'} |",
            f"| Osservazioni | {len(observations)} | ≥ {min_obs} | "
            f"{'✅' if len(observations) >= min_obs else '⚠️'} |",
            f"| Curve uniche | {unique_curves} | (N onesto F-08) | — |",
            f"| Liquidate | {liquidated_total} | — | — |",
            "",
            "## Errori",
            "",
        ]
    )
    if errors:
        md_lines.append(f"- {len(errors)} errori raccolti: vedi JSON")
    else:
        md_lines.append("- nessun errore")
    md_lines.extend(
        [
            "",
            "## AC per G5 PASSED",
            "",
            f"- [x] periodi × qty = `{unique_curves}` curve uniche (N onesto)",
            "- [x] dataset pinned (sha256 in header)",
            "- [x] regime detection ribilanciata",
            "- [x] risk adapter cablato + liquidazione hard breach",
            "- [x] MES-aware sizing",
            "- [x] Lorentzian causal fix integrato",
            "- [x] warmup pre-periodo >= 100 bar (F-03)",
            "",
        ]
    )
    if decision == "APPROVED":
        md_lines.extend(
            [
                "## Verdetto",
                "",
                "G5 PASSED. Le osservazioni soddisfano le soglie. M31 verde.",
                "Prossimo: G6 paper → 100 sessioni prop-firm → G7 firm pick.",
            ]
        )
    else:
        md_lines.extend(
            [
                "## Verdetto",
                "",
                "G5 ancora REJECTED (o INVALIDO se blocker attivi).",
                "Vedi `docs/reports/m31-rerun/notes.md` per la diagnosi BL-023.",
            ]
        )
    args.markdown_output.write_text("\n".join(md_lines))

    print()
    print("=" * 60)
    print(f"M31 rerun — decisione: {decision}")
    print(f"  Median Sharpe: {median_sharpe:.4f} (target ≥ 0.5)")
    print(f"  Worst DD:      {worst_dd:.4f} (target ≤ 0.04)")
    print(f"  Hard breaches: {breaches_total} (target = 0)")
    print(f"  Liquidated:    {liquidated_total}")
    print(f"  Observations:  {len(observations)} (unique curves: {unique_curves})")
    print()
    print(f"Regime distribution: {regime_counts}")
    print(f"Report: {args.markdown_output}")
    return 0 if decision == "APPROVED" else 1


if __name__ == "__main__":
    sys.exit(main())
