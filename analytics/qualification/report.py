"""JSON and Markdown report rendering for M31."""

from __future__ import annotations

from pathlib import Path

from analytics.qualification.models import QualificationReport


def write_report(report: QualificationReport, *, json_path: Path, markdown_path: Path) -> None:
    """Persist machine-readable and human-readable M31 evidence."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: QualificationReport) -> str:
    """Render a concise, reviewable qualification report."""
    evidence = report.evidence
    summary = report.summary
    lines = [
        "# M31 — Historical Replay Qualification",
        "",
        f"> Decisione: **{report.decision.value.upper()}**",
        "> Questo report non autorizza evaluation, live o funded trading.",
        "",
        "## Identità",
        "",
        f"- Generato: `{report.generated_at.isoformat()}`",
        f"- Git commit: `{evidence.git_commit}`",
        f"- Data hash: `{evidence.data_hash}`",
        f"- Config hash: `{evidence.config_hash}`",
        f"- Discovery engine: `{evidence.discovery_engine}`",
        f"- Qualification engine: `{evidence.qualification_engine or 'not-configured'}`",
        f"- Segnale: `{evidence.signal_name}`",
        "",
        "## Decisione",
        "",
    ]
    lines.extend(f"- {reason}" for reason in report.reasons)
    lines.extend(["", "## Evidenza", "", "| Controllo | Stato |", "|---|:---:|"])
    evidence_rows = (
        ("Periodi selezionati prima dell'esecuzione", evidence.selected_before_strategy_execution),
        ("Dati point-in-time verificati", evidence.point_in_time_data_verified),
        ("Macro surprise verificata", evidence.macro_surprise_data_verified),
        ("Profilo regole prop certificato", evidence.prop_profile_certified),
        ("Motore event-driven certificato", evidence.qualification_engine_certified),
        ("Replay regole prop-firm", evidence.prop_rule_replay_exercised),
        ("Risk gate obbligatorio esercitato", evidence.risk_gate_exercised),
        ("OMS autorevole esercitato", evidence.oms_exercised),
        ("Ledger riconciliato", evidence.ledger_reconciled),
        ("Matrice intelligence completa", evidence.intelligence_variants_executed),
        ("Artefatti intelligence verificati", evidence.intelligence_artifacts_verified),
        ("Parità economica verificata", evidence.economic_parity_verified),
    )
    lines.extend(f"| {label} | {_status(value)} |" for label, value in evidence_rows)
    lines.extend(
        [
            "",
            "## Sintesi",
            "",
            "| Metrica | Valore |",
            "|---|---:|",
            f"| Periodi | {summary.period_count} |",
            (
                f"| Varianti eseguite | {summary.executed_variant_count}/"
                f"{summary.expected_variant_count} |"
            ),
            f"| Osservazioni | {summary.observation_count} |",
            f"| Median net return | {_number(summary.median_net_return, percent=True)} |",
            f"| Median Sharpe | {_number(summary.median_sharpe)} |",
            f"| Median Sortino | {_number(summary.median_sortino)} |",
            f"| Median Calmar | {_number(summary.median_calmar)} |",
            f"| Worst drawdown | {_number(summary.worst_drawdown, percent=True)} |",
            f"| Hard breaches | {summary.hard_breaches} |",
            (
                "| Median execution cost ratio | "
                f"{_number(summary.median_execution_cost_ratio, percent=True)} |"
            ),
            f"| Worst luck p-value | {_number(summary.worst_luck_p_value)} |",
            f"| Pooled luck p-value | {_number(summary.pooled_luck_p_value)} |",
            f"| Luck test | {evidence.luck_test_method} |",
            (
                "| Worst decision latency p95 | "
                f"{_number(summary.worst_decision_latency_ms_p95, suffix=' ms')} |"
            ),
            f"| Risk checks | {summary.risk_checks} |",
            f"| Rule evaluations | {summary.rule_evaluations} |",
            f"| Ordini OMS | {summary.orders_persisted} |",
            f"| Fill registrati | {summary.fills_recorded} |",
            f"| Ledger entries | {summary.ledger_entries} |",
            f"| Reconciliation | {summary.reconciliation_runs} |",
            f"| Mismatch | {summary.reconciliation_mismatches} |",
            f"| Slice non flat | {summary.unflattened_slices} |",
            "",
            "## Periodi",
            "",
            "| Regime | Inizio | Fine | Selezione | Score |",
            "|---|---|---|---|---:|",
        ]
    )
    for period in report.periods:
        lines.append(
            f"| {period.regime.value} | {period.start.date()} | {period.end.date()} | "
            f"{period.selection_metric} | {period.selection_score:.6g} |"
        )

    lines.extend(
        [
            "",
            "## Osservazioni",
            "",
            (
                "| Periodo | Variante | Engine | Return | Sharpe | Max DD | Hard | "
                "Risk | Ordini | Fill | Recon |"
            ),
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
        ]
    )
    for observation in report.observations:
        metrics = observation.metrics
        execution = observation.execution_evidence
        lines.append(
            f"| {observation.period_name} | {observation.variant_name} | "
            f"{observation.engine} | {_number(metrics.net_return, percent=True)} | "
            f"{_number(metrics.sharpe_ratio)} | {_number(metrics.max_drawdown, percent=True)} | "
            f"{metrics.hard_breaches} | "
            f"{execution.risk_checks if execution else 0} | "
            f"{execution.orders_persisted if execution else 0} | "
            f"{execution.fills_recorded if execution else 0} | "
            f"{_status(execution.reconciliation_clean) if execution else 'n/a'} |"
        )

    limitations = list(
        dict.fromkeys(
            warning for observation in report.observations for warning in observation.warnings
        )
    )
    if limitations:
        lines.extend(["", "## Limitazioni dichiarate", ""])
        lines.extend(f"- {limitation}" for limitation in limitations)

    stop_condition = (
        "M31 è conclusa: tutte le evidenze obbligatorie sono vere, la matrice 2x2x2 "
        "è completa e ogni soglia versionata è rispettata."
        if report.decision.value == "approved"
        else "M31 resta aperta finché tutte le evidenze obbligatorie sono vere, la matrice "
        "2x2x2 è completa e ogni soglia versionata è rispettata."
    )
    lines.extend(["", "## Stop condition", "", stop_condition, ""])
    return "\n".join(lines)


def _status(value: bool) -> str:
    return "PASS" if value else "MISSING"


def _number(value: float | None, *, percent: bool = False, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    if percent:
        return f"{value:.2%}{suffix}"
    return f"{value:.4f}{suffix}"
