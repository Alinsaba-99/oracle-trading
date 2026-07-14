"""LLM strategy researcher — Modo A.

The LLM acts as a quant researcher: given the current best candidate and
the history of tried specs + their Monte-Carlo results, it proposes new
:class:`StrategySpec` objects.  The machine deterministically builds,
backtests (sized), and Monte-Carlo evaluates each.  The LLM never runs
code or places orders — it only fills the validated spec DSL.

LLM access is via an OpenAI-compatible endpoint (litellm).  Configure with
env: ``LLM_BASE``, ``LLM_KEY``, ``LLM_MODEL`` (see ``.env.example``).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import structlog

from analytics.backtest.fx_data import fetch_ohlcv
from analytics.strategy.evaluation import monte_carlo_calendar_windows
from analytics.strategy.metrics_enrich import recompute_metrics
from analytics.strategy.risk_sized import sized_backtest
from analytics.strategy.spec import (
    ENTRY_TYPES,
    INSTRUMENTS,
    REGIMES,
    TIMEFRAMES,
    StrategySpec,
    spec_summary,
)
from policy.prop_firm import THE5ERS

logger = structlog.get_logger("oracle.strategy.researcher")

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
DEFAULT_BASE = os.environ.get("LLM_BASE", "https://api.vsllm.com/v1")


@dataclass
class SpecResult:
    """Evaluation of one spec."""

    spec: StrategySpec
    pass_rate: float
    sharpe: float
    return_pct: float
    fail_d: float
    fail_o: float
    n_windows: int
    error: str = ""


@dataclass
class ResearchLog:
    """Accumulated specs + results across rounds."""

    results: list[SpecResult] = field(default_factory=list)

    def best(self) -> SpecResult | None:
        valid = [r for r in self.results if not r.error]
        return max(valid, key=lambda r: r.pass_rate) if valid else None

    def history_text(self, k: int = 8) -> str:
        valid = [r for r in self.results if not r.error]
        ranked = sorted(valid, key=lambda r: r.pass_rate, reverse=True)[:k]
        if not ranked:
            return "(none yet)"
        return "\n".join(spec_summary(r.spec, r.__dict__) for r in ranked)


#: yfinance period per timeframe (longest history each serves).
PERIOD_BY_TF: dict[str, str] = {"1d": "2y", "1h": "730d", "15m": "60d"}


def evaluate_spec(spec: StrategySpec, period: str | None = None) -> SpecResult:
    """Build + backtest + Monte-Carlo evaluate one spec (multi-timeframe)."""
    try:
        tf = spec.timeframe if spec.timeframe in PERIOD_BY_TF else "1d"
        period = period or PERIOD_BY_TF[tf]
        data = fetch_ohlcv(spec.ticker(), period=period, interval=tf)
        if data.is_empty():
            raise ValueError(f"no data for {spec.ticker()}")
        signal = spec.build_signal()

        if spec.regime == "fixed":
            from analytics.backtest.orchestrator import BacktestOrchestrator

            result = recompute_metrics(
                BacktestOrchestrator().run(
                    signal, engine="vectorized", instrument_id=spec.instrument, data=data
                )
            )
        else:
            result = recompute_metrics(
                sized_backtest(
                    data,
                    signal,
                    spec.instrument,
                    risk_pct=spec.risk_pct,
                    stop_atr_mult=spec.stop_atr_mult,
                )
            )

        # Calendar-window MC (works for 1d / 1h / 15m via real day-rollover).
        equity = result.equity_curve
        dates = [t.date() for t in data["timestamp"].to_list()][: len(equity)]
        unique_days = len(set(dates))
        window_days = min(60, max(20, unique_days // 3))
        stride_days = max(1, window_days // 10)
        mc = monte_carlo_calendar_windows(
            dates, equity, THE5ERS, window_days=window_days, stride_days=stride_days
        )
        return SpecResult(
            spec=spec,
            pass_rate=mc.pass_rate,
            sharpe=result.sharpe_ratio,
            return_pct=result.total_return * 100,
            fail_d=mc.failed_daily_rate,
            fail_o=mc.failed_overall_rate,
            n_windows=mc.total,
        )
    except Exception as exc:
        logger.warning("researcher.eval_failed", spec=spec.name, error=str(exc))
        return SpecResult(spec, 0.0, 0.0, 0.0, 0.0, 0.0, 0, error=str(exc))


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
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
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
    cleaned = cleaned[min(starts):]
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
    rounds: int = 3,
    per_round: int = 3,
    log: ResearchLog | None = None,
) -> ResearchLog:
    """Iterate: propose -> evaluate -> record, for ``rounds`` rounds."""
    log = log or ResearchLog()
    for r in range(rounds):
        specs = researcher.propose(log, per_round)
        logger.info("researcher.round", round=r + 1, proposed=len(specs))
        for spec in specs:
            log.results.append(evaluate_spec(spec))
        best = log.best()
        if best:
            logger.info(
                "researcher.best_so_far",
                round=r + 1,
                name=best.spec.name,
                pass_rate=round(best.pass_rate, 3),
            )
    return log
