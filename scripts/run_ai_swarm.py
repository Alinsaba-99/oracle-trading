"""Run the AI Analyst Swarm on a target ticker/company.

Examples:
    .venv/bin/python scripts/run_ai_swarm.py --target INTC
    .venv/bin/python scripts/run_ai_swarm.py --target "Advanced Micro Devices"
    .venv/bin/python scripts/run_ai_swarm.py --target "Applied Materials" --skip-sentiment
    .venv/bin/python scripts/run_ai_swarm.py --target AAPL --output docs/reports/ai-swarm/aapl-2026-08.md

Output:
    Console: thesis summary
    JSON file: full thesis with evidence_by_analyst + skeptic_findings
    Markdown: human-readable report
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.ai_analysts.swarm import AIAnalystSwarm, SwarmConfig  # noqa: E402
from analytics.fundamental.simfin_loader import SimFinLoader  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AI Analyst Swarm on a target ticker")
    parser.add_argument(
        "--target",
        required=True,
        help="Ticker or company name (e.g. INTC, 'Advanced Micro Devices')",
    )
    parser.add_argument("--skip-sentiment", action="store_true", help="Skip RSS scraping + NLP")
    parser.add_argument("--skip-lateral", action="store_true", help="Skip LLM lateral analyst")
    parser.add_argument("--skip-sector", action="store_true", help="Skip sector ETF fetch")
    parser.add_argument("--output-dir", default="docs/reports/ai-swarm")
    parser.add_argument("--json-only", action="store_true", help="Only output JSON, skip markdown")
    args = parser.parse_args()

    simfin_key = os.environ.get("SIMFIN_API_KEY", "")
    if not simfin_key:
        print("❌ SIMFIN_API_KEY env var not set")
        return 1
    llm_key = os.environ.get("LLM_KEY", "")
    if not llm_key:
        print("⚠️ LLM_KEY env var not set — lateral/synthesizer will fail")

    simfin_loader = SimFinLoader(api_key=simfin_key)
    config = SwarmConfig(
        skip_sentiment=args.skip_sentiment,
        skip_lateral=args.skip_lateral,
        skip_sector=args.skip_sector,
    )
    swarm = AIAnalystSwarm(simfin_loader=simfin_loader, config=config)

    print(f"\nAI Analyst Swarm — target: {args.target}")
    print(
        f"Config: skip_sentiment={config.skip_sentiment}, skip_lateral={config.skip_lateral}, skip_sector={config.skip_sector}"
    )

    thesis = swarm.analyze(args.target)

    # Save JSON
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
    safe_target = args.target.replace(" ", "-").replace("/", "-").lower()[:30]
    json_path = output_dir / f"{safe_target}-{timestamp}.json"

    payload = {
        "target": args.target,
        "generated_at": datetime.now(UTC).isoformat(),
        "thesis": {
            "ticker": thesis.ticker,
            "catalyst": thesis.catalyst,
            "invalidation": thesis.invalidation,
            "horizon_days": thesis.horizon_days,
            "sizing_pct": thesis.sizing_pct,
            "confidence": thesis.confidence,
            "evidence_by_analyst": thesis.evidence_by_analyst,
            "skeptic_findings": thesis.skeptic_findings,
            "risk_decision": thesis.risk_decision,
            "final_size_pct": thesis.final_size_pct,
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n✅ JSON saved to: {json_path}")

    if not args.json_only:
        md_path = output_dir / f"{safe_target}-{timestamp}.md"
        md: list[str] = []
        md.append(f"# AI Analyst Swarm Report — {args.target}\n\n")
        md.append(f"**Generated**: {datetime.now(UTC).isoformat()}\n")
        md.append(f"**Target**: {args.target}\n\n")
        md.append("## Thesis\n\n")
        md.append(f"- **Catalyst**: {thesis.catalyst}\n")
        md.append(f"- **Invalidation**: {thesis.invalidation}\n")
        md.append(f"- **Horizon**: {thesis.horizon_days}d\n")
        md.append(f"- **Sizing**: {thesis.sizing_pct:.1%}\n")
        md.append(f"- **Confidence**: {thesis.confidence:.2f}\n")
        md.append(f"- **Risk decision**: {thesis.risk_decision}\n")
        md.append(f"- **Final size**: {thesis.final_size_pct:.1%}\n\n")
        md.append("## Evidence by analyst\n\n")
        for analyst, ev in thesis.evidence_by_analyst.items():
            md.append(f"### {analyst.title()}\n\n")
            if isinstance(ev, dict):
                for k, v in ev.items():
                    md.append(f"**{k.title()}**:\n")
                    if isinstance(v, list):
                        for item in v:
                            md.append(f"- {item}\n")
                    else:
                        md.append(f"- {v}\n")
                    md.append("\n")
            elif isinstance(ev, list):
                for item in ev:
                    md.append(f"- {item}\n")
                md.append("\n")
        md.append("\n## Skeptic findings\n\n")
        if thesis.skeptic_findings:
            for s in thesis.skeptic_findings:
                md.append(f"- {s}\n")
        else:
            md.append("(no skeptic findings)\n")
        md_path.write_text("".join(md))
        print(f"✅ Markdown saved to: {md_path}")

    return 0 if thesis.risk_decision != "REJECT" else 1


if __name__ == "__main__":
    sys.exit(main())
