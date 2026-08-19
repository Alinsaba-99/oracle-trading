"""Run AI Analyst Swarm on multiple tickers + generate comparative report.

Usage:
    .venv/bin/python scripts/run_ai_swarm_batch.py
    .venv/bin/python scripts/run_ai_swarm_batch.py --targets AMD,NVDA,INTC
    .venv/bin/python scripts/run_ai_swarm_batch.py --output docs/reports/ai-swarm/batch.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.ai_analysts.swarm import AIAnalystSwarm, SwarmConfig  # noqa: E402
from analytics.fundamental.simfin_loader import SimFinLoader  # noqa: E402

# 10 tickers tech dove l'operatore ha vantaggio informativo strutturale
# (conoscenza prodotto + sector + CEO patterns). Selezione strategica:
# - Top semis: AMD, NVDA, INTC, AVGO, AAPL, MSFT (deep tech knowledge)
# - Consumer tech: TSLA, AMZN (product + market positioning)
# - Platforms: GOOGL, META (ad models + AI ecosystem)
DEFAULT_TARGETS = [
    "Advanced Micro Devices",  # AMD — Lisa Su turnaround, MI300X datacenter
    "NVIDIA Corporation",  # NVDA — CUDA moat, Blackwell cadence
    "Intel Corporation",  # INTC — Pat Gelsinger turnaround, 18A foundry
    "Apple Inc.",  # AAPL — iPhone ecosystem, M-series silicon
    "Microsoft Corporation",  # MSFT — Azure + OpenAI partnership
    "Tesla, Inc.",  # TSLA — FSD + robotaxi + energy
    "Alphabet Inc.",  # GOOGL — Gemini + Google Cloud
    "Meta Platforms, Inc.",  # META — Llama + Reality Labs
    "Amazon.com, Inc.",  # AMZN — AWS + retail + AI
    "Broadcom Inc.",  # AVGO — VMware + AI custom silicon
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AI Analyst Swarm on multiple tickers")
    parser.add_argument(
        "--targets",
        default=",".join(DEFAULT_TARGETS),
        help="Comma-separated company names (default: 10 tech leaders)",
    )
    parser.add_argument(
        "--skip-sentiment", action="store_true", help="Skip RSS scraping + NLP (faster)"
    )
    parser.add_argument(
        "--skip-lateral",
        action="store_true",
        help="Skip LLM lateral analyst (faster but loses key intuition)",
    )
    parser.add_argument("--skip-sector", action="store_true")
    parser.add_argument(
        "--output",
        default="docs/reports/ai-swarm/batch-tech-validation.md",
        help="Output markdown report path",
    )
    args = parser.parse_args()

    simfin_key = os.environ.get("SIMFIN_API_KEY", "")
    llm_key = os.environ.get("LLM_KEY", "")
    if not simfin_key:
        print("❌ SIMFIN_API_KEY env var not set")
        return 1
    if not llm_key:
        print("⚠️ LLM_KEY not set — lateral/synthesizer will fail")

    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    print(f"\n{'=' * 70}")
    print(f"AI Analyst Swarm — Batch Validation ({len(targets)} tickers)")
    print(f"{'=' * 70}")
    print("Targets:")
    for i, t in enumerate(targets, 1):
        print(f"  {i}. {t}")
    print()

    simfin_loader = SimFinLoader(api_key=simfin_key)
    config = SwarmConfig(
        skip_sentiment=args.skip_sentiment,
        skip_lateral=args.skip_lateral,
        skip_sector=args.skip_sector,
    )
    swarm = AIAnalystSwarm(simfin_loader=simfin_loader, config=config)

    results: list[dict[str, Any]] = []
    for i, target in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] === {target} ===")
        try:
            thesis = swarm.analyze(target)
            results.append(
                {
                    "target": target,
                    "thesis": {
                        "ticker": thesis.ticker,
                        "catalyst": thesis.catalyst,
                        "invalidation": thesis.invalidation,
                        "horizon_days": thesis.horizon_days,
                        "sizing_pct": thesis.sizing_pct,
                        "confidence": thesis.confidence,
                        "risk_decision": thesis.risk_decision,
                        "final_size_pct": thesis.final_size_pct,
                        "skeptic_findings": thesis.skeptic_findings,
                        "evidence_by_analyst": thesis.evidence_by_analyst,
                    },
                }
            )
        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append({"target": target, "error": str(e)})

    # Generate comparative report
    print(f"\n{'=' * 70}")
    print("Comparative Summary")
    print(f"{'=' * 70}")
    print(f"{'Target':<30} {'Verdict':<15} {'Conf':<8} {'Size':<8} {'Skeptic':<10}")
    print(f"{'-' * 30} {'-' * 15} {'-' * 8} {'-' * 8} {'-' * 10}")
    for r in results:
        if "thesis" in r:
            t = r["thesis"]
            print(
                f"{r['target'][:30]:<30} {t['risk_decision']:<15} "
                f"{t['confidence']:.2f}    {t['final_size_pct']:.1%}    "
                f"{len(t.get('skeptic_findings', []))}"
            )

    # Save markdown
    out_path = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md: list[str] = []
    md.append(f"# AI Analyst Swarm — Batch Validation ({len(targets)} tech tickers)\n\n")
    md.append(f"**Generated**: {datetime.now(UTC).isoformat()}\n")
    md.append(f"**Targets**: {', '.join(targets)}\n\n")
    md.append("## Comparative Summary\n\n")
    md.append("| Target | Risk Decision | Confidence | Final Size | Skeptic Findings |\n")
    md.append("|---|---|---|---|---|\n")
    for r in results:
        if "thesis" in r:
            t = r["thesis"]
            md.append(
                f"| {r['target']} | {t['risk_decision']} | "
                f"{t['confidence']:.2f} | {t['final_size_pct']:.1%} | "
                f"{len(t.get('skeptic_findings', []))} |\n"
            )
        else:
            md.append(f"| {r['target']} | ERROR | n/a | n/a | {r.get('error', 'unknown')[:60]} |\n")
    md.append("\n## Per-target Thesis\n\n")
    for r in results:
        if "thesis" not in r:
            md.append(f"### {r['target']}\n\n❌ Error: {r.get('error', 'unknown')}\n\n")
            continue
        t = r["thesis"]
        md.append(f"### {r['target']}\n\n")
        md.append(f"- **Catalyst**: {t['catalyst']}\n")
        md.append(f"- **Invalidation**: {t['invalidation']}\n")
        md.append(f"- **Horizon**: {t['horizon_days']}d\n")
        md.append(f"- **Sizing**: {t['sizing_pct']:.1%}\n")
        md.append(f"- **Confidence**: {t['confidence']:.2f}\n")
        md.append(f"- **Risk decision**: {t['risk_decision']}\n")
        md.append(f"- **Final size**: {t['final_size_pct']:.1%}\n")
        if t.get("skeptic_findings"):
            md.append("\n**Skeptic findings**:\n")
            for s in t["skeptic_findings"]:
                md.append(f"- {s}\n")
        md.append("\n")
        # Save evidence by analyst (summary only to keep md readable)
        ev = t.get("evidence_by_analyst", {})
        if ev:
            md.append("<details><summary>Evidence by analyst</summary>\n\n")
            for analyst, bullets in ev.items():
                md.append(f"**{analyst.title()}**:\n")
                if isinstance(bullets, dict):
                    for k, v in bullets.items():
                        md.append(f"- {k}: {v if isinstance(v, str) else '...'}\n")
                elif isinstance(bullets, list):
                    for b in bullets[:5]:  # top 5 bullets per analyst
                        md.append(f"- {b}\n")
                md.append("\n")
            md.append("</details>\n\n")

    # Hit-rate summary
    approved = [r for r in results if "thesis" in r and r["thesis"]["risk_decision"] == "APPROVE"]
    reduce_size = [
        r for r in results if "thesis" in r and r["thesis"]["risk_decision"] == "REDUCE_SIZE"
    ]
    rejected = [r for r in results if "thesis" in r and r["thesis"]["risk_decision"] == "REJECT"]
    md.append("## Decision distribution\n\n")
    md.append(f"- APPROVE: {len(approved)}/{len(results)}\n")
    md.append(f"- REDUCE_SIZE: {len(reduce_size)}/{len(results)}\n")
    md.append(f"- REJECT: {len(rejected)}/{len(results)}\n\n")
    md.append("## Next steps\n\n")
    md.append(
        "1. For APPROVE targets: pre-register in TrialLedger via `scripts/register_thesis.py`\n"
    )
    md.append("2. For REDUCE_SIZE targets: smaller position (half default sizing)\n")
    md.append("3. For REJECT targets: skip — Skeptic found fatal flaws\n")
    md.append("4. Validate hit-rate over 50+ theses via `scripts/generate_alert_report.py`\n")

    out_path.write_text("".join(md))
    print(f"\n✅ Markdown report: {out_path}")

    # Save JSON
    json_path = out_path.with_suffix(".json")
    json_path.write_text(json.dumps({"results": results}, indent=2, default=str))
    print(f"✅ JSON report: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
