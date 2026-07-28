"""R4 search runner — LLM researcher + GA + walk-forward + persistence.

Runs a multi-round search loop:
  1. LLM researcher proposes N specs per round (Modo A)
  2. GA search runs independently, contributes candidates
  3. Top candidates from both sources go through walk-forward validation
  4. All results persisted to experiments/r4_search.db
  5. Summary printed at end

Usage examples:
    python -m scripts.run_r4_search --mode firm --llm-rounds 3 --ga-gens 10
    python -m scripts.run_r4_search --mode free --llm-only --llm-rounds 5
    python -m scripts.run_r4_search --mode firm --ga-only --ga-gens 20 --ga-pop 40
    python -m scripts.run_r4_search --mode firm --top-wf 5 --wf-splits 5
    python -m scripts.run_r4_search --status
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Resolve project root so imports work when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.backtest.providers import DataRegistry
from analytics.strategy.experiments_store import (
    all_specs,
    save_spec_result,
    save_wf_result,
    top_specs,
)
from analytics.strategy.fitness import EvalMode, FitnessReport
from analytics.strategy.ga_spec_search import GASearchConfig, ga_spec_search
from analytics.strategy.researcher import (
    LLMStrategyResearcher,
    ResearchLog,
    SpecResult,
    run_research_rounds,
)
from analytics.strategy.spec import StrategySpec
from analytics.strategy.walk_forward_spec import walk_forward_spec

_ROOT = Path(__file__).parent.parent
logger = logging.getLogger("oracle.r4_search")


def _make_registry() -> DataRegistry:
    return DataRegistry(root=_ROOT / "data" / "ohlcv")


def cmd_run(args: argparse.Namespace) -> int:
    mode = EvalMode(args.mode)
    registry = _make_registry()

    llm_results: list[SpecResult] = []
    ga_results: list[tuple[StrategySpec, FitnessReport]] = []

    # ── LLM researcher ─────────────────────────────────────────────────────
    if not args.ga_only and args.llm_rounds > 0:
        logger.info(
            "=== LLM researcher: %d rounds x %d specs ===", args.llm_rounds, args.llm_per_round
        )
        researcher = LLMStrategyResearcher()
        log = ResearchLog(mode=mode)
        log = run_research_rounds(
            researcher, registry, rounds=args.llm_rounds, per_round=args.llm_per_round, mode=mode
        )
        llm_results = log.results
        for r in llm_results:
            if not r.error:
                spec_id = save_spec_result(r.spec, r.report, source="llm")
                logger.info(
                    "llm: saved %s fitness=%.4f pass_rate=%.1f%%",
                    r.spec.name,
                    r.fitness,
                    r.pass_rate * 100,
                )
        best = log.best()
        if best:
            logger.info(
                "LLM best: %s fitness=%.4f pass_rate=%.1f%% sharpe=%.2f",
                best.spec.name,
                best.fitness,
                best.pass_rate * 100,
                best.sharpe,
            )

    # ── GA search ──────────────────────────────────────────────────────────
    if not args.llm_only and args.ga_gens > 0:
        logger.info("=== GA search: pop=%d gens=%d ===", args.ga_pop, args.ga_gens)
        ga_config = GASearchConfig(
            pop_size=args.ga_pop,
            n_generations=args.ga_gens,
            n_elite=max(2, args.ga_pop // 10),
            seed=args.seed,
        )
        ga_result = ga_spec_search(registry, mode=mode, config=ga_config)
        ga_results = ga_result.specs
        for spec, report in ga_results:
            if report.fitness > 0:
                save_spec_result(spec, report, source="ga")
        if ga_result.best:
            best_spec, best_rep = ga_result.best
            logger.info(
                "GA best: %s fitness=%.4f pass_rate=%.1f%% sharpe=%.2f (total_evals=%d %.1fs)",
                best_spec.name,
                best_rep.fitness,
                best_rep.mc_pass_rate * 100,
                best_rep.sharpe,
                ga_result.total_evaluations,
                ga_result.elapsed_s,
            )

    # ── Walk-forward on top candidates ─────────────────────────────────────
    if args.top_wf > 0:
        logger.info("=== Walk-forward on top %d candidates ===", args.top_wf)
        candidates = top_specs(mode=args.mode, limit=args.top_wf, min_fitness=0.01)
        logger.info("Candidates for WF: %d", len(candidates))
        for row in candidates:
            spec_id = row["id"]
            spec_dict = row.get("spec", {})
            try:
                from analytics.strategy.spec import StrategySpec

                spec = StrategySpec(**spec_dict)
            except Exception as exc:
                logger.warning("WF skip %s: bad spec — %s", spec_id, exc)
                continue
            logger.info("WF: %s (%s)…", spec.name, spec.instrument)
            try:
                wf_report = walk_forward_spec(
                    spec,
                    registry,
                    mode=mode,
                    n_splits=args.wf_splits,
                    purge_window=args.wf_purge,
                    split_method="time",
                )
                save_wf_result(
                    spec_id,
                    wf_report.fold_reports,
                    {
                        "oos_sharpe_ratio": wf_report.oos_sharpe,
                        "oos_sortino_ratio": wf_report.oos_sortino,
                        "oos_max_drawdown": wf_report.oos_max_drawdown,
                        "oos_total_return": wf_report.oos_total_return,
                    },
                )
                logger.info(
                    "WF %s: median_fitness=%.4f min=%.4f std=%.4f "
                    "oos_sharpe=%.2f pass_rate_consistency=%.0f%%",
                    spec.name,
                    wf_report.median_fitness,
                    wf_report.min_fitness,
                    wf_report.fold_std,
                    wf_report.oos_sharpe,
                    wf_report.pass_rate_consistency * 100,
                )
            except Exception as exc:
                logger.warning("WF failed for %s: %s", spec.name, exc)

    # ── Summary ────────────────────────────────────────────────────────────
    _print_summary(args.mode, top_n=10)
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    for mode in ("firm", "free"):
        rows = all_specs(mode=mode)
        if not rows:
            continue
        print(f"\n{'=' * 60}")
        print(f"  Mode: {mode.upper()} — {len(rows)} specs evaluated")
        print(f"{'=' * 60}")
        rows_with_wf = [r for r in rows if r.get("wf_median_fitness") is not None]
        print(f"  Walk-forward validated: {len(rows_with_wf)}")
        top = sorted(rows, key=lambda r: r.get("fitness", 0), reverse=True)[:10]
        print("\n  Top 10 by fitness:")
        print(
            f"  {'Name':<14} {'Src':<12} {'Fitness':>7} {'PassRate':>8} "
            f"{'Sharpe':>6} {'WF-med':>7} {'WF-min':>7}"
        )
        print(f"  {'-' * 70}")
        for r in top:
            wf_med = r.get("wf_median_fitness")
            wf_min = r.get("wf_min_fitness")
            # Format the WF columns separately: folding these conditionals into
            # the row f-string made the ternary swallow the whole line, so every
            # not-yet-walk-forwarded spec printed as a bare "—".
            med_txt = f"{wf_med:>7.4f}" if wf_med is not None else f"{'—':>7}"
            min_txt = f"{wf_min:>7.4f}" if wf_min is not None else f"{'—':>7}"
            print(
                f"  {r.get('spec_name', '?'):<14} "
                f"{r.get('source', '?'):<12} "
                f"{r.get('fitness', 0):>7.4f} "
                f"{r.get('pass_rate', 0) * 100:>7.1f}% "
                f"{r.get('sharpe', 0):>6.2f} "
                f"{med_txt} {min_txt}"
            )
    return 0


def _print_summary(mode: str, top_n: int = 10) -> None:
    rows = top_specs(mode=mode, limit=top_n)
    if not rows:
        print("\n[R4] No results yet.")
        return
    print(f"\n{'=' * 60}")
    print(f"  R4 Search Summary — {mode.upper()} mode — top {len(rows)}")
    print(f"{'=' * 60}")
    for i, r in enumerate(rows):
        # `is not None`, not truthiness: a walk-forward median of exactly 0.0
        # is a real result and must not read as "never validated".
        wf_med = r.get("wf_median_fitness")
        wf = f" wf={wf_med:.4f}" if wf_med is not None else ""
        print(
            f"  [{i + 1:2d}] {r.get('spec_name', '?'):<28} "
            f"fit={r.get('fitness', 0):.4f} "
            f"pass={r.get('pass_rate', 0) * 100:.0f}% "
            f"sharpe={r.get('sharpe', 0):.2f}"
            f"{wf}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="R4 search: LLM + GA + walk-forward",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    # run sub-command
    run_p = sub.add_parser("run", help="Run search")
    run_p.add_argument("--mode", default="firm", choices=["firm", "free"])
    run_p.add_argument("--llm-rounds", type=int, default=3)
    run_p.add_argument("--llm-per-round", type=int, default=5)
    run_p.add_argument("--llm-only", action="store_true")
    run_p.add_argument("--ga-gens", type=int, default=10)
    run_p.add_argument("--ga-pop", type=int, default=30)
    run_p.add_argument("--ga-only", action="store_true")
    run_p.add_argument("--top-wf", type=int, default=5, help="N top specs to validate with WF")
    run_p.add_argument("--wf-splits", type=int, default=5)
    run_p.add_argument("--wf-purge", type=int, default=5)
    run_p.add_argument("--seed", type=int, default=42)

    # status sub-command
    sub.add_parser("status", help="Show current results")

    # top-level flags (default cmd = run)
    parser.add_argument("--mode", default="firm", choices=["firm", "free"])
    parser.add_argument("--llm-rounds", type=int, default=3)
    parser.add_argument("--llm-per-round", type=int, default=5)
    parser.add_argument("--llm-only", action="store_true")
    parser.add_argument("--ga-gens", type=int, default=10)
    parser.add_argument("--ga-pop", type=int, default=30)
    parser.add_argument("--ga-only", action="store_true")
    parser.add_argument("--top-wf", type=int, default=5)
    parser.add_argument("--wf-splits", type=int, default=5)
    parser.add_argument("--wf-purge", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--status", action="store_true", help="Show status and exit")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    if getattr(args, "status", False) or getattr(args, "cmd", None) == "status":
        sys.exit(cmd_status(args))

    sys.exit(cmd_run(args))


if __name__ == "__main__":
    main()
