"""Lateral Analyst — cross-domain pattern matching (the operator's "look where it wouldn't make sense" intuition).

This analyst deliberately looks for patterns OUTSIDE the standard
fundamental/technical/sector playbook. It uses an LLM to identify
cross-domain analogies that a human analyst might spot, like:

- Intel touchscreen capacitivo vs resistivo (operator's Apple insight)
- AMD CEO Lisa Su career history (operator's CEO-quality insight)
- Xiaomi cross-market positioning (China + tech + consumer)
- Nvidia CUDA moat vs AMD ROCm (cross-vendor tech comparison)
- Supply chain interdependencies (TSMC capacity → Apple/AMD/Nvidia)

The LLM is prompted to be creative and explore analogies, then return
structured evidence. This analyst has the HIGHEST weight in the
synthesizer because it's where the operator's true edge lives.

References
----------
- Operator's chat with Roberta (2026-08-14): "L'approccio, quello è
  l'algoritmo da comprendere" — the analyst's intuition IS the algorithm
- Deep-research 2026-08-15 RF-DR4: "retail edge documentato ≠ catturabile
  senza vantaggio strutturale" — LLM-as-analyst IS the structural advantage
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LateralReport:
    """Lateral / cross-domain analysis for one ticker.

    Attributes
    ----------
    ticker : str
        Target ticker.
    analogies : list[str]
        Cross-domain analogies found by the LLM (e.g., "Apple 2007
        touchscreen moment for INTC 18A process").
    ceo_pattern : str | None
        CEO pattern identified (e.g., "Lisa Su turnaround archetype").
    supply_chain_insight : str | None
        Supply chain interdependency (e.g., "TSMC 3nm capacity → Apple
        A17 → margin expansion").
    moat_assessment : str | None
        Moat assessment (e.g., "CUDA lock-in = strong; ROCM = weak").
    hidden_catalyst : str | None
        Catalyst not yet priced in (e.g., "Intel foundry services
        agreements with ARM licensees").
    red_flag : str | None
        Counter-narrative / red flag the LLM surfaced.
    evidence : list[str]
        Bullet-point evidence for the synthesizer.
    """

    ticker: str
    analogies: list[str] = field(default_factory=list)
    ceo_pattern: str | None = None
    supply_chain_insight: str | None = None
    moat_assessment: str | None = None
    hidden_catalyst: str | None = None
    red_flag: str | None = None
    evidence: list[str] = field(default_factory=list)


LATERAL_PROMPT_TEMPLATE = """You are a LATERAL ANALYST — a creative pattern-matcher who finds insights where conventional analysts wouldn't look.

The operator's intuition (from his actual Intel/Xiaomi trades) is that edge lives in:
1. Deep product knowledge (touchscreen capacitivo vs resistivo — real innovation, not marketing)
2. CEO career history (Lisa Su AMD turnaround archetype)
3. Cross-market positioning (Xiaomi = China + tech + consumer)
4. Supply chain interdependencies (TSMC capacity → Apple/AMD/Nvidia)
5. Hidden moats (CUDA lock-in vs ROCM)
6. Catalysts not yet priced in (Intel foundry services with ARM licensees)

You have deep knowledge of the target company. Apply your lateral thinking:

## Target: {ticker} ({company_name})
## Business summary: {business_summary}

## Recent fundamentals:
- Revenue YoY growth: {revenue_growth}
- Gross margin: {gross_margin} ({gross_margin_trend})
- F-Score: {f_score}/9
- 12-month return: {return_12m}

## Recent news headlines (top 5):
{top_headlines}

## Your task
Find NON-OBVIOUS insights for this company. Look for:
- Historical analogies (a similar moment from another company/sector)
- CEO / management patterns
- Supply chain interdependencies
- Hidden moats / switching costs
- Catalysts not yet priced in
- Counter-narrative / red flag

Be CREATIVE but HONEST. If you don't see a real insight, say "no strong lateral pattern identified".

Return JSON with this exact schema:
{{
  "analogies": ["analogy 1 — what historical moment this reminds you of and why",
                "analogy 2 — another cross-domain pattern"],
  "ceo_pattern": "CEO career history pattern OR null",
  "supply_chain_insight": "supply chain interdependency OR null",
  "moat_assessment": "hidden moat / switching cost assessment OR null",
  "hidden_catalyst": "catalyst not yet priced in OR null",
  "red_flag": "counter-narrative or red flag OR null",
  "evidence": ["bullet 1 — one-sentence summary of your strongest lateral insight",
               "bullet 2 — second insight",
               "bullet 3 — third insight"]
}}
"""


class LateralAnalyst:
    """Lateral / cross-domain LLM analyst.

    Uses an LLM to identify cross-domain patterns. The operator's
    intuition (Intel touchscreen, Xiaomi cross-market) lives here.
    """

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
        """Call the LLM with raw HTTP request (more reliable than litellm for response_format)."""
        import requests

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            # glm-5.3 is a "thinking" model: the actual JSON output appears in
            # message.content only after the model's reasoning_content finishes.
            # If max_tokens is too small, finish_reason="length" and content=""
            # (reasoning consumed all tokens). Raise max_tokens to 8000 to give
            # reasoning + answer room to complete.
            body: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a JSON generator. Return ONLY valid JSON. No markdown, no prose, no code fences. Output the JSON object directly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 8000,  # BL-505 fix: glm-5.3 thinking needs ~2-4k reasoning tokens before answer
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

                    time.sleep(
                        12 * (attempt + 1)
                    )  # 12s, 24s, 36s backoff for proxy rate-limit queue
                    continue
                break
            assert resp is not None
            if resp.status_code != 200:
                return {
                    "analogies": [],
                    "ceo_pattern": None,
                    "supply_chain_insight": None,
                    "moat_assessment": None,
                    "hidden_catalyst": None,
                    "red_flag": f"LLM HTTP {resp.status_code}: {resp.text[:200]}",
                    "evidence": [f"Lateral analyst LLM HTTP error: {resp.status_code}"],
                }
            data = resp.json()
            content = (data["choices"][0]["message"].get("content") or "").strip()
            finish_reason = data["choices"][0].get("finish_reason", "")
            if not content:
                return {
                    "analogies": [],
                    "ceo_pattern": None,
                    "supply_chain_insight": None,
                    "moat_assessment": None,
                    "hidden_catalyst": None,
                    "red_flag": f"LLM returned empty content (finish_reason={finish_reason})",
                    "evidence": [
                        f"Lateral analyst LLM returned empty content (finish={finish_reason})"
                    ],
                }
            parsed: dict[str, Any] = json.loads(content)
            return parsed
        except Exception as e:
            return {
                "analogies": [],
                "ceo_pattern": None,
                "supply_chain_insight": None,
                "moat_assessment": None,
                "hidden_catalyst": None,
                "red_flag": f"LLM call failed: {e}",
                "evidence": [f"Lateral analyst LLM error: {e}"],
            }

    def analyze(
        self,
        ticker: str,
        *,
        company_name: str = "",
        business_summary: str = "",
        revenue_growth: str = "n/a",
        gross_margin: str = "n/a",
        gross_margin_trend: str = "stable",
        f_score: int = 0,
        return_12m: str = "n/a",
        top_headlines: str = "(no headlines provided)",
    ) -> LateralReport:
        """Analyze cross-domain patterns for a ticker."""
        prompt = LATERAL_PROMPT_TEMPLATE.format(
            ticker=ticker,
            company_name=company_name or ticker,
            business_summary=business_summary or "(unknown)",
            revenue_growth=revenue_growth,
            gross_margin=gross_margin,
            gross_margin_trend=gross_margin_trend,
            f_score=f_score,
            return_12m=return_12m,
            top_headlines=top_headlines,
        )
        result = self._call_llm(prompt)
        return LateralReport(
            ticker=ticker,
            analogies=result.get("analogies", []),
            ceo_pattern=result.get("ceo_pattern"),
            supply_chain_insight=result.get("supply_chain_insight"),
            moat_assessment=result.get("moat_assessment"),
            hidden_catalyst=result.get("hidden_catalyst"),
            red_flag=result.get("red_flag"),
            evidence=result.get("evidence", []),
        )


__all__: list[str] = ["LATERAL_PROMPT_TEMPLATE", "LateralAnalyst", "LateralReport"]
