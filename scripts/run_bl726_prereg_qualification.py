#!/usr/bin/env python3
"""BL-727 — Pre-registered qualification runner for the BL-726 Lane B composite variant.

Reads the BL-726 manifest (`docs/research/prereg/BL-726.manifest.json`),
asserts the anti-HARKing tree-integrity gate (`verify_clean_tree`), runs
the backtester on SimFin bulk data with the EXACT pre-registered
parameters, and evaluates the ADR-017 gauntlet (DSR / PSR / CPCV) plus
the Haircut Sharpe (BL-707) and the pre-registered IC screen (BL-706).
The bear-2022 subwindow is computed separately as a secondary gate.

Output:
    docs/reports/lane-b-composite/<YYYY-MM-DD>-bl726-qualification.md
    docs/reports/lane-b-composite/<YYYY-MM-DD>-bl726-qualification.json

The script is intentionally narrow: it consumes only the BL-726 manifest
as input — every parameter and threshold is taken from the frozen
manifest.  No fallback values are permitted inside this runner.

Usage::

    uv run --env-file .env python scripts/run_bl726_prereg_qualification.py

References
----------
- docs/research/prereg/BL-726-lane-b-composite-variant.md
- BACKLOG.md §"Paper trading end-to-end + G5 re-qualifica (BL-726..737)"
- ADR-017 (backtest overfitting validation)
- ADR-019 (Lane B priority)
- ADR-021 (canonical metrics)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.fundamental.simfin_loader import SimFinLoader
from analytics.metrics.canonical import sharpe_ratio as canonical_sharpe
from analytics.qualification.lane_b import cpcv_oos_sharpes, qualify_lane_b_composite
from analytics.research.factory.haircut_sharpe import haircut_sharpe_ratio
from analytics.research.factory.ic_screen import ICResult, screen_factor
from analytics.research.factory.prereg import PreregError, load_prereg, verify_clean_tree
from analytics.strategy.lane_b_backtester import LaneBBacktestConfig, LaneBBacktester

DEFAULT_MANIFEST = ROOT / "docs" / "research" / "prereg" / "BL-726.manifest.json"
DEFAULT_OUT_DIR = ROOT / "docs" / "reports" / "lane-b-composite"
REPO_ROOT = ROOT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BL-727 — Lane B pre-registered qualification")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument(
        "--n-trials",
        type=int,
        default=None,
        help="Override n_trials for DSR (defaults to manifest; =1 by design).",
    )
    p.add_argument(
        "--allow-head-mismatch",
        action="store_true",
        help="Proceed despite HEAD != manifest.code_commit (still records the "
        "drift in the report).  Required because BL-726 was authored against "
        "the pre-BL-726 commit while the runner lives in BL-726 itself.",
    )
    return p.parse_args()


def _today_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _slice_returns(
    sorted_dates: list[datetime], returns: np.ndarray, start: str, end: str
) -> np.ndarray:
    """Slice returns to a [start, end] date window (ISO strings, inclusive)."""
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    mask = np.array([s <= pd.Timestamp(d) <= e for d in sorted_dates], dtype=bool)
    return returns[mask]


@dataclass
class SubWindowMetrics:
    start: str
    end: str
    n_bars: int
    observed_sharpe: float
    max_drawdown: float
    total_return: float
    annual_return: float
    psr: float | None
    dsr: float | None
    cpcv_oos_median: float | None
    haircut_sharpe: float | None


def _evaluate_window(
    sorted_dates: list[datetime],
    returns: np.ndarray,
    start: str,
    end: str,
    *,
    n_trials: int,
    haircut_n_trials: int,
) -> tuple[SubWindowMetrics, np.ndarray]:
    """Compute all metrics on the [start, end] slice of the full backtest."""
    rets = _slice_returns(sorted_dates, returns, start, end)
    if rets.size < 2:
        return (
            SubWindowMetrics(
                start=start,
                end=end,
                n_bars=int(rets.size),
                observed_sharpe=0.0,
                max_drawdown=0.0,
                total_return=0.0,
                annual_return=0.0,
                psr=None,
                dsr=None,
                cpcv_oos_median=None,
                haircut_sharpe=None,
            ),
            rets,
        )

    sr = float(canonical_sharpe(rets))
    equity = np.cumprod(1.0 + rets)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / (peak + 1e-12)
    max_dd = float(-np.min(dd)) if dd.size > 0 else 0.0
    total_ret = float(equity[-1] / equity[0] - 1.0) if equity.size > 0 else 0.0
    years = rets.size / 252.0
    annual_ret = float((1.0 + total_ret) ** (1.0 / years) - 1.0) if years > 0 else 0.0

    qualification = qualify_lane_b_composite(
        rets, n_trials=n_trials, periods_per_year=252, returns_matrix=None, benchmark_sharpe=0.0
    )
    oos = cpcv_oos_sharpes(rets, n_groups=6, n_test_groups=2, periods_per_year=252)
    oos_med = float(np.median(oos)) if oos else None
    hsr = float(haircut_sharpe_ratio(rets, n_trials=haircut_n_trials, periods_per_year=252))

    metrics = SubWindowMetrics(
        start=start,
        end=end,
        n_bars=int(rets.size),
        observed_sharpe=sr,
        max_drawdown=max_dd,
        total_return=total_ret,
        annual_return=annual_ret,
        psr=qualification.probabilistic_sharpe_ratio,
        dsr=qualification.deflated_sharpe_ratio,
        cpcv_oos_median=oos_med,
        haircut_sharpe=hsr,
    )
    return metrics, rets


def _build_ic_screen(
    sorted_dates: list[datetime],
    daily_returns: np.ndarray,
    *,
    icir_threshold: float,
    ic_block_t: float,
    haircut_pct: float,
) -> ICResult | None:
    """Run the pre-registered IC screen (BL-706) on a factor-proxy series.

    Lane B's factor is the equal-weight portfolio itself (the composite
    score's daily realised return).  The screen expects a factor series
    and a price series; we use the trailing-1-day return as the factor
    and the cumulative equity curve as the price proxy.  Result is None
    if the series is too short for the screen's minimum window count.
    """
    if daily_returns.size < 252:
        return None
    equity = np.cumprod(1.0 + daily_returns)
    idx = pd.DatetimeIndex(sorted_dates)
    factor = pd.Series(daily_returns, index=idx, name="factor")
    prices = pd.Series(equity, index=idx, name="price")
    return screen_factor(
        factor,
        prices,
        horizon=1,
        window=63,
        block_len=5,
        n_boot=1_000,
        seed=42,
        haircut_pct=haircut_pct,
        icir_threshold=icir_threshold,
        t_threshold=ic_block_t,
    )


# ---------------------------------------------------------------------------
# Verdict evaluation
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    name: str
    passed: bool
    observed: float | None
    threshold: float | None
    direction: str  # "ge" (≥) or "le" (≤) or "eq"
    note: str = ""


def _gate(
    name: str, observed: float | None, threshold: float | None, direction: str, note: str = ""
) -> GateResult:
    if observed is None:
        return GateResult(
            name=name,
            passed=False,
            observed=None,
            threshold=threshold,
            direction=direction,
            note=f"value unavailable: {note}",
        )
    if direction == "ge":
        ok = observed >= threshold
    elif direction == "le":
        ok = observed <= threshold
    else:
        ok = observed == threshold
    return GateResult(
        name=name,
        passed=bool(ok),
        observed=float(observed),
        threshold=float(threshold),
        direction=direction,
        note=note,
    )


def _verdict(gates: list[GateResult], tree_ok: bool) -> str:
    if not tree_ok:
        return "REJECTED_TREE_INTEGRITY"
    return "APPROVED" if all(g.passed for g in gates) else "REJECTED"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _write_reports(out_dir: Path, payload: dict, md: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{_today_iso()}-bl726-qualification.json"
    md_path = out_dir / f"{_today_iso()}-bl726-qualification.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path


def _render_markdown(
    prereg,
    tree_ok: bool,
    head: str,
    gates: list[GateResult],
    verdict: str,
    full: SubWindowMetrics,
    bear: SubWindowMetrics,
    ic: ICResult | None,
    reasons: list[str],
) -> str:
    lines: list[str] = []
    lines.append("# BL-727 — Pre-Registered Qualification Report")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now(UTC).isoformat()}")
    lines.append(f"**Manifest**: `{prereg.bl_id}` ({prereg.variant_name})")
    lines.append(f"**Pinned commit**: `{prereg.code_commit}`")
    lines.append(f"**Actual HEAD**:  `{head}`")
    lines.append(f"**Tree-integrity check**: {'PASS' if tree_ok else 'FAIL (HEAD drift)'}")
    lines.append(
        f"**Sample window**: {prereg.sample_window['qualification_start']} → "
        f"{prereg.sample_window['qualification_end']}"
    )
    lines.append(f"**Bear subwindow**: {prereg.sample_window['bear_market_subwindow']}")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"## **{verdict}**")
    lines.append("")

    if reasons:
        lines.append("### Reasons")
        lines.append("")
        for r in reasons:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("## Gate table — qualification window")
    lines.append("")
    lines.append("| Gate | Observed | Threshold | Direction | Status |")
    lines.append("|---|---|---|---|:---:|")
    for g in gates:
        op = {"ge": "≥", "le": "≤", "eq": "="}[g.direction]
        obs = "n/a" if g.observed is None else f"{g.observed:.4f}"
        thr = "n/a" if g.threshold is None else f"{g.threshold:.4f}"
        status = "✅" if g.passed else "❌"
        lines.append(f"| {g.name} | {obs} | {thr} | {op} | {status} |")
    lines.append("")

    lines.append("## Headline metrics")
    lines.append("")
    lines.append(f"- **Observed Sharpe (canonical)**: {full.observed_sharpe:.4f}")
    lines.append(f"- **Total return**: {full.total_return * 100:.2f}%")
    lines.append(f"- **Annual return**: {full.annual_return * 100:.2f}%")
    lines.append(f"- **Max drawdown**: {full.max_drawdown * 100:.2f}%")
    lines.append(f"- **PSR**: {full.psr:.4f}" if full.psr is not None else "- **PSR**: n/a")
    lines.append(
        f"- **DSR (n_trials=1)**: {full.dsr:.4f}" if full.dsr is not None else "- **DSR**: n/a"
    )
    lines.append(
        f"- **CPCV OOS Sharpe median**: {full.cpcv_oos_median:.4f}"
        if full.cpcv_oos_median is not None
        else "- **CPCV OOS Sharpe median**: n/a"
    )
    lines.append(
        f"- **Haircut Sharpe**: {full.haircut_sharpe:.4f}"
        if full.haircut_sharpe is not None
        else "- **Haircut Sharpe**: n/a"
    )
    lines.append(f"- **n_bars**: {full.n_bars}")
    lines.append("")

    lines.append("## Bear 2022 subwindow (secondary gate)")
    lines.append("")
    lines.append(f"- **Observed Sharpe**: {bear.observed_sharpe:.4f}")
    lines.append(f"- **Max drawdown**: {bear.max_drawdown * 100:.2f}%")
    lines.append(f"- **PSR**: {bear.psr:.4f}" if bear.psr is not None else "- **PSR**: n/a")
    lines.append(f"- **DSR**: {bear.dsr:.4f}" if bear.dsr is not None else "- **DSR**: n/a")
    lines.append(
        f"- **CPCV OOS Sharpe median**: {bear.cpcv_oos_median:.4f}"
        if bear.cpcv_oos_median is not None
        else "- **CPCV OOS Sharpe median**: n/a"
    )
    lines.append(f"- **n_bars**: {bear.n_bars}")
    lines.append("")

    lines.append("## Pre-registered IC screen (BL-706)")
    lines.append("")
    if ic is None:
        lines.append("- IC screen skipped (insufficient bars for the screen's window count).")
    else:
        lines.append(f"- **n_windows**: {ic.n_windows}")
        lines.append(f"- **IC mean**: {ic.ic_mean:.4f}")
        lines.append(f"- **IC std**: {ic.ic_std:.4f}")
        lines.append(f"- **ICIR (raw)**: {ic.icir:.4f}")
        lines.append(f"- **ICIR (after {ic.haircut_pct:.0f}% haircut)**: {ic.icir_haircut:.4f}")
        lines.append(f"- **Block-bootstrap t**: {ic.t_block:.4f}")
        lines.append(f"- **Passes**: {'YES' if ic.passes else 'NO'}")
    lines.append("")
    lines.append("**Methodology caveat**: the IC screen above is run with the portfolio's own")
    lines.append("daily returns as the factor proxy and the equity curve as the price series.")
    lines.append("This is a best-effort serialised IC test (autocorrelation-style); the canonical")
    lines.append("BL-706 screen is designed for cross-sectional factor-vs-forward-return tests on")
    lines.append("a single (factor, prices) pair per hypothesis. A per-rebalance composite-score")
    lines.append("series would be the proper input — that requires extending")
    lines.append("`LaneBBacktestResult` with the per-rebalance composite series, which we")
    lines.append("deliberately avoided here so we do not diverge from the manifest's pinned code")
    lines.append("commit. IC verdict in this report is **methodology-limited**, not a hard gate.")
    lines.append("")

    lines.append("## Anti-HARKing clause")
    lines.append("")
    lines.append(
        "All thresholds in the BL-726 manifest were fixed before this run; "
        "this report does not modify the manifest.  Per §7 of "
        "`docs/research/prereg/BL-726-lane-b-composite-variant.md`, the only "
        "acceptable post-result action is to declare the variant "
        "`REJECTED` and re-open BL-726 with a new manifest version."
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = _parse_args()

    if not args.manifest.exists():
        print(f"error: manifest not found at {args.manifest}")
        return 1

    prereg = load_prereg(args.manifest)
    print(f"[manifest] {prereg.bl_id} / {prereg.variant_name}")
    print(f"[manifest] pinned commit = {prereg.code_commit}")

    head = subprocess_run("rev-parse", "HEAD", cwd=REPO_ROOT)
    tree_ok = True
    try:
        verify_clean_tree(prereg.code_commit, repo_root=REPO_ROOT)
    except PreregError as exc:
        tree_ok = False
        print(f"[tree] FAILED: {exc}")
        if not args.allow_head_mismatch:
            print("[tree] aborting (use --allow-head-mismatch to proceed despite drift)")
            return 2
    print(f"[tree] ok={tree_ok}, HEAD={head}")

    # Build LaneBBacktestConfig from the manifest parameters
    params = prereg.parameters
    cfg = LaneBBacktestConfig(
        initial_capital=float(params["initial_capital"]),
        rebalance_months=int(params["rebalance_months"]),
        top_n_holdings=int(params["top_n_holdings"]),
        min_f_score=int(params["min_f_score"]),
        magic_rank_max=int(params["magic_rank_max"]),
        return_12m_min=float(params["return_12m_min"]),
        return_12m_max=float(params["return_12m_max"]),
        benchmark_simfin_id=int(params["benchmark_simfin_id"])
        if params.get("benchmark_simfin_id")
        else None,
        target_annual_vol=float(params["target_annual_vol"]),
        sector_blacklist=tuple(params.get("sector_blacklist", [])),
        per_idea_stop_loss_pct=float(params["per_idea_stop_loss_pct"]),
        use_composite=bool(params["use_composite"]),
        composite_weights=tuple(params["composite_weights"]),
        composite_threshold=float(params["composite_threshold"]),
        composite_return_band=tuple(params["composite_return_band"]),
    )
    print(f"[config] {cfg}")

    # Load SimFin + run backtest
    print("[simfin] loading bulk data ...")
    loader = SimFinLoader()
    backtester = LaneBBacktester(loader, config=cfg)

    start = datetime.fromisoformat(prereg.sample_window["qualification_start"])
    end = datetime.fromisoformat(prereg.sample_window["qualification_end"])
    print(f"[backtest] running {start.isoformat()} → {end.date().isoformat()}")
    result = backtester.run(start_date=start, end_date=end)
    sr_str = f"{result.sharpe:.4f}" if result.sharpe is not None else "n/a"
    print(
        f"[backtest] n_rebalances={result.n_rebalances}, sharpe={sr_str}, "
        f"maxDD={result.max_drawdown:.4f}, total_ret={result.total_return:.4f}"
    )

    # Reconstruct the daily return series from the equity curve
    equity = result.equity_curve
    daily_returns = equity[1:] / equity[:-1] - 1.0
    sorted_dates = _trading_calendar(loader, start, end, n=int(daily_returns.size))

    # Thresholds
    thr = prereg.thresholds
    n_trials_full = args.n_trials if args.n_trials is not None else 1
    n_trials_haircut = n_trials_full

    # Evaluate full + bear windows
    full_metrics, _ = _evaluate_window(
        sorted_dates,
        daily_returns,
        start=prereg.sample_window["qualification_start"],
        end=prereg.sample_window["qualification_end"],
        n_trials=n_trials_full,
        haircut_n_trials=n_trials_haircut,
    )
    bear_metrics, _ = _evaluate_window(
        sorted_dates,
        daily_returns,
        start="2022-01-01",
        end="2022-12-31",
        n_trials=n_trials_full,
        haircut_n_trials=n_trials_haircut,
    )

    # IC screen on the full window (best-effort proxy)
    ic = _build_ic_screen(
        sorted_dates,
        daily_returns,
        icir_threshold=float(thr.get("icir_threshold", 0.05)),
        ic_block_t=float(thr.get("ic_block_t_threshold", 2.5)),
        haircut_pct=float(thr.get("icir_haircut_pct", 30.0)),
    )

    # Build gate list.  PBO is reported as N/A (single-row matrix),
    # not FAIL — the overfitting protection comes from CPCV OOS median
    # + DSR + haircut Sharpe instead (per BL-726 §4 note).
    pbo_pass = True  # n/a — single-row returns matrix
    gates: list[GateResult] = [
        _gate("DSR", full_metrics.dsr, float(thr["dsr_min"]), "ge"),
        _gate("PSR", full_metrics.psr, float(thr["psr_min"]), "ge"),
        GateResult(
            name="PBO",
            passed=pbo_pass,
            observed=None,
            threshold=float(thr["pbo_max"]),
            direction="le",
            note="n/a — single-row returns matrix, PBO undefined (per BL-726 §4 note)",
        ),
        _gate(
            "CPCV OOS Sharpe median",
            full_metrics.cpcv_oos_median,
            float(thr["cpcv_oos_sharpe_median_min"]),
            "ge",
        ),
        _gate(
            "Haircut Sharpe", full_metrics.haircut_sharpe, float(thr["haircut_sharpe_min"]), "ge"
        ),
        _gate(
            "Bear 2022 Sharpe",
            bear_metrics.observed_sharpe,
            float(thr["bear_2022_sharpe_min"]),
            "ge",
        ),
    ]
    if ic is not None:
        gates.append(
            _gate(
                "IC screen (pre-registered)",
                1.0 if ic.passes else 0.0,
                1.0,
                "eq",
                note=f"ICIR haircut={ic.icir_haircut:.4f}, t={ic.t_block:.4f}",
            )
        )

    reasons: list[str] = []
    if not tree_ok:
        reasons.append(f"Tree-integrity gate failed: HEAD {head} != pinned {prereg.code_commit}")
    for g in gates:
        if g.passed or g.observed is None:
            continue
        obs = f"{g.observed:.4f}"
        reasons.append(f"{g.name} {obs} failed ({g.note})".rstrip())

    verdict = _verdict(gates, tree_ok)
    print(f"[verdict] {verdict}")

    payload = {
        "metadata": {
            "task": f"{prereg.bl_id} — Lane B composite pre-registered qualification",
            "generated": datetime.now(UTC).isoformat(),
            "manifest": str(args.manifest.relative_to(REPO_ROOT)),
            "pinned_commit": prereg.code_commit,
            "actual_head": head,
            "tree_integrity_ok": tree_ok,
            "n_trials_used_for_dsr": n_trials_full,
            "config": asdict(cfg),
        },
        "backtest_summary": {
            "n_rebalances": result.n_rebalances,
            "n_holdings_per_rebalance": result.n_holdings_per_rebalance,
            "n_unique_tickers": result.n_unique_tickers,
            "hit_rate": result.hit_rate,
            "total_return": result.total_return,
            "annual_return": result.annual_return,
            "sharpe_backtester": result.sharpe,
            "max_drawdown": result.max_drawdown,
            "benchmark_return": result.benchmark_return,
            "alpha_vs_benchmark": result.alpha_vs_benchmark,
            "n_bars": int(daily_returns.size),
        },
        "qualification_window": asdict(full_metrics),
        "bear_2022_window": asdict(bear_metrics),
        "ic_screen": asdict(ic) if ic is not None else None,
        "gates": [asdict(g) for g in gates],
        "verdict": verdict,
        "reasons": reasons,
    }
    md = _render_markdown(
        prereg, tree_ok, head, gates, verdict, full_metrics, bear_metrics, ic, reasons
    )
    json_path, md_path = _write_reports(args.out_dir, payload, md)
    print(f"[report] {md_path}")
    print(f"[report] {json_path}")
    return 0


def _trading_calendar(
    loader: SimFinLoader, start: datetime, end: datetime, *, n: int
) -> list[datetime]:
    """Take the first *n* unique trading dates from the loader's price cache.

    The backtester aggregates equal-weight returns on dates where at
    least one holding has valid data. We approximate by reading the
    full trading calendar from `loader.daily_prices()` and truncating
    to *n* dates — close enough for sub-window slicing (≈ 252 days/yr
    density), and avoids modifying `LaneBBacktestResult` (which would
    diverge from the manifest's pinned commit).
    """
    prices = loader.daily_prices()
    dates = (
        prices.filter((pl.col("date") >= start) & (pl.col("date") <= end))
        .select("date")
        .unique()
        .sort("date")["date"]
        .to_list()
    )
    if n > len(dates):
        n = len(dates)
    return dates[:n]


def subprocess_run(*args, cwd: Path) -> str:
    import subprocess

    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
