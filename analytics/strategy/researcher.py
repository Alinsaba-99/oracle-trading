"""LLM strategy researcher — Modo A (R4-rewired).

The LLM acts as a quant researcher: given the current best candidate and
the history of tried specs + their FitnessReports, it proposes new
:class:`StrategySpec` objects.  The machine deterministically builds,
backtests, and evaluates each via :func:`evaluator.evaluate_spec` (the
unified R3 entry point) — same fitness function used by the GA.

LLM access is via an OpenAI-compatible endpoint (litellm).  Configure with
env: ``LLM_BASE``, ``LLM_KEY``, ``LLM_MODEL`` (see ``.env.example``).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from analytics.backtest.providers import DataRegistry
from analytics.strategy.evaluator import evaluate_spec as _evaluate_spec
from analytics.strategy.fitness import EvalMode, FitnessReport
from analytics.strategy.spec import (
    ENTRY_TYPES,
    INSTRUMENTS,
    REGIMES,
    TIMEFRAMES,
    StrategySpec,
    spec_summary,
)

logger = logging.getLogger("oracle.strategy.researcher")

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
DEFAULT_BASE = os.environ.get("LLM_BASE", "https://api.vsllm.com/v1")


@dataclass
class SpecResult:
    """Evaluation of one spec — wraps FitnessReport."""

    spec: StrategySpec
    report: FitnessReport
    error: str = ""

    @property
    def pass_rate(self) -> float:
        return self.report.mc_pass_rate or 0.0

    @property
    def sharpe(self) -> float:
        return self.report.sharpe or 0.0

    @property
    def return_pct(self) -> float:
        return (self.report.total_return or 0.0) * 100

    @property
    def fitness(self) -> float:
        return self.report.fitness


@dataclass
class ResearchLog:
    """Accumulated specs + results across rounds."""

    results: list[SpecResult] = field(default_factory=list)
    mode: EvalMode = EvalMode.FIRM

    def best(self) -> SpecResult | None:
        valid = [r for r in self.results if not r.error]
        return max(valid, key=lambda r: r.fitness) if valid else None

    def history_text(self, k: int = 8) -> str:
        valid = [r for r in self.results if not r.error]
        ranked = sorted(valid, key=lambda r: r.fitness, reverse=True)[:k]
        if not ranked:
            return "(none yet)"
        return "\n".join(
            spec_summary(r.spec, {"pass_rate": r.pass_rate, "sharpe": r.sharpe}) for r in ranked
        )


def evaluate_spec_with_registry(
    spec: StrategySpec, registry: DataRegistry, mode: EvalMode | str = EvalMode.FIRM, **kwargs: Any
) -> SpecResult:
    """Evaluate one spec via the unified R3 evaluator."""
    try:
        report = _evaluate_spec(spec, registry, mode, **kwargs)
        return SpecResult(spec=spec, report=report)
    except Exception as exc:
        logger.warning("researcher.eval_failed spec=%s error=%s", spec.name, exc)
        empty = FitnessReport(mode=EvalMode(mode), fitness=0.0)
        return SpecResult(spec=spec, report=empty, error=str(exc))


class LLMStrategyResearcher:
    """Proposes strategy specs via an OpenAI-compatible LLM endpoint."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_base: str = DEFAULT_BASE,
        api_key: str | None = None,
        temperature: float = 0.8,
    ) -> None:
        self.model = model
        self.api_base = api_base
        self.api_key = api_key or os.environ.get("LLM_KEY", "")
        self.temperature = temperature

    def propose(self, log: ResearchLog, n: int = 3) -> list[StrategySpec]:
        """Ask the LLM for ``n`` new strategy specs given the research history."""
        import litellm

        system = self._system_prompt()
        user = self._user_prompt(log, n)
        resp = litellm.completion(
            model=f"openai/{self.model}",
            api_base=self.api_base,
            api_key=self.api_key,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=self.temperature,
            max_tokens=2000,
        )
        text = resp["choices"][0]["message"]["content"]
        return _parse_specs(text, n)

    def _system_prompt(self) -> str:
        return (
            "You are a senior quantitative researcher optimizing a trading strategy to PASS "
            "a prop-firm challenge (The5ers: +10% profit target, 3% max daily loss, 6% max "
            "overall loss, static drawdown). The ONLY objective is maximizing the simulated "
            "challenge PASS-RATE under a rolling-window Monte Carlo (each window starts at a "
            "fresh balance; daily loss is measured intraday).\n\n"
            f"Instruments: {list(INSTRUMENTS)} (metals/cmdty/indices/FX/crypto).\n"
            f"Timeframes: {TIMEFRAMES} (1d ~2y history; 1h ~2y; 15m ~60d).\n"
            f"Regimes: {REGIMES} — 'fixed' = full notional (more return, more drawdown), "
            "'sized' = volatility-scaled per-trade (less drawdown, less return).\n"
            f"Entry rules: {list(ENTRY_TYPES)}. Params:\n"
            "  donchian_breakout(period), ema_trend(fast, slow), "
            "rsi_reversion(period, oversold, exit_level), bband_reversion(period, std), "
            "trend_filtered_breakout(period, ma_period), roc_momentum(period), "
            "zscore_reversion(period, entry_z), keltner_reversion(period, mult).\n"
            "Sizing (sized only): risk_pct (0.005-0.03), stop_atr_mult (1.5-3.0).\n\n"
            "Vary instruments, timeframes, regimes, entry rules, and params WIDELY. "
            "Prefer uncorrelated ideas. Note: shorter TFs + shorter lookbacks whipsaw more; "
            "'fixed' regime on a strong-trend instrument often passes more.\n\n"
            "Return STRICT JSON: a JSON ARRAY of objects with keys "
            "name, instrument, entry, entry_params, timeframe, regime, risk_pct, "
            "stop_atr_mult, rationale. No prose, no code fences — just the JSON array."
        )

    def _user_prompt(self, log: ResearchLog, n: int) -> str:
        best = log.best()
        best_line = (
            f"Current best: pass={best.pass_rate * 100:.0f}% sharpe={best.sharpe:.2f}"
            if best
            else "No baseline yet."
        )
        return (
            f"{best_line}\n\n"
            f"Recent results (ranked):\n{log.history_text()}\n\n"
            f"Propose {n} NEW, DIVERSE strategy specs that could beat the current best pass-rate. "
            "Vary instruments, entry rules, params, and sizing. Prefer uncorrelated ideas. "
            "Return only the JSON array."
        )


def _parse_specs(text: str, n: int) -> list[StrategySpec]:
    """Robustly extract StrategySpec objects from an LLM JSON response."""
    cleaned = re.sub(r"```(?:json)?|```", "", text, flags=re.MULTILINE).strip()
    starts = [i for i in (cleaned.find("["), cleaned.find("{")) if i >= 0]
    if not starts:
        return []
    cleaned = cleaned[min(starts) :]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # last-resort: balance braces
        end = max(cleaned.rfind("]"), cleaned.rfind("}"))
        try:
            data = json.loads(cleaned[: end + 1])
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        data = [data]
    specs: list[StrategySpec] = []
    for d in data:
        try:
            specs.append(StrategySpec(**d))
        except Exception:
            continue
    return specs[:n]


def run_research_rounds(
    researcher: LLMStrategyResearcher,
    registry: DataRegistry,
    rounds: int = 3,
    per_round: int = 3,
    mode: EvalMode | str = EvalMode.FIRM,
    log: ResearchLog | None = None,
) -> ResearchLog:
    """Iterate: propose -> evaluate -> record, for ``rounds`` rounds."""
    log = log or ResearchLog(mode=EvalMode(mode))
    for r in range(rounds):
        specs = researcher.propose(log, per_round)
        logger.info("researcher.round=%d proposed=%d", r + 1, len(specs))
        for spec in specs:
            log.results.append(evaluate_spec_with_registry(spec, registry, mode))
        best = log.best()
        if best:
            logger.info(
                "researcher.best_so_far round=%d name=%s pass_rate=%.3f",
                r + 1,
                best.spec.name,
                best.pass_rate,
            )
    return log
