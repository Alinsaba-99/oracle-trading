"""Dystopian stress testing — synthetic worst-case scenarios.

Step 5 Opzione C (2026-08-16). Extends the historical CrisisPeriod gauntlet
with two new stress-test types that go beyond what's ever happened
historically:

- **Type 2 — Synthetic Dystopian**: parametrically-generated scenarios worse
  than any historical regime: SPY -40% in 2 weeks, VIX spike to 100,
  liquidity collapse (spread 10× normal), 3 black-swan events in 6 months,
  stagflation (inflation 10% + recession -20% for 24 months). The point is
  to ask "what would break this strategy?" — and reject specs that break.

- **Type 3 — Adversarial Regime**: scan a grid of synthetic regime
  parameters (drift, vol, jump_intensity, jump_size, autocorrelation) and
  find the regime where this strategy has its worst Sharpe. If that
  worst-case Sharpe is below a threshold, the spec is fragile.

These tests are pure-Python — they don't need a data registry, they
generate synthetic price paths and run the spec's signal on them.

References
- López de Prado (2018) "Advances in Financial Machine Learning" ch.13
- Bailey, Borwein, López de Prado, Zhu (2017) "The Probability of
  Backtest Overfitting" — adversarial regime search
- Deep-research synthesis 2026-08-15 §3.6 (stress testing dystopico)
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger("oracle.strategy.dystopian")

# ---------------------------------------------------------------------------
# Synthetic price path generators
# ---------------------------------------------------------------------------


def _seed_rng(seed: int | None) -> np.random.Generator:
    """Deterministic RNG — we want reproducible stress scenarios."""
    return np.random.default_rng(seed)


def generate_gbm_path(
    n_days: int,
    start_price: float,
    annual_drift: float = 0.07,
    annual_vol: float = 0.15,
    trading_days_per_year: int = 252,
    seed: int | None = None,
) -> np.ndarray:
    """Geometric Brownian Motion price path.

    Standard Black-Scholes assumption (log-normal, no jumps). The base
    case for adversarial regime search — we generate many of these with
    different (drift, vol) parameters and find the worst regime for the
    strategy under test.
    """
    rng = _seed_rng(seed)
    dt = 1.0 / trading_days_per_year
    mu = annual_drift - 0.5 * annual_vol * annual_vol
    # Brownian increments
    z = rng.standard_normal(n_days)
    log_returns = mu * dt + annual_vol * math.sqrt(dt) * z
    log_prices = np.cumsum(log_returns) + math.log(start_price)
    return np.exp(log_prices)


def generate_jump_diffusion_path(
    n_days: int,
    start_price: float,
    annual_drift: float = 0.07,
    annual_vol: float = 0.15,
    jump_intensity_per_year: float = 5.0,
    jump_mean: float = -0.05,
    jump_std: float = 0.10,
    trading_days_per_year: int = 252,
    seed: int | None = None,
) -> np.ndarray:
    """Merton jump-diffusion: GBM + Poisson jumps with log-normal sizes.

    This is the realistic dystopian case — Black Monday 1987 was a -22%
    one-day move that GBM says should happen once in 10^50 years. Jump
    diffusion reproduces tail risk that GBM cannot.
    """
    rng = _seed_rng(seed)
    dt = 1.0 / trading_days_per_year
    mu = (
        annual_drift
        - 0.5 * annual_vol * annual_vol
        - jump_intensity_per_year * (math.exp(jump_mean + 0.5 * jump_std * jump_std) - 1.0)
    )
    z = rng.standard_normal(n_days)
    log_returns = mu * dt + annual_vol * math.sqrt(dt) * z
    # Poisson number of jumps per day
    n_jumps_per_day = rng.poisson(jump_intensity_per_year * dt, size=n_days)
    # Jump sizes: log-normal with mean jump_mean, std jump_std
    jump_log_sizes = rng.normal(loc=jump_mean, scale=jump_std, size=n_days)
    # Apply jumps
    jump_returns = np.where(n_jumps_per_day > 0, n_jumps_per_day * jump_log_sizes, 0.0)
    log_returns = log_returns + jump_returns
    log_prices = np.cumsum(log_returns) + math.log(start_price)
    return np.exp(log_prices)


def generate_crash_path(
    n_days: int,
    start_price: float,
    crash_day: int,
    crash_pct: float = -0.20,
    recovery_days: int = 30,
    recovery_pct: float = 0.50,
    seed: int | None = None,
) -> np.ndarray:
    """A synthetic crash with deterministic V-shape recovery.

    Used for COVID-2020-like or 1987-like scenarios where the crash is
    fast and the recovery is also fast. The strategy must survive both
    legs.
    """
    rng = _seed_rng(seed)
    prices = np.zeros(n_days)
    prices[0] = start_price
    for i in range(1, n_days):
        if i == crash_day:
            prices[i] = prices[i - 1] * (1.0 + crash_pct)
        elif crash_day < i <= crash_day + recovery_days:
            # Linear recovery of `recovery_pct` of the crash over `recovery_days`
            recovery_step = (abs(crash_pct) * recovery_pct) / recovery_days
            prices[i] = prices[i - 1] * (1.0 + recovery_step)
        else:
            # Tiny noise around flat
            prices[i] = prices[i - 1] * (1.0 + 0.0001 * rng.standard_normal())
    return prices


# ---------------------------------------------------------------------------
# Dystopian scenario definitions (Type 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DystopianScenario:
    """A synthetic worst-case stress scenario."""

    name: str
    n_days: int
    annual_drift: float
    annual_vol: float
    jump_intensity_per_year: float = 0.0
    jump_mean: float = 0.0
    jump_std: float = 0.0
    crash_day: int | None = None
    crash_pct: float = 0.0
    recovery_days: int = 0
    recovery_pct: float = 0.0
    note: str = ""
    seed: int = 42  # Deterministic for reproducibility

    def generate(self, start_price: float = 100.0) -> np.ndarray:
        """Generate the price path for this scenario."""
        if self.crash_day is not None:
            return generate_crash_path(
                n_days=self.n_days,
                start_price=start_price,
                crash_day=self.crash_day,
                crash_pct=self.crash_pct,
                recovery_days=self.recovery_days,
                recovery_pct=self.recovery_pct,
                seed=self.seed,
            )
        if self.jump_intensity_per_year > 0:
            return generate_jump_diffusion_path(
                n_days=self.n_days,
                start_price=start_price,
                annual_drift=self.annual_drift,
                annual_vol=self.annual_vol,
                jump_intensity_per_year=self.jump_intensity_per_year,
                jump_mean=self.jump_mean,
                jump_std=self.jump_std,
                seed=self.seed,
            )
        return generate_gbm_path(
            n_days=self.n_days,
            start_price=start_price,
            annual_drift=self.annual_drift,
            annual_vol=self.annual_vol,
            seed=self.seed,
        )


#: Curated dystopian scenarios — each one tests a specific failure mode.
DYSTOPIAN_SCENARIOS: tuple[DystopianScenario, ...] = (
    # COVID-2020 on steroids: -34% in 33 days was the historical worst;
    # we make it -40% in 14 days + fast V-recovery
    DystopianScenario(
        name="covid_extreme_2020_plus",
        n_days=252,
        annual_drift=0.0,
        annual_vol=0.40,
        crash_day=15,
        crash_pct=-0.40,
        recovery_days=30,
        recovery_pct=0.70,
        note="Worse than 2020 COVID: -40% in 2 weeks vs historical -34% in 33 days",
    ),
    # VIX spike to 100 (historical max: 89.53 in Mar 2020)
    DystopianScenario(
        name="vix_spike_100",
        n_days=126,
        annual_drift=-0.50,
        annual_vol=1.00,
        note="Implied vol at 100% annualised — VIX historical max was 89.53 (Mar 2020)",
    ),
    # Jump-diffusion: 10 jumps/year averaging -8% (1987 Black Monday had -22% one-day)
    DystopianScenario(
        name="jump_diffusion_1987_style",
        n_days=252,
        annual_drift=-0.10,
        annual_vol=0.25,
        jump_intensity_per_year=10.0,
        jump_mean=-0.08,
        jump_std=0.15,
        note="Frequent large-gap moves — worse than any single historical crash",
    ),
    # 3 black swans in 6 months (180 days)
    DystopianScenario(
        name="triple_black_swan_6mo",
        n_days=180,
        annual_drift=-0.20,
        annual_vol=0.30,
        jump_intensity_per_year=20.0,
        jump_mean=-0.10,
        jump_std=0.20,
        note="Three independent -10% gap events in 6 months — regime stacking",
    ),
    # Stagflation: inflation 10% + recession -20% for 24 months
    DystopianScenario(
        name="stagflation_24mo",
        n_days=252 * 2,
        annual_drift=-0.20,
        annual_vol=0.25,
        jump_intensity_per_year=4.0,
        jump_mean=-0.03,
        jump_std=0.05,
        note="Persistent stagflation: -20% drift + 4 small jumps/year over 24 months",
    ),
    # Choppy range-bound: trend-follower's worst nightmare
    DystopianScenario(
        name="choppy_range_2024_style",
        n_days=252,
        annual_drift=0.0,
        annual_vol=0.10,
        note="Low-vol choppy range — kills trend-following via whipsaw losses",
    ),
    # Extreme vol + zero drift — pure noise, no edge
    DystopianScenario(
        name="pure_noise_high_vol",
        n_days=252,
        annual_drift=0.0,
        annual_vol=0.80,
        note="Pure noise at 80% vol — strategy must not hallucinate edge from randomness",
    ),
)


# ---------------------------------------------------------------------------
# Adversarial regime search (Type 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdversarialRegimeGrid:
    """Grid of regime parameters to search for worst-case Sharpe."""

    drifts: tuple[float, ...] = (-0.30, -0.10, 0.0, 0.10, 0.30)
    vols: tuple[float, ...] = (0.05, 0.15, 0.30, 0.50, 0.80)
    jump_intensities: tuple[float, ...] = (0.0, 5.0, 20.0)
    jump_means: tuple[float, ...] = (-0.10, -0.05, 0.0)
    n_days_per_scenario: int = 252
    seed: int = 42


@dataclass
class AdversarialRegimeResult:
    """Result of one regime-spec combination."""

    drift: float
    vol: float
    jump_intensity: float
    jump_mean: float
    sharpe: float
    total_return: float
    max_drawdown: float
    n_trades: int


@dataclass
class AdversarialReport:
    """Worst-case regime found for a strategy."""

    worst_regime: AdversarialRegimeResult | None = None
    best_regime: AdversarialRegimeResult | None = None
    median_sharpe: float = 0.0
    n_scenarios: int = 0
    fragility_score: float = 0.0  # 0 = robust, 1 = extremely fragile
    all_results: list[AdversarialRegimeResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Metrics on synthetic paths
# ---------------------------------------------------------------------------


def compute_synthetic_metrics(
    prices: np.ndarray,
    signal_func: Callable[[np.ndarray], np.ndarray],  # -> positions in [-1, 1]
    trading_days_per_year: int = 252,
) -> dict[str, float]:
    """Compute Sharpe, return, max DD on a synthetic path with a signal.

    ``signal_func`` takes the price array and returns a position array of
    the same length. Position can be fractional (e.g. 0.5 = half-size long).
    Returns are daily. Sharpe annualised assuming 252 trading days/year.
    """
    if len(prices) < 2:
        return {"sharpe": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "n_trades": 0}
    positions = signal_func(prices)
    if len(positions) != len(prices):
        raise ValueError(
            f"signal_func must return array of same length as prices: "
            f"got {len(positions)} vs {len(prices)}"
        )
    # Daily asset returns
    asset_rets = np.diff(prices) / prices[:-1]
    # Strategy returns: position_t * return_{t+1}
    strat_rets = positions[:-1] * asset_rets
    # Metrics
    n = len(strat_rets)
    if n == 0:
        return {"sharpe": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "n_trades": 0}
    mean_r = float(np.mean(strat_rets))
    std_r = float(np.std(strat_rets, ddof=1)) if n > 1 else 0.0
    sharpe = (mean_r / std_r) * math.sqrt(trading_days_per_year) if std_r > 0 else 0.0
    # Equity curve
    equity = np.cumprod(1.0 + strat_rets)
    total_return = float(equity[-1] - 1.0)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / np.where(peak > 0, peak, 1.0)
    max_dd = float(-np.min(dd)) if dd.size > 0 else 0.0
    # Trade count = number of position changes
    n_trades = int(np.sum(np.abs(np.diff(positions)) > 0))
    return {
        "sharpe": sharpe,
        "total_return": total_return,
        "max_drawdown": max_dd,
        "n_trades": n_trades,
    }


# ---------------------------------------------------------------------------
# Top-level runners
# ---------------------------------------------------------------------------


@dataclass
class DystopianReport:
    """Result of running a strategy across all dystopian scenarios."""

    scenario_results: dict[str, dict[str, float]] = field(default_factory=dict)
    survival_rate: float = 0.0
    worst_scenario: str = ""
    worst_sharpe: float = 0.0
    worst_max_drawdown: float = 0.0
    passed: bool = False
    failures: list[str] = field(default_factory=list)


def run_dystopian(
    signal_func: Callable[[np.ndarray], np.ndarray],
    scenarios: tuple[DystopianScenario, ...] = DYSTOPIAN_SCENARIOS,
    *,
    min_sharpe: float = -0.5,
    max_drawdown_threshold: float = 0.50,
) -> DystopianReport:
    """Run a signal function across all dystopian scenarios.

    A spec "passes" if it survives ALL scenarios with:
    - Sharpe > min_sharpe (allow small losses in dystopian regimes)
    - Max drawdown < max_drawdown_threshold (50% default — extreme but
      we're testing survival, not profitability)

    The point is to find the breaking point, not the average performance.
    """
    report = DystopianReport()
    for scenario in scenarios:
        prices = scenario.generate(start_price=100.0)
        metrics = compute_synthetic_metrics(prices, signal_func)
        report.scenario_results[scenario.name] = metrics
        if metrics["sharpe"] < min_sharpe:
            report.failures.append(
                f"{scenario.name}: Sharpe {metrics['sharpe']:.2f} < {min_sharpe}"
            )
        if metrics["max_drawdown"] > max_drawdown_threshold:
            report.failures.append(
                f"{scenario.name}: Max DD {metrics['max_drawdown']:.1%} > {max_drawdown_threshold:.0%}"
            )

    # Worst-case summary
    sharpes = [(name, m["sharpe"]) for name, m in report.scenario_results.items()]
    dds = [(name, m["max_drawdown"]) for name, m in report.scenario_results.items()]
    if sharpes:
        report.worst_scenario = min(sharpes, key=lambda x: x[1])[0]
        report.worst_sharpe = min(s for _, s in sharpes)
        report.worst_max_drawdown = max(d for _, d in dds)
        # Survival = fraction of scenarios without failure
        n_failed_scenarios = len({f.split(":")[0] for f in report.failures})
        report.survival_rate = 1.0 - n_failed_scenarios / len(scenarios)

    report.passed = len(report.failures) == 0
    return report


def run_adversarial_regime_search(
    signal_func: Callable[[np.ndarray], np.ndarray], grid: AdversarialRegimeGrid | None = None
) -> AdversarialReport:
    """Find the regime where the strategy has its worst Sharpe.

    Scans a grid of (drift, vol, jump_intensity, jump_mean) parameters
    and reports the worst-case. A robust strategy has a high worst-case
    Sharpe; a fragile one breaks.
    """
    grid = grid or AdversarialRegimeGrid()
    results: list[AdversarialRegimeResult] = []
    for drift in grid.drifts:
        for vol in grid.vols:
            for j_int in grid.jump_intensities:
                for j_mean in grid.jump_means:
                    if j_int > 0:
                        prices = generate_jump_diffusion_path(
                            n_days=grid.n_days_per_scenario,
                            start_price=100.0,
                            annual_drift=drift,
                            annual_vol=vol,
                            jump_intensity_per_year=j_int,
                            jump_mean=j_mean,
                            seed=grid.seed,
                        )
                    else:
                        prices = generate_gbm_path(
                            n_days=grid.n_days_per_scenario,
                            start_price=100.0,
                            annual_drift=drift,
                            annual_vol=vol,
                            seed=grid.seed,
                        )
                    m = compute_synthetic_metrics(prices, signal_func)
                    results.append(
                        AdversarialRegimeResult(
                            drift=drift,
                            vol=vol,
                            jump_intensity=j_int,
                            jump_mean=j_mean,
                            sharpe=m["sharpe"],
                            total_return=m["total_return"],
                            max_drawdown=m["max_drawdown"],
                            n_trades=int(m["n_trades"]),
                        )
                    )
    if not results:
        return AdversarialReport()
    sharpes = [r.sharpe for r in results]
    worst = min(results, key=lambda r: r.sharpe)
    best = max(results, key=lambda r: r.sharpe)
    median_sharpe = float(np.median(sharpes))
    # Fragility score: 0 if worst-case Sharpe is at median, 1 if worst-case is in bottom 5%
    fragility = 0.0
    if worst.sharpe < median_sharpe:
        # Distance from median, normalised
        spread = max(abs(median_sharpe), 1e-6)
        fragility = min(1.0, (median_sharpe - worst.sharpe) / spread)
    return AdversarialReport(
        worst_regime=worst,
        best_regime=best,
        median_sharpe=median_sharpe,
        n_scenarios=len(results),
        fragility_score=fragility,
        all_results=results,
    )


__all__ = [
    "DYSTOPIAN_SCENARIOS",
    "AdversarialRegimeGrid",
    "AdversarialRegimeResult",
    "AdversarialReport",
    "DystopianReport",
    "DystopianScenario",
    "compute_synthetic_metrics",
    "generate_crash_path",
    "generate_gbm_path",
    "generate_jump_diffusion_path",
    "run_adversarial_regime_search",
    "run_dystopian",
]
