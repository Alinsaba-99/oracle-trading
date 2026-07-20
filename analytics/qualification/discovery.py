"""Discovery-only replay runner used to bootstrap M31 evidence."""

from __future__ import annotations

from math import isfinite
from time import perf_counter

import polars as pl

from analytics.backtest.challenge_intraday import run_intraday
from analytics.backtest.config import BacktestConfig
from analytics.backtest.engines.vectorized import VectorizedEngine
from analytics.backtest.protocol import BacktestSignal
from analytics.qualification.models import (
    ReplayMetrics,
    ReplayObservation,
    ReplayPeriod,
    ReplayVariant,
)
from analytics.qualification.statistics import (
    bootstrap_luck_p_value,
    factor_attribution,
    returns_from_values,
)
from policy.prop_firm.profile import PropFirmProfile


class DiscoveryReplayRunner:
    """Run signal-only vectorized replay without claiming qualification."""

    def __init__(
        self, signal: BacktestSignal, config: BacktestConfig, prop_profile: PropFirmProfile
    ) -> None:
        self._signal = signal
        self._config = config
        self._prop_profile = prop_profile

    @staticmethod
    def supports(variant: ReplayVariant) -> bool:
        """Return whether the discovery runner can execute a variant honestly."""
        return variant == ReplayVariant.control()

    def run(
        self, data: pl.DataFrame, period: ReplayPeriod, variant: ReplayVariant
    ) -> ReplayObservation:
        """Run net and zero-cost discovery backtests for one period."""
        if not self.supports(variant):
            raise ValueError(f"Discovery runner cannot execute intelligence variant {variant.name}")
        if data.height < 3:
            raise ValueError("Replay period requires at least three bars")

        started = perf_counter()
        net_result = VectorizedEngine().run(data, self._signal, self._config)
        gross_config = self._config.model_copy(update={"slippage_bps": 0.0, "commission_pct": 0.0})
        gross_result = VectorizedEngine().run(data, self._signal, gross_config)
        engine_runtime_ms = (perf_counter() - started) * 1000.0

        timestamps = data["timestamp"].to_list()
        challenge = run_intraday(
            self._prop_profile,
            float(self._config.initial_capital),
            net_result.equity_curve,
            timestamps,
        )
        hard_breaches = sum(breach.severity == "hard" for breach in challenge.breaches)
        soft_breaches = sum(breach.severity == "soft" for breach in challenge.breaches)

        strategy_returns = returns_from_values(net_result.equity_curve)
        market_returns = returns_from_values(data["close"].to_list())
        attribution = factor_attribution(strategy_returns, market_returns)
        luck_p_value = bootstrap_luck_p_value(strategy_returns)

        initial_capital = float(self._config.initial_capital)
        execution_cost = max(gross_result.final_equity - net_result.final_equity, 0.0)
        execution_cost_ratio = execution_cost / initial_capital if initial_capital else 0.0
        turnover_notional = sum(
            float(abs(trade.quantity * trade.entry_price)) for trade in net_result.trades
        )
        turnover = turnover_notional / initial_capital if initial_capital else 0.0

        metrics = ReplayMetrics(
            net_return=net_result.total_return,
            sharpe_ratio=_finite_or_none(net_result.sharpe_ratio),
            sortino_ratio=_finite_or_none(net_result.sortino_ratio),
            calmar_ratio=_finite_or_none(net_result.calmar_ratio),
            max_drawdown=net_result.max_drawdown,
            hard_breaches=hard_breaches,
            soft_breaches=soft_breaches,
            turnover=turnover,
            execution_cost=execution_cost,
            execution_cost_ratio=execution_cost_ratio,
            model_cost_usd=0.0,
            decision_latency_ms_p95=None,
            factor_attribution=attribution,
            luck_p_value=luck_p_value,
            total_trades=net_result.total_trades,
            bars=data.height,
            engine_runtime_ms=engine_runtime_ms,
        )
        return ReplayObservation(
            period_name=period.name,
            regime=period.regime,
            variant_name=variant.name,
            engine="vectorized",
            component_path="signal-only-discovery",
            metrics=metrics,
            warnings=[
                "Vectorized discovery is not the certified event-driven qualification engine.",
                (
                    "This path does not exercise the mandatory risk gate, OMS, ledger, "
                    "or reconciliation."
                ),
                "Decision latency is not measured by the vectorized batch runner.",
            ],
        )


def _finite_or_none(value: float) -> float | None:
    numeric = float(value)
    return numeric if isfinite(numeric) else None
