"""Probe LLM with a long lateral-style prompt to find why it returns empty content."""

from __future__ import annotations

import os
import sys
from typing import Any

import requests

LATERAL_PROMPT = """You are a LATERAL ANALYST — a creative pattern-matcher who finds insights where conventional analysts wouldn't look.

The operator's intuition (from his actual Intel/Xiaomi trades) is that edge lives in:
1. Deep product knowledge (touchscreen capacitivo vs resistivo — real innovation, not marketing)
2. CEO career history (Lisa Su AMD turnaround archetype)
3. Cross-market positioning (Xiaomi = China + tech + consumer)
4. Supply chain interdependencies (TSMC capacity → Apple/AMD/Nvidia)
5. Hidden moats (CUDA lock-in vs ROCM)
6. Catalysts not yet priced in (Intel foundry services with ARM licensees)

You have deep knowledge of the target company. Apply your lateral thinking:

## Target: AMD (Advanced Micro Devices)
## Business summary: Semiconductor company, CPUs + GPUs, AI accelerators
## Recent fundamentals:
- Revenue YoY growth: +3.3%
- Gross margin: 39.8% (contracting)
- F-Score: 5/9
- 12-month return: +11.2%

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
{
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
}
"""


def main() -> int:
    base = os.environ.get("LLM_BASE", "https://opencode.ai/zen/go/v1")
    key = os.environ.get("LLM_KEY", "")
    model = os.environ.get("LLM_MODEL", "glm-5.3")

    print(f"Probing {model} at {base} with a long lateral prompt")
    print(f"Prompt length: {len(LATERAL_PROMPT)} chars")
    print()

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a JSON generator. Return ONLY valid JSON. No markdown, no prose, no code fences. Output the JSON object directly.",
            },
            {"role": "user", "content": LATERAL_PROMPT},
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(f"{base}/chat/completions", headers=headers, json=body, timeout=120)
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error body: {resp.text[:1000]}")
            return 1
        data = resp.json()
        # Print full response structure
        print("\nResponse keys:", list(data.keys()))
        if "choices" in data:
            msg = data["choices"][0]["message"]
            print(f"Message keys: {list(msg.keys())}")
            print(f"Finish reason: {data['choices'][0].get('finish_reason', 'unknown')}")
            print(f"Content length: {len(msg.get('content') or '')}")
            print(f"Content (first 500 chars): {(msg.get('content') or '')[:500]}")
            if msg.get("reasoning_content"):
                print(f"Reasoning length: {len(msg['reasoning_content'])}")
                print(f"Reasoning (first 300 chars): {msg['reasoning_content'][:300]}")
        if "usage" in data:
            print(f"\nUsage: {data['usage']}")
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
