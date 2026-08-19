"""Synthesizer + Skeptic + Risk Manager — the LangGraph orchestrator.

The Synthesizer aggregates evidence from 5 analysts (sector, macro,
sentiment, fundamental, lateral) into a structured thesis. The Skeptic
challenges the synthesis. The Risk Manager applies position sizing +
final gate.

References
----------
- ai-hedge-fund pattern (virattt/ai-hedge-fund, 14K★): multi-agent LLM
  with CEO + Analyst + Trader + Risk with voting instead of binary routing
- Operator's vision (2026-08-16): "agenti AI come team di hedge fund o
  analisti come Jim Simons" — Renaissance Medallion style
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from analytics.ai_analysts.fundamental import FundamentalReport
from analytics.ai_analysts.lateral import LateralReport
from analytics.ai_analysts.sector import SectorReport
from analytics.ai_analysts.sentiment import SentimentReport


@dataclass
class SynthesisThesis:
    """Final thesis output from the AI Analyst Swarm.

    Attributes
    ----------
    ticker : str
        Target ticker.
    catalyst : str
        Identified catalyst.
    invalidation : str
        What would make the thesis wrong.
    horizon_days : int
        Recommended holding period.
    sizing_pct : float
        Position size as fraction (0.025 = 2.5%).
    confidence : float
        Synthesizer confidence in [0, 1].
    evidence_by_analyst : dict[str, list[str]]
        Map: analyst_name → list of evidence bullets.
    skeptic_findings : list[str]
        Skeptic challenges.
    risk_decision : str
        One of: "APPROVE", "REDUCE_SIZE", "REJECT".
    final_size_pct : float
        Final sizing after risk adjustments.
    """

    ticker: str
    catalyst: str = ""
    invalidation: str = ""
    horizon_days: int = 365
    sizing_pct: float = 0.025
    confidence: float = 0.0
    evidence_by_analyst: dict[str, list[str]] = field(default_factory=dict)
    skeptic_findings: list[str] = field(default_factory=list)
    risk_decision: str = "REJECT"
    final_size_pct: float = 0.0


SYNTHESIS_PROMPT = """You are the SYNTHESIZER of an AI hedge-fund analyst swarm.

You have received reports from 5 specialised analysts on the target ticker.
Your job: aggregate their evidence into a single THESIS with:
- catalyst (one specific catalyst the swarm agrees on)
- invalidation (what would make the thesis wrong)
- horizon_days (holding period in days)
- sizing_pct (position size as fraction; default 0.025 = 2.5%; max 0.05)
- confidence (0-1; how confident you are in the thesis)
- evidence_by_analyst (preserve which analyst contributed which evidence)
- skeptic_findings (challenges you anticipate from the Skeptic)

## Target ticker: {ticker}

## Sector Analyst Report
- Sector: {sector} ({sector_etf})
- Rotation: {rotation_signal}
- 1m/3m/12m returns: {sector_returns}
- Evidence: {sector_evidence}

## Sentiment Analyst Report
- Articles: {n_articles} (z-score {news_volume_zscore})
- Avg sentiment: {avg_sentiment}
- Sentiment momentum: {sentiment_momentum}
- Top headlines: {top_headlines}
- Evidence: {sentiment_evidence}

## Fundamental Analyst Report
- F-Score: {f_score}/9
- Revenue YoY: {revenue_growth}
- Gross Margin: {gross_margin} ({gross_margin_trend})
- 12-mo return: {return_12m}
- Evidence: {fundamental_evidence}

## Lateral Analyst Report
- Analogies: {lateral_analogies}
- CEO pattern: {ceo_pattern}
- Supply chain: {supply_chain_insight}
- Moat: {moat_assessment}
- Hidden catalyst: {hidden_catalyst}
- Red flag: {lateral_red_flag}
- Evidence: {lateral_evidence}

## Your task
Synthesize the thesis. Be HONEST:
- If the evidence is conflicting (e.g., sentiment positive but F-Score low), say so.
- If the lateral analyst found a strong analogy (like Apple 2007 touchscreen) AND fundamentals confirm, raise confidence.
- If the lateral analyst found a red flag AND sentiment is deteriorating, lower confidence or REJECT.
- Default sizing 0.025 (2.5%); if confidence > 0.7, may raise to 0.04 (4%); if confidence < 0.4, REJECT.

Return JSON with this exact schema:
{{
  "catalyst": "one specific catalyst (e.g., 'Intel 18A process ramp + foundry customer wins')",
  "invalidation": "one specific invalidation (e.g., '18A delay >2 quarters OR gross margin <35% for 2 consecutive quarters')",
  "horizon_days": 365,
  "sizing_pct": 0.025,
  "confidence": 0.65,
  "evidence_by_analyst": {{
    "sector": ["bullet 1", "bullet 2"],
    "sentiment": ["bullet 1"],
    "fundamental": ["bullet 1", "bullet 2"],
    "lateral": ["bullet 1", "bullet 2"]
  }},
  "skeptic_findings": [
    "anticipated skeptic challenge 1",
    "anticipated skeptic challenge 2"
  ]
}}
"""

SKEPTIC_PROMPT = """You are the SKEPTIC / DEVIL'S ADVOCATE of the AI hedge-fund swarm.

Your job: find the FATAL FLAW in the synthesis. Default to REJECT unless
the evidence is overwhelming. Look for:
- Overfitting to recent news (recency bias)
- Conflicting signals masked as confirmations
- Lateral analogies that don't actually apply
- Margin compression risk not priced in
- Sector rotation turning against the thesis
- Macro environment changing

## Target ticker: {ticker}
## Synthesis thesis:
{synthesis_json}

## Your task
Challenge the synthesis. Return JSON:
{{
  "fatal_flaw": "the single biggest risk to this thesis OR null if thesis is robust",
  "additional_concerns": ["concern 1", "concern 2"],
  "verdict": "APPROVE" or "REDUCE_SIZE" or "REJECT"
}}
"""


class Synthesizer:
    """LLM-powered synthesizer that aggregates 5 analyst reports into one thesis."""

    def __init__(
        self,
        *,
        llm_model: str | None = None,
        llm_base: str | None = None,
        llm_key: str | None = None,
    ) -> None:
        self.model = llm_model or os.environ.get("LLM_MODEL", "glm-5.3")
        self.base = llm_base or os.environ.get("LLM_BASE", "https://opencode.ai/zen/go/v1")
        self.api_key = llm_key or os.environ.get("LLM_KEY", "")

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        """Call LLM via raw HTTP request for reliability."""
        import requests

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            body: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a JSON generator. Return ONLY valid JSON. No markdown, no prose, no code fences. Output the JSON object directly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 8000,  # thinking model needs room for reasoning + answer
                "response_format": {"type": "json_object"},
                "stream": False,
            }
            resp = None
            for attempt in range(4):
                resp = requests.post(
                    f"{self.base}/chat/completions",
                    headers=headers,
                    json=body,
                    timeout=180,  # longer timeout for thinking models
                )
                if resp.status_code == 200:
                    break
                if resp.status_code == 503 and attempt < 3:
                    import time

                    time.sleep(12 * (attempt + 1))
                    continue
                break
            assert resp is not None
            if resp.status_code != 200:
                return {
                    "catalyst": "",
                    "invalidation": "",
                    "horizon_days": 365,
                    "sizing_pct": 0.025,
                    "confidence": 0.0,
                    "evidence_by_analyst": {},
                    "skeptic_findings": [
                        f"Synthesizer LLM HTTP {resp.status_code}: {resp.text[:200]}"
                    ],
                }
            data = resp.json()
            content = (data["choices"][0]["message"].get("content") or "").strip()
            finish_reason = data["choices"][0].get("finish_reason", "")
            if not content:
                return {
                    "catalyst": "",
                    "invalidation": "",
                    "horizon_days": 365,
                    "sizing_pct": 0.025,
                    "confidence": 0.0,
                    "evidence_by_analyst": {},
                    "skeptic_findings": [
                        f"Synthesizer LLM returned empty content (finish={finish_reason})"
                    ],
                }
            parsed: dict[str, Any] = json.loads(content)
            return parsed
        except Exception as e:
            return {
                "catalyst": "",
                "invalidation": "",
                "horizon_days": 365,
                "sizing_pct": 0.025,
                "confidence": 0.0,
                "evidence_by_analyst": {},
                "skeptic_findings": [f"Synthesizer LLM error: {e}"],
            }

    def synthesize(
        self,
        ticker: str,
        *,
        sector: SectorReport,
        sentiment: SentimentReport,
        fundamental: FundamentalReport,
        lateral: LateralReport,
    ) -> tuple[dict[str, Any], list[str]]:
        """Synthesize a thesis from 4 analyst reports.

        Returns
        -------
        tuple
            (synthesis_dict, skeptic_findings)
        """
        prompt = SYNTHESIS_PROMPT.format(
            ticker=ticker,
            sector=sector.sector,
            sector_etf=sector.sector_etf,
            rotation_signal=sector.rotation_signal,
            sector_returns=f"{sector.sector_1m_return:+.1%} / {sector.sector_3m_return:+.1%} / {sector.sector_12m_return:+.1%}",
            sector_evidence=sector.evidence,
            n_articles=sentiment.n_articles,
            news_volume_zscore=f"{sentiment.news_volume_zscore:+.2f}",
            avg_sentiment=f"{sentiment.avg_sentiment:+.3f}",
            sentiment_momentum=f"{sentiment.sentiment_momentum:+.3f}",
            top_headlines=sentiment.top_headlines,
            sentiment_evidence=sentiment.evidence,
            f_score=fundamental.f_score,
            revenue_growth=f"{fundamental.revenue_growth_yoy:+.1%}"
            if fundamental.revenue_growth_yoy is not None
            else "n/a",
            gross_margin=f"{fundamental.gross_margin:.1%}"
            if fundamental.gross_margin is not None
            else "n/a",
            gross_margin_trend=fundamental.gross_margin_trend,
            return_12m=f"{fundamental.return_12m:+.1%}",
            fundamental_evidence=fundamental.evidence,
            lateral_analogies=lateral.analogies,
            ceo_pattern=lateral.ceo_pattern or "null",
            supply_chain_insight=lateral.supply_chain_insight or "null",
            moat_assessment=lateral.moat_assessment or "null",
            hidden_catalyst=lateral.hidden_catalyst or "null",
            lateral_red_flag=lateral.red_flag or "null",
            lateral_evidence=lateral.evidence,
        )
        synthesis = self._call_llm(prompt)

        # Now run skeptic
        skeptic_prompt = SKEPTIC_PROMPT.format(
            ticker=ticker, synthesis_json=json.dumps(synthesis, indent=2)
        )
        skeptic_result = self._call_llm(skeptic_prompt)
        skeptic_findings = []
        if skeptic_result.get("fatal_flaw"):
            skeptic_findings.append(f"Fatal flaw: {skeptic_result['fatal_flaw']}")
        for concern in skeptic_result.get("additional_concerns", []):
            skeptic_findings.append(f"Concern: {concern}")

        return synthesis, skeptic_findings


__all__: list[str] = ["SynthesisThesis", "Synthesizer"]
