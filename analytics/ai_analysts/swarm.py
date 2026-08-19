"""AI Analyst Swarm — top-level orchestrator (Renaissance Medallion pattern).

Usage:
    from analytics.ai_analysts.swarm import AIAnalystSwarm
    swarm = AIAnalystSwarm(symbol_or_name="INTC")
    thesis = await swarm.analyze()

Returns a SynthesisThesis with catalyst, invalidation, horizon, sizing,
confidence, evidence by analyst, and skeptic findings.

Pipeline (no LangGraph required for v1; sequential LLM calls):
1. FundamentalAnalyst (deterministic; SimFin bulk data)
2. SectorAnalyst (deterministic; yfinance sector ETFs)
3. SentimentAnalyst (RSS scraping + transformers NLP)
4. LateralAnalyst (LLM; cross-domain pattern matching)
5. Synthesizer (LLM; aggregate 4 reports into thesis)
6. Skeptic (LLM; challenge the synthesis)
7. Risk Manager (deterministic; final gate)

Each analyst runs independently; results are aggregated by the
Synthesizer. The Skeptic can downgrade or reject the thesis.

The LLM endpoint is configurable via env: LLM_BASE, LLM_KEY, LLM_MODEL.
Default uses opencode.ai zen + claude-sonnet-4-6 (already configured in .env).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from analytics.ai_analysts.fundamental import FundamentalAnalyst
from analytics.ai_analysts.lateral import LateralAnalyst, LateralReport
from analytics.ai_analysts.sector import SectorAnalyst, SectorReport
from analytics.ai_analysts.sentiment import SentimentAnalyst, SentimentReport
from analytics.ai_analysts.synthesizer import SynthesisThesis, Synthesizer
from analytics.fundamental.simfin_loader import SimFinLoader


@dataclass
class SwarmConfig:
    """Configuration for the AI Analyst Swarm.

    Attributes
    ----------
    skip_sentiment : bool
        If True, skip RSS scraping + transformers NLP (slow).
        Default False.
    skip_lateral : bool
        If True, skip LLM lateral analyst.
        Default False (lateral is the operator's core intuition).
    skip_sector : bool
        If True, skip sector ETF fetching.
        Default False.
    """

    skip_sentiment: bool = False
    skip_lateral: bool = False
    skip_sector: bool = False


class AIAnalystSwarm:
    """Multi-agent AI analyst swarm (Renaissance Medallion pattern).

    Orchestrates 4-5 specialised analysts + synthesizer + skeptic to
    produce a single thesis for a target ticker.
    """

    def __init__(
        self,
        *,
        simfin_loader: SimFinLoader | None = None,
        llm_model: str | None = None,
        llm_base: str | None = None,
        llm_key: str | None = None,
        config: SwarmConfig | None = None,
    ) -> None:
        self.config = config or SwarmConfig()
        self.simfin_loader = simfin_loader or SimFinLoader(
            api_key=os.environ.get("SIMFIN_API_KEY", "")
        )
        self.fundamental = FundamentalAnalyst(loader=self.simfin_loader)
        self.sector = SectorAnalyst()
        self.sentiment = SentimentAnalyst()
        self.lateral = LateralAnalyst(llm_model=llm_model, llm_base=llm_base, llm_key=llm_key)
        self.synthesizer = Synthesizer(llm_model=llm_model, llm_base=llm_base, llm_key=llm_key)

    def analyze(self, symbol_or_name: str) -> SynthesisThesis:
        """Run all analysts + synthesizer + skeptic for a ticker."""
        print(f"\n{'=' * 60}")
        print(f"AI Analyst Swarm — analyzing: {symbol_or_name}")
        print(f"{'=' * 60}")

        # 1. Fundamental analyst (deterministic)
        print("\n[1/5] Fundamental analyst (SimFin)...")
        fundamental = self.fundamental.analyze(symbol_or_name)
        print(
            f"  F-Score: {fundamental.f_score}/9, "
            f"Rev YoY: {fundamental.revenue_growth_yoy}, "
            f"12m ret: {fundamental.return_12m:+.1%}"
        )
        if fundamental.simfin_id == 0:
            print(f"  ❌ Company '{symbol_or_name}' not found in SimFin — aborting")
            return SynthesisThesis(
                ticker=symbol_or_name,
                risk_decision="REJECT",
                final_size_pct=0.0,
                evidence_by_analyst={"fundamental": fundamental.evidence},
            )

        # 2. Sector analyst (deterministic, yfinance)
        if not self.config.skip_sector:
            print("\n[2/5] Sector analyst (yfinance ETF rotation)...")
            business_summary = fundamental.company_name + " " + " ".join(fundamental.evidence)
            sector = self.sector.analyze(symbol_or_name, business_summary=business_summary)
            print(
                f"  Sector: {sector.sector} ({sector.sector_etf}), "
                f"rotation: {sector.rotation_signal}"
            )
        else:
            sector = SectorReport(
                ticker=symbol_or_name,
                sector="unknown",
                sector_etf="unknown",
                evidence=["(sector analyst skipped)"],
            )

        # 3. Sentiment analyst (RSS + transformers)
        if not self.config.skip_sentiment:
            print("\n[3/5] Sentiment analyst (RSS + transformers NLP)...")
            try:
                sentiment = self.sentiment.analyze(symbol_or_name)
                print(
                    f"  Articles: {sentiment.n_articles}, "
                    f"avg sentiment: {sentiment.avg_sentiment:+.3f}, "
                    f"momentum: {sentiment.sentiment_momentum:+.3f}"
                )
            except Exception as e:
                print(f"  ⚠️ Sentiment analyst failed: {e}")
                sentiment = SentimentReport(
                    ticker=symbol_or_name, evidence=[f"Sentiment analyst error: {e}"]
                )
        else:
            sentiment = SentimentReport(
                ticker=symbol_or_name, evidence=["(sentiment analyst skipped)"]
            )

        # 4. Lateral analyst (LLM)
        if not self.config.skip_lateral:
            print("\n[4/5] Lateral analyst (LLM cross-domain patterns)...")
            top_headlines_str = "\n".join(f"  - {h}" for h in sentiment.top_headlines[:5])
            lateral = self.lateral.analyze(
                symbol_or_name,
                company_name=fundamental.company_name,
                business_summary=" ".join(fundamental.evidence),
                revenue_growth=(
                    f"{fundamental.revenue_growth_yoy:+.1%}"
                    if fundamental.revenue_growth_yoy is not None
                    else "n/a"
                ),
                gross_margin=(
                    f"{fundamental.gross_margin:.1%}"
                    if fundamental.gross_margin is not None
                    else "n/a"
                ),
                gross_margin_trend=fundamental.gross_margin_trend,
                f_score=fundamental.f_score,
                return_12m=f"{fundamental.return_12m:+.1%}",
                top_headlines=top_headlines_str,
            )
            print(f"  Analogies: {len(lateral.analogies)}, red_flag: {lateral.red_flag or 'none'}")
        else:
            lateral = LateralReport(ticker=symbol_or_name, evidence=["(lateral analyst skipped)"])

        # 5. Synthesizer + Skeptic (LLM)
        print("\n[5/5] Synthesizer + Skeptic (LLM)...")
        synthesis_dict, skeptic_findings = self.synthesizer.synthesize(
            symbol_or_name,
            sector=sector,
            sentiment=sentiment,
            fundamental=fundamental,
            lateral=lateral,
        )

        # Build final thesis
        thesis = SynthesisThesis(
            ticker=symbol_or_name,
            catalyst=synthesis_dict.get("catalyst", ""),
            invalidation=synthesis_dict.get("invalidation", ""),
            horizon_days=int(synthesis_dict.get("horizon_days", 365)),
            sizing_pct=float(synthesis_dict.get("sizing_pct", 0.025)),
            confidence=float(synthesis_dict.get("confidence", 0.0)),
            evidence_by_analyst={
                "sector": sector.evidence,
                "sentiment": sentiment.evidence,
                "fundamental": fundamental.evidence,
                "lateral": lateral.evidence,
                "synthesizer": synthesis_dict.get("evidence_by_analyst", {}),
            },
            skeptic_findings=skeptic_findings or synthesis_dict.get("skeptic_findings", []),
        )

        # Risk manager decision (deterministic)
        if thesis.confidence < 0.4 or "REJECT" in str(thesis.skeptic_findings).upper():
            thesis.risk_decision = "REJECT"
            thesis.final_size_pct = 0.0
        elif thesis.confidence >= 0.7 and not thesis.skeptic_findings:
            thesis.risk_decision = "APPROVE"
            thesis.final_size_pct = min(thesis.sizing_pct, 0.05)  # cap at 5%
        else:
            thesis.risk_decision = "REDUCE_SIZE"
            thesis.final_size_pct = min(thesis.sizing_pct * 0.5, 0.025)  # half size, cap 2.5%

        print()
        print("=" * 60)
        print(f"Thesis for {thesis.ticker}:")
        print(f"  Catalyst: {thesis.catalyst}")
        print(f"  Invalidation: {thesis.invalidation}")
        print(f"  Horizon: {thesis.horizon_days}d, sizing: {thesis.sizing_pct:.1%}")
        print(f"  Confidence: {thesis.confidence:.2f}")
        print(f"  Risk decision: {thesis.risk_decision}, final size: {thesis.final_size_pct:.1%}")
        if thesis.skeptic_findings:
            print("  Skeptic findings:")
            for s in thesis.skeptic_findings:
                print(f"    - {s}")
        print("=" * 60)

        return thesis


__all__: list[str] = ["AIAnalystSwarm", "SwarmConfig"]
