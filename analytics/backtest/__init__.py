"""Backtesting — metrics, protocols, configuration, and data provider."""

from analytics.backtest.benchmarks import BenchmarkFactory
from analytics.backtest.bias import BiasCorrector
from analytics.backtest.config import BacktestConfig
from analytics.backtest.data import BacktestDataProvider
from analytics.backtest.engines import VectorizedEngine, sma_crossover_signal
from analytics.backtest.metrics import MetricsCalculator
from analytics.backtest.orchestrator import BacktestOrchestrator
from analytics.backtest.portfolio import BacktestPortfolio
from analytics.backtest.portfolio_opt import PortfolioOptimizer
from analytics.backtest.protocol import BacktestSignal
from analytics.backtest.result import BacktestResult

__all__ = [
    "BacktestConfig",
    "BacktestDataProvider",
    "BacktestOrchestrator",
    "BacktestPortfolio",
    "BacktestResult",
    "BacktestSignal",
    "BenchmarkFactory",
    "BiasCorrector",
    "MetricsCalculator",
    "PortfolioOptimizer",
    "VectorizedEngine",
    "sma_crossover_signal",
]
