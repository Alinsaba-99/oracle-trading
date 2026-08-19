"""AI Analyst Swarm — Renaissance Oracle pattern (Phase 1).

A multi-agent system inspired by Renaissance Medallion + Citadel +
Two Sigma research teams, where the LLM acts as **multiple specialised
analysts** (sector, macro, sentiment, fundamental, lateral) and a
**LangGraph orchestrator** aggregates their evidence into a single
thesis recommendation.

The pattern deliberately mirrors what human hedge-fund analysts do,
including the **"lateral" / "where it wouldn't make sense to look"**
step that the operator identified as a key intuition source (e.g.,
noticing Intel touchscreen capacitivo vs resistivo, AMD CEO Lisa Su
pattern, Xiaomi cross-market positioning).

References
----------
- Jim Simons / Renaissance Medallion: 100+ PhD researchers, not one
  signal but an ENSEMBLE of weak edges
- ai-hedge-fund (virattt/ai-hedge-fund, 14K★): multi-agent LLM pattern
  (CEO + Analyst + Trader + Risk with voting instead of binary routing)
- Deep-research synthesis 2026-08-15: retail edge documented ≠ catturabile
  without structural advantage; LLM-as-analyst IS a structural advantage
  (can ingest 1000x more news/filings than a human)

Pipeline (LangGraph)
--------------------
1. **Sector Analyst** — ingests sector ETF returns, industry rotation
2. **Macro Analyst** — FRED macro data, Fed fund rates, CPI trends
3. **Sentiment Analyst** — RSS news scraping + transformers NLP model
4. **Fundamental Analyst** — SimFin bulk fundamentals (Piotroski + Greenblatt)
5. **Lateral Analyst** — cross-domain pattern matching (the operator's
   "where it wouldn't make sense to look" intuition, e.g., touchscreen
   capacitivo for Apple, CEO career history for AMD)
6. **Synthesizer** — aggregates evidence from 5 analysts + outputs
   thesis (catalyst, invalidation, horizon, sizing, confidence)
7. **Skeptic (Devil's Advocate)** — challenges the synthesis; if the
   skeptic finds a fatal flaw, the thesis is downgraded or rejected
8. **Risk Manager** — final gate: position sizing, max exposure, kill switch

Each analyst runs independently with its own LLM call; the Synthesizer
runs once. Output is a structured JSON thesis with provenance (which
analyst contributed which evidence).

Use
---
    from analytics.ai_analysts.swarm import AIAnalystSwarm
    swarm = AIAnalystSwarm(symbol="INTC")
    thesis = await swarm.analyze()
    # thesis = {catalyst, invalidation, horizon_days, sizing_pct,
    #           confidence, evidence_by_analyst, skeptic_findings}
"""

from __future__ import annotations
