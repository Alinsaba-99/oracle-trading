"""BL-OPC-12 — Qualificazione Lane B composite via ADR-017 (DSR/PBO/CPCV).

Qualifies the Lane B composite edge (Sharpe 0.93, alpha +59% vs SPY,
`docs/reports/lane-b-composite/2026-08-17-compare.md`) against the
ADR-017 overfitting gauntlet before it can be promoted research → paper
(BL-OPC-7):

* **DSR ≥ 0.95** with an honest ``n_trials`` (number of variants
  actually explored in the discovery sweep — under-reporting it
  re-opens the overfitting hole the gate exists to close);
* **PSR ≥ 0.95**;
* **PBO < 0.5** across the competing config family;
* **CPCV** honest OOS Sharpe distribution;
* the **2022 bear market** evaluated separately (the edge must not be
  a pure bull-market artifact).

All statistics come from ``analytics/qualification/lane_b.py``
(itself delegating to ``qualification/dsr.py`` purgedcv wrappers and
the canonical metrics of ADR-021). No formula re-derivation here.

Usage:
    uv run --env-file .env python scripts/run_lane_b_qualification.py

Output: report in ``docs/reports/lane-b-composite/`` (JSON + MD) with
the gate verdict registered.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: Discovery sweep the DSR multi-test correction must account for:
#: legacy AND screen, composite default, composite threshold 0.55/0.60/
#: 0.70, composite weights 50/30/20 — every variant ever run on this
#: edge (BL-505b..505d, Opzione C step 3, this script's own family).
#: 8 trials total. Documented, not tuned to pass.
N_TRIALS_DISCOVERY = 8

#: Config family competing for the PBO estimate (equal-length daily
#: return rows over the same 2020→2025 window).
FAMILY_START = datetime(2020, 1, 1)
FAMILY_END = datetime(2025, 8, 14)
#: Bear-market slice evaluated on its own (AC: 2022 separato).
BEAR_START = datetime(2022, 1, 1)
BEAR_END = datetime(2022, 12, 31)


def _configs() -> list[tuple[str, Any]]:
    from analytics.strategy.lane_b_backtester import LaneBBacktestConfig

    return [
        ("composite_default", LaneBBacktestConfig(use_composite=True)),
        ("legacy_and", LaneBBacktestConfig(use_composite=False)),
        (
            "composite_threshold_055",
            LaneBBacktestConfig(use_composite=True, composite_threshold=0.55),
        ),
        (
            "composite_threshold_070",
            LaneBBacktestConfig(use_composite=True, composite_threshold=0.70),
        ),
        (
            "composite_weights_50_30_20",
            LaneBBacktestConfig(use_composite=True, composite_weights=(0.50, 0.30, 0.20)),
        ),
    ]


def _daily_returns_from_equity(equity: np.ndarray) -> np.ndarray:
    """Convert an equity curve to per-bar returns (canonical input)."""
    if equity.size < 2:
        return np.array([])
    return np.asarray(equity[1:] / equity[:-1] - 1.0)


def main() -> int:
    simfin_key = os.environ.get("SIMFIN_API_KEY", "")
    if not simfin_key:
        print("ERROR: SIMFIN_API_KEY not set")
        return 1

    from analytics.fundamental.simfin_loader import SimFinLoader
    from analytics.qualification.lane_b import DSR_MIN, PBO_MAX, PSR_MIN, qualify_lane_b_composite
    from analytics.strategy.lane_b_backtester import LaneBBacktester

    loader = SimFinLoader(api_key=simfin_key)

    print(f"Config family: {len(_configs())} variants, {FAMILY_START.date()} → {FAMILY_END.date()}")
    family_returns: dict[str, np.ndarray] = {}
    summary: dict[str, dict[str, Any]] = {}

    for name, cfg in _configs():
        print(f"\n[{name}] running backtest...")
        backtester = LaneBBacktester(loader, cfg)
        try:
            result = backtester.run(start_date=FAMILY_START, end_date=FAMILY_END)
        except Exception as exc:
            print(f"[{name}] FAIL: {exc}")
            summary[name] = {"error": str(exc)}
            continue
        rets = _daily_returns_from_equity(result.equity_curve)
        family_returns[name] = rets
        summary[name] = {
            "n_rebalances": result.n_rebalances,
            "total_return": result.total_return,
            "annual_return": result.annual_return,
            "sharpe": result.sharpe,
            "max_drawdown": result.max_drawdown,
            "n_bars": int(result.equity_curve.size),
        }
        print(
            f"[{name}] sharpe={result.sharpe}, total={result.total_return:.4%}, "
            f"dd={result.max_drawdown:.4%}, bars={result.equity_curve.size}"
        )

    primary = family_returns.get("composite_default")
    if primary is None or primary.size < 60:
        print("FATAL: composite_default backtest did not produce a usable return series")
        return 2

    # Align the matrix rows (PBO needs equal lengths — truncate to the
    # shortest row; honest: shorter variants simply contribute less).
    min_len = min(r.size for r in family_returns.values()) if family_returns else 0
    matrix = np.asarray([r[:min_len] for r in family_returns.values()]) if min_len >= 60 else None

    print("\nRunning ADR-017 gauntlet (DSR/PSR/PBO/CPCV)...")
    qualification = qualify_lane_b_composite(
        primary, n_trials=N_TRIALS_DISCOVERY, periods_per_year=252, returns_matrix=matrix
    )

    # 2022 bear market, evaluated on its own window.
    print(f"\nBear window {BEAR_START.date()} → {BEAR_END.date()}...")
    bear_report: dict[str, Any] | None = None
    try:
        bear_result = LaneBBacktester(loader, _configs()[0][1]).run(
            start_date=BEAR_START, end_date=BEAR_END
        )
        bear_rets = _daily_returns_from_equity(bear_result.equity_curve)
        if bear_rets.size >= 60:
            bear_qual = qualify_lane_b_composite(
                bear_rets, n_trials=N_TRIALS_DISCOVERY, periods_per_year=252
            )
            bear_report = {
                "n_bars": int(bear_result.equity_curve.size),
                "sharpe": bear_result.sharpe,
                "max_drawdown": bear_result.max_drawdown,
                "dsr": bear_qual.deflated_sharpe_ratio,
                "psr": bear_qual.probabilistic_sharpe_ratio,
                "cpcv_oos_median": bear_qual.cpcv_oos_sharpe_median,
                "verdict": bear_qual.verdict,
            }
        else:
            bear_report = {
                "n_bars": int(bear_result.equity_curve.size),
                "verdict": "INSUFFICIENT_DATA",
            }
        print(f"[bear] {bear_report}")
    except Exception as exc:
        bear_report = {"error": str(exc)}
        print(f"[bear] FAIL: {exc}")

    out: dict[str, Any] = {
        "metadata": {
            "task": "BL-OPC-12 — Lane B composite ADR-017 qualification",
            "generated": datetime.now(UTC).isoformat(),
            "window": f"{FAMILY_START.date()} → {FAMILY_END.date()}",
            "bear_window": f"{BEAR_START.date()} → {BEAR_END.date()}",
            "n_trials": N_TRIALS_DISCOVERY,
            "gates": {"dsr_min": DSR_MIN, "psr_min": PSR_MIN, "pbo_max": PBO_MAX},
            "family": sorted(family_returns.keys()),
        },
        "family_summary": summary,
        "qualification": {
            "verdict": qualification.verdict,
            "observed_sharpe": qualification.observed_sharpe,
            "deflated_sharpe_ratio": qualification.deflated_sharpe_ratio,
            "probabilistic_sharpe_ratio": qualification.probabilistic_sharpe_ratio,
            "pbo": qualification.pbo,
            "cpcv_oos_sharpe_median": qualification.cpcv_oos_sharpe_median,
            "reasons": qualification.reasons,
        },
        "bear_2022": bear_report,
    }

    out_dir = ROOT / "docs" / "reports" / "lane-b-composite"
    out_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now(UTC).strftime("%Y-%m-%d")
    json_path = out_dir / f"{date_tag}-qualification.json"
    md_path = out_dir / f"{date_tag}-qualification.md"
    json_path.write_text(json.dumps(out, indent=2, default=str))

    qual = out["qualification"]
    bear = bear_report or {}
    md = [
        "# Lane B Composite — Qualificazione ADR-017 (BL-OPC-12)\n\n",
        f"**Generated**: {out['metadata']['generated']}\n",
        f"**Window**: {out['metadata']['window']} (bear: {out['metadata']['bear_window']})\n",
        f"**n_trials (discovery sweep)**: {N_TRIALS_DISCOVERY} — documentato nello script\n\n",
        f"## Verdetto: **{qual['verdict']}**\n\n",
        "| Gate | Valore | Soglia | Stato |\n|---|---|---|:---:|\n",
        f"| Observed Sharpe (canonical) | {qual['observed_sharpe']:.4f} | — | — |\n",
        f"| DSR | {qual['deflated_sharpe_ratio']} | ≥ {DSR_MIN} | "
        f"{'✅' if (qual['deflated_sharpe_ratio'] or 0) >= DSR_MIN else '❌'} |\n",
        f"| PSR | {qual['probabilistic_sharpe_ratio']} | ≥ {PSR_MIN} | "
        f"{'✅' if (qual['probabilistic_sharpe_ratio'] or 0) >= PSR_MIN else '❌'} |\n",
        f"| PBO | {qual['pbo']} | < {PBO_MAX} | "
        f"{'✅' if (qual['pbo'] is None or qual['pbo'] < PBO_MAX) else '❌'} |\n",
        f"| CPCV OOS Sharpe median | {qual['cpcv_oos_sharpe_median']} | — | — |\n\n",
    ]
    if qual["reasons"]:
        md.append("## Motivi del rigetto\n\n")
        for reason in qual["reasons"]:
            md.append(f"- {reason}\n")
        md.append("\n")
    md.append("## Bear market 2022 (separato)\n\n")
    md.append(f"```\n{json.dumps(bear, indent=2, default=str)}\n```\n\n")
    md.append("## Family summary\n\n")
    md.append("| Config | Sharpe | Total return | MaxDD |\n|---|---|---|---|\n")
    for name, row in summary.items():
        if "error" in row:
            md.append(f"| {name} | ERROR | {row['error']} | — |\n")
        else:
            md.append(
                f"| {name} | {row['sharpe']} | {row['total_return']:.4%} | "
                f"{row['max_drawdown']:.4%} |\n"
            )
    md_path.write_text("".join(md))

    print(f"\n{'=' * 60}")
    print(f"BL-OPC-12 verdict: {qualification.verdict}")
    print(f"  Observed Sharpe: {qualification.observed_sharpe:.4f}")
    print(f"  DSR: {qualification.deflated_sharpe_ratio} (≥ {DSR_MIN})")
    print(f"  PSR: {qualification.probabilistic_sharpe_ratio} (≥ {PSR_MIN})")
    print(f"  PBO: {qualification.pbo} (< {PBO_MAX})")
    print(f"  CPCV OOS median: {qualification.cpcv_oos_sharpe_median}")
    print(f"  Report: {md_path}")
    return 0 if qualification.verdict == "APPROVED" else 1


if __name__ == "__main__":
    sys.exit(main())
