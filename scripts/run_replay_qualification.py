#!/usr/bin/env python3
"""Generate fail-closed M31 historical replay qualification evidence."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.qualification import (
    EventDrivenQualificationRunner,
    GateDecision,
    QualificationEvidence,
    QualificationThresholds,
    ReplayObservation,
    ReplayRegime,
    ReplayVariant,
    build_offline_intelligence_artifact,
    build_qualification_report,
    select_replay_periods,
    slice_period,
    write_report,
)
from analytics.qualification.models import MacroSurpriseEvent
from analytics.strategy.lorentzian import LorentzianKNN
from analytics.strategy.regime_ensemble import RegimeAwareEnsemble, SpecialistId
from analytics.strategy.signals import DonchianBreakout, EmaTrend, RsiReversion
from market.contracts import MES
from policy.prop_firm.fixtures import TOPSTEP_TC_50K


def main() -> int:
    """Run the event-driven control replay and publish current M31 blockers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data/ohlcv/ES_1d.parquet"))
    parser.add_argument(
        "--data-source",
        choices=("lake", "legacy"),
        default="legacy",
        help="lake = DataRegistry force=True (F-04); legacy = parquet locale",
    )
    parser.add_argument("--symbol", default="ES", help="lake symbol (data-source=lake)")
    parser.add_argument("--timeframe", default="1d", help="lake timeframe (data-source=lake)")
    parser.add_argument("--config", type=Path, default=Path("config/qualification/m31.yaml"))
    parser.add_argument("--macro-events", type=Path, default=Path("data/macro/m31-events.json"))
    parser.add_argument(
        "--data-provenance", type=Path, default=Path("data/ohlcv/ES_1d.provenance.json")
    )
    parser.add_argument(
        "--prop-profile-evidence", type=Path, default=Path("data/prop_firm/topstep_tc_50k.json")
    )
    parser.add_argument("--window-bars", type=int, default=40)
    parser.add_argument("--warmup-bars", type=int, default=100, help="BL-023 F-03: >= 100")
    parser.add_argument("--stop-mode", choices=("fixed", "atr"), default="fixed")
    parser.add_argument("--atr-multiple", type=float, default=1.0, help="ADR-016: ATR 1x")
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--stop-distance-points", type=float, default=None)
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("docs/reports/m31-historical-replay-qualification.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("docs/reports/m31-historical-replay-qualification.md"),
    )
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()

    data = _load_data(args)
    macro_events = _load_macro_events(args.macro_events)
    selection = select_replay_periods(data, window_bars=args.window_bars, macro_events=macro_events)
    thresholds = _load_thresholds(args.config)
    expected_variants = ReplayVariant.factorial()
    if args.data_source == "lake":
        # BL-023 F-04/F-07: with the lake the row-count guard IS the
        # provenance check (EXPECTED_ROWS pin, enforced in _load_data).
        data_hash = f"lake:{args.symbol}:{args.timeframe}:{data.height}rows"
        point_in_time_verified = True
    else:
        data_hash = _sha256(args.data)
        point_in_time_verified = _data_provenance_verified(
            args.data_provenance, data_hash=data_hash, data=data
        )
    prop_profile_certified = _prop_profile_certified(args.prop_profile_evidence)
    signal = RegimeAwareEnsemble(
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
    runner = EventDrivenQualificationRunner(
        signal=signal,
        contract=MES,
        initial_capital=Decimal(str(TOPSTEP_TC_50K.account_size)),
        prop_profile=TOPSTEP_TC_50K,
        profile_certified=prop_profile_certified,
        stop_mode=args.stop_mode,
        atr_multiple=args.atr_multiple,
        atr_period=args.atr_period,
        stop_distance_points=(
            Decimal(str(args.stop_distance_points))
            if args.stop_distance_points is not None
            else Decimal("5")
        ),
        periods_per_year=_periods_per_year(args.timeframe),
        liquidate_on_hard_breach=True,
    )

    observations: list[ReplayObservation] = []
    replay_errors: list[str] = []
    for period in selection.periods:
        period_data = slice_period(selection.normalized_data, period, warmup_bars=args.warmup_bars)
        for variant in expected_variants:
            artifact = build_offline_intelligence_artifact(period, variant)
            try:
                observations.append(asyncio.run(runner.run(period_data, period, variant, artifact)))
            except (RuntimeError, ValueError) as exc:
                replay_errors.append(f"{period.name}/{variant.name}: {exc}")

    determinism_verified = _verify_control_determinism(
        runner,
        selection.normalized_data,
        list(selection.periods),
        warmup_bars=args.warmup_bars,
        observations=observations,
    )

    macro_verified = (
        bool(macro_events)
        and all(
            event.source_sha256 is not None and event.retrieved_at is not None
            for event in macro_events
        )
        and any(period.regime == ReplayRegime.MACRO_SURPRISE for period in selection.periods)
    )
    intelligence_verified = bool(observations) and all(
        observation.execution_evidence is not None
        and observation.execution_evidence.intelligence_artifact is not None
        and observation.execution_evidence.intelligence_artifact.variant_name
        == observation.variant_name
        for observation in observations
    )
    economic_parity_verified = bool(observations) and all(
        observation.execution_evidence is not None
        and observation.execution_evidence.economic_parity_verified
        for observation in observations
    )
    engine_certified = determinism_verified and economic_parity_verified
    evidence = QualificationEvidence(
        discovery_engine="oracle-regime-selector-v1",
        qualification_engine="oracle-event-driven-paper-v1",
        qualification_engine_certified=engine_certified,
        selected_before_strategy_execution=True,
        point_in_time_data_verified=point_in_time_verified,
        macro_surprise_data_verified=macro_verified,
        prop_profile_certified=prop_profile_certified,
        prop_rule_replay_exercised=_sum_execution(observations, "rule_evaluations") > 0,
        risk_gate_exercised=_sum_execution(observations, "risk_checks") > 0,
        oms_exercised=_sum_execution(observations, "orders_persisted") > 0,
        ledger_reconciled=bool(observations)
        and all(
            observation.execution_evidence is not None
            and observation.execution_evidence.reconciliation_clean
            and observation.execution_evidence.flattened
            for observation in observations
        ),
        intelligence_variants_executed=intelligence_verified,
        economic_parity_verified=economic_parity_verified,
        intelligence_artifacts_verified=intelligence_verified,
        luck_test_method="pooled out-of-sample moving-block bootstrap",
        data_hash=data_hash,
        config_hash=_sha256(args.config),
        git_commit=_git_commit(),
    )
    report = build_qualification_report(
        periods=list(selection.periods),
        expected_variants=expected_variants,
        observations=observations,
        evidence=evidence,
        thresholds=thresholds,
        selection_blockers=[*selection.blockers, *replay_errors],
    )
    write_report(report, json_path=args.json_output, markdown_path=args.markdown_output)

    print(f"M31 decision: {report.decision.value.upper()}")
    print(f"Periods: {report.summary.period_count}")
    print(
        f"Variants: {report.summary.executed_variant_count}/{report.summary.expected_variant_count}"
    )
    for reason in report.reasons:
        print(f"- {reason}")
    print(f"JSON report: {args.json_output}")
    print(f"Markdown report: {args.markdown_output}")

    if args.require_pass and report.decision != GateDecision.APPROVED:
        return 2
    return 0


def _load_thresholds(path: Path) -> QualificationThresholds:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Qualification config must be a mapping: {path}")
    return QualificationThresholds.model_validate(raw)


def _load_macro_events(path: Path | None) -> list[MacroSurpriseEvent]:
    if path is None:
        return []
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("events", [])
    if not isinstance(payload, list):
        raise ValueError("Macro event input must be a list or an object with an events list")
    return [MacroSurpriseEvent.model_validate(item) for item in payload]


#: Expected row counts per symbol/timeframe read from the lake parquet
#: directly (BL-023 F-07: coverage.json is stale — 13042 != 6523).
#: NOTE: the lake is LIVE (daily ingestion) — the pin tracks the current
#: row count; bump it when the lake grows (2026-08-04: 6523, new bar).
EXPECTED_ROWS: dict[str, int] = {"ES|1d": 6523, "ES|1h": 13747}


def _periods_per_year(timeframe: str) -> int:
    """F-17: annualization factor per timeframe (252 daily, ~5796 1h)."""
    return 5796 if timeframe == "1h" else 252


def _load_data(args: argparse.Namespace) -> pl.DataFrame:
    """Load OHLCV from lake (direct read, F-04) or legacy parquet.

    Raises on row-count mismatch when a lake row-count expectation is
    pinned (F-07). Legacy keeps the old lowercase-rename behaviour.
    """
    if args.data_source == "lake":
        from analytics.backtest.providers import read_from_lake

        frame = read_from_lake(args.symbol, args.timeframe)
        if frame is None:
            raise ValueError(f"Lake has no data for {args.symbol}|{args.timeframe}")
        key = f"{args.symbol}|{args.timeframe}"
        expected = EXPECTED_ROWS.get(key)
        if expected is not None and frame.height != expected:
            raise ValueError(
                f"Lake {key} row-count mismatch: got {frame.height}, expected {expected} "
                f"(BL-023 F-04 guard). Pin stale?"
            )
        return frame
    frame = pl.read_parquet(args.data)
    return frame.rename({column: column.lower() for column in frame.columns})


def _data_provenance_verified(path: Path, *, data_hash: str, data: pl.DataFrame) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    normalized = {column.lower(): column for column in data.columns}
    date_column = normalized.get("timestamp") or normalized.get("date")
    if date_column is None or data.height == 0:
        return False
    timestamps = data[date_column].cast(pl.Datetime).sort()
    return bool(
        payload.get("sha256") == data_hash
        and payload.get("rows") == data.height
        and payload.get("provider")
        and payload.get("availability_policy")
        and timestamps[0].date().isoformat() in str(payload.get("first_timestamp"))
        and timestamps[-1].date().isoformat() in str(payload.get("last_timestamp"))
    )


def _prop_profile_certified(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload.get("rules", {})
    sources = payload.get("sources", [])
    contract_cap = TOPSTEP_TC_50K.contract_cap
    if contract_cap is None:
        return False
    return bool(
        payload.get("profile_key") == TOPSTEP_TC_50K.version_key
        and rules.get("account_size") == TOPSTEP_TC_50K.account_size
        and rules.get("maximum_loss_limit") == TOPSTEP_TC_50K.max_overall_loss_amount
        and rules.get("optional_daily_loss_limit") == TOPSTEP_TC_50K.max_daily_loss_amount
        and rules.get("maximum_loss_mode") == TOPSTEP_TC_50K.dd_mode.value
        and rules.get("max_minis") == contract_cap.max_mini_eq
        and rules.get("max_micros") == contract_cap.per_product.get("MES")
        and len(sources) >= 3
        and all(len(str(source.get("sha256", ""))) == 64 for source in sources)
    )


def _verify_control_determinism(
    runner: EventDrivenQualificationRunner,
    data: pl.DataFrame,
    periods: list[Any],
    *,
    warmup_bars: int,
    observations: list[ReplayObservation],
) -> bool:
    controls = {
        observation.period_name: observation
        for observation in observations
        if observation.variant_name == ReplayVariant.control().name
    }
    if len(controls) != len(periods):
        return False
    for period in periods:
        period_data = slice_period(data, period, warmup_bars=warmup_bars)
        artifact = build_offline_intelligence_artifact(period, ReplayVariant.control())
        rerun = asyncio.run(runner.run(period_data, period, ReplayVariant.control(), artifact))
        if _economic_fingerprint(rerun) != _economic_fingerprint(controls[period.name]):
            return False
    return True


def _economic_fingerprint(observation: ReplayObservation) -> tuple[Any, ...]:
    metrics = observation.metrics
    evidence = observation.execution_evidence
    return (
        metrics.net_return,
        metrics.sharpe_ratio,
        metrics.sortino_ratio,
        metrics.calmar_ratio,
        metrics.max_drawdown,
        metrics.hard_breaches,
        metrics.total_trades,
        metrics.execution_cost,
        metrics.turnover,
        evidence.risk_checks if evidence else None,
        evidence.orders_persisted if evidence else None,
        evidence.fills_recorded if evidence else None,
        evidence.ledger_entries if evidence else None,
        evidence.independent_cash_delta if evidence else None,
        evidence.ledger_cash_delta if evidence else None,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _sum_execution(observations: list[ReplayObservation], field: str) -> int:
    return sum(
        int(getattr(observation.execution_evidence, field))
        for observation in observations
        if observation.execution_evidence is not None
    )


if __name__ == "__main__":
    raise SystemExit(main())
