"""Hard-mode search: adaptive multi-objective GA + stress gauntlet.

Two stages. The GA explores the spec space under FIRM-mode prop-firm
constraints and keeps a Pareto front of trade-offs rather than one winner. The
survivors then face the stress gauntlet — walk-forward folds plus named crisis
windows — which is where most apparently-good specs are rejected.

Usage:
    python -m scripts.run_hard_search --smoke
    python -m scripts.run_hard_search --islands 4 --pop 20 --gens 25 --gauntlet 15
    python -m scripts.run_hard_search --mode free --gens 10
    python -m scripts.run_hard_search --report
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.backtest.providers import DataRegistry
from analytics.strategy.experiments_store import save_spec_result, top_specs
from analytics.strategy.fitness import EvalMode
from analytics.strategy.ga_adaptive import AdaptiveGAConfig, adaptive_ga_search
from analytics.strategy.spec import ENTRY_TYPES, INSTRUMENTS
from analytics.strategy.stress_gauntlet import (
    GauntletThresholds,
    gauntlet_stats,
    rank_survivors,
    run_gauntlet,
)

_ROOT = Path(__file__).parent.parent
log = logging.getLogger("oracle.hard_search")


def _registry() -> DataRegistry:
    return DataRegistry(root=_ROOT / "data" / "ohlcv")


def _print_search_summary(result, mode: str) -> None:
    print(f"\n{'=' * 78}")
    print(f"  GA SEARCH — {mode.upper()} mode")
    print(f"{'=' * 78}")
    print(f"  {result.summary()}")

    if result.history:
        print(f"\n  {'gen':>4} {'best':>9} {'mean':>9} {'diversity':>10} {'mutation':>9}")
        print(f"  {'-' * 46}")
        # Show the trajectory sparsely — the shape matters, not every row.
        step = max(1, len(result.history) // 12)
        for gen, best, mean, diversity, mutation in result.history[::step]:
            print(f"  {gen:>4} {best:>9.4f} {mean:>9.4f} {diversity:>10.2f} {mutation:>9.2f}")

    if result.pareto_front:
        print(f"\n  Pareto front ({len(result.pareto_front)} non-dominated trade-offs):")
        print(
            f"  {'entry':<24} {'instr':<8} {'tf':<4} {'fit':>7} "
            f"{'mc%':>6} {'sharpe':>7} {'dd%':>6} {'trades':>7}"
        )
        print(f"  {'-' * 76}")
        for ind in result.pareto_front[:15]:
            r, s = ind.report, ind.spec
            print(
                f"  {s.entry:<24} {s.instrument:<8} {s.timeframe:<4} "
                f"{r.fitness:>7.3f} {r.mc_pass_rate * 100:>6.1f} {r.sharpe:>7.2f} "
                f"{abs(r.max_drawdown) * 100:>6.1f} {r.total_trades:>7}"
            )


def _print_gauntlet_summary(reports: list, thresholds: GauntletThresholds) -> None:
    print(f"\n{'=' * 78}")
    print("  STRESS GAUNTLET")
    print(f"{'=' * 78}")
    stats = gauntlet_stats(reports)
    if stats:
        print(
            f"  evaluated={int(stats['n_evaluated'])} "
            f"passed={int(stats['n_passed'])} "
            f"({stats['pass_fraction'] * 100:.0f}%) "
            f"median_robustness={stats['median_robustness']:.3f}"
        )
    print(
        f"\n  gate: mc>={thresholds.min_mc_pass_rate * 100:.0f}% "
        f"wf_median>={thresholds.min_median_fitness:.2f} "
        f"worst_fold>={thresholds.min_fold_fitness:.2f} "
        f"crisis>={thresholds.min_crisis_survival * 100:.0f}%"
    )

    survivors = [r for r in reports if r.passed]
    print(f"\n  --- SURVIVORS ({len(survivors)}) ---")
    if not survivors:
        print("  none — no spec cleared every stage")
    for report in rank_survivors(reports):
        if report.passed:
            print(f"  {report.summary()}")

    print("\n  --- REJECTED (with binding reason) ---")
    rejected = [r for r in rank_survivors(reports) if not r.passed]
    for report in rejected[:12]:
        print(f"  {report.summary()}")
    if len(rejected) > 12:
        print(f"  ... and {len(rejected) - 12} more")


def cmd_run(args: argparse.Namespace) -> int:
    mode = EvalMode(args.mode)
    registry = _registry()

    print(f"search space: {len(INSTRUMENTS)} instruments x {len(ENTRY_TYPES)} entries x 3 TFs")

    cfg = AdaptiveGAConfig(
        pop_per_island=args.pop,
        n_islands=args.islands,
        n_generations=args.gens,
        migration_interval=args.migration_interval,
        seed=args.seed,
    )
    result = adaptive_ga_search(registry, mode=mode, config=cfg)
    _print_search_summary(result, args.mode)

    # Persist everything with a positive score so a later run can resume.
    saved = 0
    for ind in result.all_evaluated:
        if ind.report.fitness > 0:
            save_spec_result(ind.spec, ind.report, source="ga_adaptive")
            saved += 1
    print(f"\n  persisted {saved} specs to experiments/r4_search.db")

    if args.gauntlet <= 0:
        return 0

    # Gauntlet the Pareto front first, topped up from the overall ranking:
    # the front is the interesting set, but it can be smaller than the budget.
    candidates = list(result.pareto_front)
    seen = {id(ind) for ind in candidates}
    for ind in result.all_evaluated:
        if len(candidates) >= args.gauntlet:
            break
        if id(ind) not in seen and ind.report.fitness > 0:
            candidates.append(ind)
            seen.add(id(ind))
    candidates = candidates[: args.gauntlet]

    thresholds = GauntletThresholds(
        min_mc_pass_rate=args.min_mc,
        min_median_fitness=args.min_wf,
        min_crisis_survival=args.min_crisis,
    )
    print(f"\nrunning gauntlet on {len(candidates)} candidates…")
    reports = []
    for i, ind in enumerate(candidates, 1):
        print(
            f"  [{i}/{len(candidates)}] {ind.spec.entry} {ind.spec.instrument} "
            f"{ind.spec.timeframe}…",
            flush=True,
        )
        report = run_gauntlet(
            ind.spec, registry, mode, thresholds=thresholds, n_splits=args.wf_splits
        )
        reports.append(report)

    _print_gauntlet_summary(reports, thresholds)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    rows = top_specs(mode=args.mode, limit=args.limit, min_fitness=0.0)
    if not rows:
        print("no results in experiments/r4_search.db")
        return 0
    print(f"top {len(rows)} stored specs ({args.mode} mode)")
    print(f"  {'entry':<24} {'instr':<8} {'tf':<4} {'fit':>7} {'mc%':>6} {'sharpe':>7}")
    print(f"  {'-' * 62}")
    for row in rows:
        spec = row.get("spec", {})
        print(
            f"  {spec.get('entry', '?')!s:<24} "
            f"{spec.get('instrument', '?')!s:<8} "
            f"{spec.get('timeframe', '?')!s:<4} "
            f"{row.get('fitness', 0):>7.3f} "
            f"{row.get('pass_rate', 0) * 100:>6.1f} "
            f"{row.get('sharpe', 0):>7.2f}"
        )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="firm", choices=["firm", "free"])
    parser.add_argument("--islands", type=int, default=4)
    parser.add_argument("--pop", type=int, default=20, help="members per island")
    parser.add_argument("--gens", type=int, default=25)
    parser.add_argument("--migration-interval", type=int, default=5)
    parser.add_argument("--gauntlet", type=int, default=15, help="candidates to stress test")
    parser.add_argument("--wf-splits", type=int, default=6)
    parser.add_argument("--min-mc", type=float, default=0.60)
    parser.add_argument("--min-wf", type=float, default=0.30)
    parser.add_argument("--min-crisis", type=float, default=0.70)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--smoke", action="store_true", help="tiny run to validate the pipeline")
    parser.add_argument("--report", action="store_true", help="print stored results and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.report:
        sys.exit(cmd_report(args))
    if args.smoke:
        args.islands, args.pop, args.gens, args.gauntlet = 2, 5, 2, 2
        args.wf_splits = 3
    sys.exit(cmd_run(args))


if __name__ == "__main__":
    main()
