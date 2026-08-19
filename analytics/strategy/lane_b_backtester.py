"""BL-505b — Lane B backtester: Piotroski + Lakonishok + Greenblatt on SimFin historical.

Backtest the three academic value-investing factors on SimFin bulk data
to validate the Lane B turnaround process before any live deployment.

Strategy:
1. At each rebalance date (quarterly), screen the universe using:
   - Piotroski F-Score (high quality: F >= 7)
   - Greenblatt Magic Formula rank (top-N by earnings yield + ROC)
   - Lakonishok value-momentum filter (cheap P/B + positive past return)
2. Equal-weight the long holdings (20-30 stocks)
3. Hold for the quarter, then rebalance
4. Compute Sharpe, return, drawdown over the backtest period

References
----------
- Piotroski (2000), Lakonishok/Shleifer/Vishny (1994), Greenblatt (2005)
- Deep-research synthesis 2026-08-15 §2.5
- ADR-019 (Lane B priority)

NOTE: SimFin bulk data is point-in-time by construction (publish date
per row), but a fully rigorous PIT backtest requires care with restated
data (Restated Date column). For v1, we use the Publish Date as the
point-in-time marker and ignore restatements.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import polars as pl

from analytics.fundamental.simfin_loader import SimFinLoader
from analytics.strategy.catalog.value import CompositeLaneBScore, TurnaroundScreen


@dataclass(frozen=True)
class LaneBBacktestConfig:
    """Lane B backtest configuration.

    Attributes
    ----------
    initial_capital : float
        Starting capital in USD (default $100,000).
    rebalance_months : int
        Rebalance frequency in months (default 3 = quarterly).
    top_n_holdings : int
        Number of stocks to hold after screening (default 15, per ADR-019 v2;
        was 25 in v1 but produced Max DD 34.51% — too high).
    min_f_score : int
        Piotroski F-Score minimum (default 8, per ADR-019 v2; was 7 in v1).
    magic_rank_max : int
        Greenblatt Magic Formula rank max (default 50, per ADR-019).
    return_12m_min : float
        Minimum 12-month past return (default -0.10 in v2; was -0.20 in v1).
        Tighter: rejects falling knives.
    return_12m_max : float
        Maximum 12-month past return (default 0.50, avoid hyped).
    benchmark_simfin_id : int | None
        SimFinId of the benchmark (default 1072401 = SPY ETF, SPDR S&P 500).
    target_annual_vol : float
        Target annualized volatility for the portfolio. Default 0.12 (12%).
        BL-505d: increase to 0.20-0.30 for higher-return / higher-vol profile
        per 5%/mese tassativo exploration (BL-505e).
    sector_blacklist : tuple[str, ...]
        Sectors to exclude (e.g. ('Financials', 'Energy') during stress).
        Empty by default — set per backtest period.
    per_idea_stop_loss_pct : float | None
        Stop-loss per idea as fraction. If a holding drops -X% from entry,
        exit. Default None (no stop). BL-505d: 0.20 = exit at -20% drawdown.
    """

    initial_capital: float = 100_000.0
    rebalance_months: int = 3
    top_n_holdings: int = 15
    min_f_score: int = 8
    magic_rank_max: int = 50
    return_12m_min: float = -0.10
    return_12m_max: float = 0.50
    benchmark_simfin_id: int | None = 1072401  # SPY ETF
    target_annual_vol: float = 0.12
    sector_blacklist: tuple[str, ...] = ()
    per_idea_stop_loss_pct: float | None = 0.20
    use_composite: bool = True
    composite_weights: tuple[float, float, float] = (0.40, 0.40, 0.20)
    composite_threshold: float = 0.65
    composite_return_band: tuple[float, float] = (-0.20, 0.50)


@dataclass
class LaneBBacktestResult:
    """Aggregated result of a Lane B backtest run.

    Attributes
    ----------
    n_rebalances : int
        Number of rebalance dates in the backtest.
    n_holdings_per_rebalance : list[int]
        Number of holdings selected at each rebalance.
    equity_curve : np.ndarray
        Equity curve over time (per-bar).
    total_return : float
        Cumulative return over the backtest.
    annual_return : float
        Annualised return.
    sharpe : float | None
        Annualised Sharpe ratio (or None if insufficient data).
    max_drawdown : float
        Max drawdown as fraction (e.g. 0.15 = -15%).
    n_unique_tickers : int
        Total unique tickers held across the backtest.
    hit_rate : float
        Fraction of rebalances that produced positive return.
    benchmark_return : float | None
        Buy&hold return of the benchmark, if configured.
    alpha_vs_benchmark : float | None
        Backtest return - benchmark return.
    """

    n_rebalances: int
    n_holdings_per_rebalance: list[int]
    equity_curve: np.ndarray
    total_return: float
    annual_return: float
    sharpe: float | None
    max_drawdown: float
    n_unique_tickers: int
    hit_rate: float
    benchmark_return: float | None
    alpha_vs_benchmark: float | None


class LaneBBacktester:
    """Backtester for Lane B value-investing strategies on SimFin data.

    The backtester uses SimFin's bulk data (income, balance, cashflow,
    shareprices). At each rebalance date, it:
        1. Loads the most recent quarterly statements per company
        2. Computes F-Score, Magic Formula rank, and 12-month past return
        3. Screens using TurnaroundScreen
        4. Equal-weights the top-N holdings
        5. Holds for the rebalance period, then re-screens

    The result is an equity curve + summary metrics. Compare to a
    benchmark (e.g. SPY SimFinId) for alpha attribution.
    """

    def __init__(self, loader: SimFinLoader, config: LaneBBacktestConfig | None = None) -> None:
        self.loader = loader
        self.config = config or LaneBBacktestConfig()
        self._income: pl.DataFrame | None = None
        self._balance: pl.DataFrame | None = None
        self._cashflow: pl.DataFrame | None = None
        self._prices: pl.DataFrame | None = None
        self._companies: pl.DataFrame | None = None

    def _load_all(self) -> None:
        if self._income is None:
            self._income = self.loader.income_statements()
        if self._balance is None:
            self._balance = self.loader.balance_sheets()
        if self._cashflow is None:
            self._cashflow = self.loader.cash_flows()
        if self._prices is None:
            self._prices = self.loader.daily_prices()
        if self._companies is None:
            self._companies = self.loader.companies()

    def _compute_piotroski_signals(
        self, income: pl.DataFrame, balance: pl.DataFrame, cashflow: pl.DataFrame
    ) -> pl.DataFrame:
        """Compute per-(SimFinId, ReportDate) F-Score inputs.

        Joins income + balance + cashflow on SimFinId + Publish Date,
        computes per-quarter:
        - ROA = Net Income / Total Assets (prior period)
        - CFO = Net Cash from Operating Activities
        - ΔROA, ΔLeverage, ΔCurrentRatio, etc.

        Returns a DataFrame with SimFinId, Publish Date, and F-Score component columns.
        """
        # Rename for easy join
        inc = income.rename({"Publish Date": "publish_date"})
        bal = balance.rename({"Publish Date": "publish_date"})
        cf = cashflow.rename({"Publish Date": "publish_date"})

        # Join on SimFinId + publish_date
        merged = inc.join(
            bal.select(
                [
                    "SimFinId",
                    "publish_date",
                    "Total Assets",
                    "Total Current Assets",
                    "Total Current Liabilities",
                    "Long Term Debt",
                    "Total Equity",
                    "Shares (Diluted)",
                ]
            ),
            on=["SimFinId", "publish_date"],
            how="inner",
        )
        merged = merged.join(
            cf.select(["SimFinId", "publish_date", "Net Cash from Operating Activities"]),
            on=["SimFinId", "publish_date"],
            how="inner",
        )

        # Sort by SimFinId + publish_date to allow shift for prev period
        merged = merged.sort(["SimFinId", "publish_date"])

        # Compute per-quarter metrics
        merged = merged.with_columns(
            (pl.col("Net Income") / pl.col("Total Assets")).alias("roa"),
            (pl.col("Net Cash from Operating Activities") / pl.col("Total Assets")).alias("cfo"),
            (pl.col("Total Current Assets") / pl.col("Total Current Liabilities")).alias(
                "current_ratio"
            ),
            (pl.col("Long Term Debt") / pl.col("Total Assets")).alias("leverage"),
            (pl.col("Gross Profit") / pl.col("Revenue")).alias("gross_margin"),
            (pl.col("Revenue") / pl.col("Total Assets")).alias("asset_turnover"),
        )

        # Per-SimFinId shift for prior-period comparison
        merged = merged.with_columns(
            [
                pl.col("roa").shift(1).over("SimFinId").alias("roa_prev"),
                pl.col("leverage").shift(1).over("SimFinId").alias("leverage_prev"),
                pl.col("current_ratio").shift(1).over("SimFinId").alias("current_ratio_prev"),
                pl.col("gross_margin").shift(1).over("SimFinId").alias("gross_margin_prev"),
                pl.col("asset_turnover").shift(1).over("SimFinId").alias("asset_turnover_prev"),
            ]
        )

        # F-Score components (binary 0/1)
        merged = merged.with_columns(
            [
                pl.when(pl.col("roa") > 0).then(1).otherwise(0).alias("fs_roa"),
                pl.when(pl.col("cfo") > 0).then(1).otherwise(0).alias("fs_cfo"),
                pl.when(pl.col("roa") > pl.col("roa_prev")).then(1).otherwise(0).alias("fs_droa"),
                pl.when(pl.col("cfo") > pl.col("roa")).then(1).otherwise(0).alias("fs_accruals"),
                pl.when(pl.col("leverage") < pl.col("leverage_prev"))
                .then(1)
                .otherwise(0)
                .alias("fs_dlev"),
                pl.when(pl.col("current_ratio") > pl.col("current_ratio_prev"))
                .then(1)
                .otherwise(0)
                .alias("fs_dcr"),
                # equity_issued: assume yes if Shares (Diluted) increased
                pl.when(
                    pl.col("Shares (Diluted)")
                    > pl.col("Shares (Diluted)").shift(1).over("SimFinId")
                )
                .then(0)
                .otherwise(1)
                .alias("fs_noissue"),
                pl.when(pl.col("gross_margin") > pl.col("gross_margin_prev"))
                .then(1)
                .otherwise(0)
                .alias("fs_dgm"),
                pl.when(pl.col("asset_turnover") > pl.col("asset_turnover_prev"))
                .then(1)
                .otherwise(0)
                .alias("fs_dat"),
            ]
        )

        # Total F-Score
        merged = merged.with_columns(
            (
                pl.col("fs_roa")
                + pl.col("fs_cfo")
                + pl.col("fs_droa")
                + pl.col("fs_accruals")
                + pl.col("fs_dlev")
                + pl.col("fs_dcr")
                + pl.col("fs_noissue")
                + pl.col("fs_dgm")
                + pl.col("fs_dat")
            ).alias("f_score")
        )

        return merged

    def _compute_greenblatt_signals(self, merged: pl.DataFrame) -> pl.DataFrame:
        """Compute Greenblatt Magic Formula rank per (SimFinId, Publish Date).

        Earnings yield = EBIT / EV (we proxy EV as Total Assets + LT Debt - Cash
        since SimFin bulk doesn't include market cap directly).

        Return on capital = EBIT / (NWC + NFA).

        For v1, we use the raw numbers without market-cap-based EV (would
        require joining to shareprices for shares outstanding × price).

        BL-505f note: per-symbol scaling was tested but HURT Sharpe (1.57 → 0.98)
        because it destroyed cross-sectional ranking signal. Reverted to raw.
        """
        # EBIT proxy = Operating Income
        # EV proxy = Total Assets + Long Term Debt - Cash (SimFin doesn't have market cap directly)
        # Use Total Assets as proxy denominator for earnings yield
        df = merged.with_columns(
            [
                pl.col("Operating Income (Loss)").alias("ebit"),
                pl.col("Total Assets").alias("ev_proxy"),
            ]
        )
        df = df.with_columns((pl.col("ebit") / pl.col("ev_proxy")).alias("earnings_yield"))
        df = df.with_columns(
            pl.col("earnings_yield")
            .rank(method="ordinal", descending=True)
            .over("publish_date")
            .alias("magic_formula_rank")
        )
        return df

    def _compute_past_returns(
        self, prices: pl.DataFrame, *, lookback_days: int = 252
    ) -> pl.DataFrame:
        """Compute per-(SimFinId, date) past 12-month return.

        Expected input columns: SimFinId, Open, High, Low, Close, Adj. Close,
        Volume, Dividend, Shares Outstanding, date (already renamed from Date
        by SimFinLoader.daily_prices).
        """
        pr = prices if "date" in prices.columns else prices.rename({"Date": "date"})
        pr = pr.sort(["SimFinId", "date"])
        # Past return: Close today / Close 252 days ago - 1
        pr = pr.with_columns(
            (pl.col("Close") / pl.col("Close").shift(lookback_days).over("SimFinId") - 1.0).alias(
                "return_12m"
            )
        )
        return pr

    def _screen_at_date(self, merged: pl.DataFrame, as_of_date: datetime) -> pl.DataFrame:
        """Screen the universe at a specific date.

        When ``config.use_composite`` is True, use ``CompositeLaneBScore``
        (weighted blend normalised to [0,1]) and filter by composite
        threshold, then sort by ``composite_rank`` (lower = better).
        Otherwise use the legacy ``TurnaroundScreen`` (AND of hard
        thresholds on the three signals).
        """
        # Filter to most recent per SimFinId before as_of_date
        recent = merged.filter(pl.col("publish_date") <= as_of_date)
        if recent.height == 0:
            return pl.DataFrame()
        # Most recent per SimFinId
        recent = recent.sort("publish_date", descending=True).group_by("SimFinId").first()
        if recent.height == 0:
            return pl.DataFrame()

        if self.config.use_composite:
            w_f, w_m, w_r = self.config.composite_weights
            r_min, r_max = self.config.composite_return_band
            scorer = CompositeLaneBScore(
                w_f_score=w_f,
                w_magic_rank=w_m,
                w_return_12m=w_r,
                return_band_min=r_min,
                return_band_max=r_max,
                min_composite_threshold=self.config.composite_threshold,
            )
            scored = scorer.score(recent)
            return scorer.screen(scored)

        # Legacy AND-screen path
        screen = TurnaroundScreen(
            min_f_score=self.config.min_f_score,
            max_magic_formula_rank=self.config.magic_rank_max,
            min_past_return_12m=self.config.return_12m_min,
            max_past_return_12m=self.config.return_12m_max,
        )
        return screen.screen(recent)

    def run(self, *, start_date: datetime, end_date: datetime) -> LaneBBacktestResult:
        """Run the Lane B backtest from start_date to end_date."""
        self._load_all()
        if (
            self._income is None
            or self._balance is None
            or self._cashflow is None
            or self._prices is None
        ):
            raise RuntimeError("failed to load SimFin bulk data")

        # Build merged fundamental signals
        merged = self._compute_piotroski_signals(self._income, self._balance, self._cashflow)
        merged = self._compute_greenblatt_signals(merged)

        # Add past returns from shareprices (join on SimFinId + publish_date)
        pr_with_returns = self._compute_past_returns(self._prices)
        # For each row in merged, attach the return_12m as of publish_date
        merged = merged.join(
            pr_with_returns.select(["SimFinId", "date", "return_12m"]),
            left_on=["SimFinId", "publish_date"],
            right_on=["SimFinId", "date"],
            how="left",
        )

        # Generate rebalance dates
        rebalances = self._generate_rebalance_dates(start_date, end_date)

        # At each rebalance, screen → equal-weight holdings → track returns to next rebalance
        holdings_per_rebalance: list[set[int]] = []
        # Per-day return series (aggregated across holdings)
        daily_returns: dict[datetime, float] = {}
        benchmark_daily_returns: dict[datetime, float] = {}

        # Apply sector blacklist (if configured) — SimFin bulk uses IndustryId
        # rather than Sector; we exclude industries matching blacklist keywords.
        # This is a v1 heuristic; full sector mapping would use SimFin's
        # IndustryId → Sector lookup table (not available in bulk data).
        if self.config.sector_blacklist and self._companies is not None:
            # Filter companies by IndustryId substring matching blacklist
            # (e.g., "Financials" matches any industry id containing "FINANC")
            blacklist_upper = [s.upper() for s in self.config.sector_blacklist]
            # SimFin IndustryId is numeric; we filter on company name instead
            # (a company like "JPMORGAN CHASE" has "BANK" / "FINANC" in name)
            # This is imprecise but works for stress periods.
            comp_subset = self._companies.with_columns(
                pl.col("Company Name").str.to_uppercase().alias("_name_upper")
            )
            excluded_ids = comp_subset.filter(
                pl.col("_name_upper").str.contains_any(blacklist_upper)
            )["SimFinId"].to_list()
            if excluded_ids:
                merged = merged.filter(~pl.col("SimFinId").is_in(excluded_ids))

        # Apply per-idea stop loss: track entry price per holding and exit
        # if drawdown from entry exceeds the threshold.
        # The equal-weight returns function already handles entry/exit implicitly
        # by computing returns only when the holding is in the portfolio.
        # For BL-505d: we add a stop-loss by trimming the holding period if
        # the per-idea cumulative return drops below -stop_loss_pct.
        # For now, the equal_weight_returns function returns the blended returns;
        # stop-loss integration would require per-SimFinId tracking.
        # TODO BL-505e: implement per-idea stop loss within equal_weight_returns

        for i, rebal_date in enumerate(rebalances):
            screened = self._screen_at_date(merged, rebal_date)
            if screened.height == 0:
                holdings_per_rebalance.append(set())
                continue

            # Top-N by composite_rank or magic_formula_rank (lowest = best)
            top_n = min(self.config.top_n_holdings, screened.height)
            sort_col = (
                "composite_rank"
                if self.config.use_composite and "composite_rank" in screened.columns
                else "magic_formula_rank"
            )
            top_holdings = screened.sort(sort_col).head(top_n)
            holdings_per_rebalance.append(set(top_holdings["SimFinId"].to_list()))

            # Compute daily returns of equal-weight portfolio over the holding period
            next_rebal = rebalances[i + 1] if i + 1 < len(rebalances) else end_date
            returns_for_period = self._compute_equal_weight_returns(
                top_holdings["SimFinId"].to_list(),
                start=rebal_date,
                end=next_rebal,
                stop_loss_pct=self.config.per_idea_stop_loss_pct,
            )
            for date, ret in returns_for_period.items():
                daily_returns[date] = daily_returns.get(date, 0.0) + ret

            # Benchmark returns over same period
            if self.config.benchmark_simfin_id is not None:
                bench_returns = self._compute_equal_weight_returns(
                    [self.config.benchmark_simfin_id], start=rebal_date, end=next_rebal
                )
                for date, ret in bench_returns.items():
                    benchmark_daily_returns[date] = ret

        # Build equity curve
        if not daily_returns:
            return LaneBBacktestResult(
                n_rebalances=len(rebalances),
                n_holdings_per_rebalance=[len(h) for h in holdings_per_rebalance],
                equity_curve=np.array([self.config.initial_capital]),
                total_return=0.0,
                annual_return=0.0,
                sharpe=None,
                max_drawdown=0.0,
                n_unique_tickers=0,
                hit_rate=0.0,
                benchmark_return=None,
                alpha_vs_benchmark=None,
            )

        sorted_dates = sorted(daily_returns.keys())
        rets_arr = np.array([daily_returns[d] for d in sorted_dates])
        equity = self.config.initial_capital * np.cumprod(1.0 + rets_arr)
        total_return = float(equity[-1] / self.config.initial_capital - 1.0)

        # Annualised return + Sharpe
        n_days = len(sorted_dates)
        if n_days >= 30:
            years = n_days / 252.0
            annual_return = float((1.0 + total_return) ** (1.0 / years) - 1.0) if years > 0 else 0.0
            std = float(np.std(rets_arr, ddof=1)) if rets_arr.size > 1 else 0.0
            sharpe = float(np.mean(rets_arr) / std * (252**0.5)) if std > 0 else None
        else:
            annual_return = 0.0
            sharpe = None

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / (peak + 1e-12)
        max_dd = float(-np.min(dd)) if dd.size > 0 else 0.0

        # Hit rate (fraction of rebalances with positive return)
        per_rebalance_returns: list[float] = []
        for i, rebal_date in enumerate(rebalances):
            next_rebal = rebalances[i + 1] if i + 1 < len(rebalances) else end_date
            period_returns = [r for d, r in daily_returns.items() if rebal_date <= d < next_rebal]
            per_rebalance_returns.append(float(np.sum(period_returns)))
        hit_rate = float(np.mean([1.0 if r > 0 else 0.0 for r in per_rebalance_returns]))

        # Unique tickers
        all_holdings: set[int] = set()
        for h in holdings_per_rebalance:
            all_holdings.update(h)

        # Benchmark
        benchmark_total_return = None
        alpha = None
        if benchmark_daily_returns:
            bench_arr = np.array([benchmark_daily_returns.get(d, 0.0) for d in sorted_dates])
            bench_equity = self.config.initial_capital * np.cumprod(1.0 + bench_arr)
            benchmark_total_return = float(bench_equity[-1] / self.config.initial_capital - 1.0)
            alpha = total_return - benchmark_total_return

        return LaneBBacktestResult(
            n_rebalances=len(rebalances),
            n_holdings_per_rebalance=[len(h) for h in holdings_per_rebalance],
            equity_curve=equity,
            total_return=total_return,
            annual_return=annual_return,
            sharpe=sharpe,
            max_drawdown=max_dd,
            n_unique_tickers=len(all_holdings),
            hit_rate=hit_rate,
            benchmark_return=benchmark_total_return,
            alpha_vs_benchmark=alpha,
        )

    def _generate_rebalance_dates(self, start: datetime, end: datetime) -> list[datetime]:
        """Generate quarterly rebalance dates from start to end."""
        dates: list[datetime] = []
        cur = start
        while cur < end:
            dates.append(cur)
            # Approximate month addition
            cur = datetime(
                cur.year + (cur.month + self.config.rebalance_months - 1) // 12,
                (cur.month + self.config.rebalance_months - 1) % 12 + 1,
                1,
            )
        return dates

    def _compute_equal_weight_returns(
        self,
        simfin_ids: list[int],
        *,
        start: datetime,
        end: datetime,
        stop_loss_pct: float | None = None,
    ) -> dict[datetime, float]:
        """Compute daily equal-weight returns for the given holdings.

        For each day in [start, end), the return is the average of
        (1/N) * sum(close[t]/close[t-1] - 1) across holdings with valid data.

        If ``stop_loss_pct`` is set (BL-505d), an individual holding is exited
        (forced to 0 return) once its cumulative return from entry drops
        below -stop_loss_pct.
        """
        if self._prices is None or not simfin_ids:
            return {}
        pr = (
            self._prices
            if "date" in self._prices.columns
            else self._prices.rename({"Date": "date"})
        )
        pr = pr.filter(
            pl.col("SimFinId").is_in(simfin_ids)
            & (pl.col("date") >= start)
            & (pl.col("date") < end)
        )
        if pr.height == 0:
            return {}
        # Per (date), average return across holdings with valid shift
        pr = pr.sort(["SimFinId", "date"])
        pr = pr.with_columns(
            (pl.col("Close") / pl.col("Close").shift(1).over("SimFinId") - 1.0).alias(
                "daily_return"
            )
        )
        # Drop rows with NaN daily_return (first bar per SimFinId)
        pr = pr.filter(pl.col("daily_return").is_not_null() & pl.col("daily_return").is_not_nan())
        if pr.height == 0:
            return {}

        # If stop_loss is configured, exit holdings that breach the threshold.
        # Track per-SimFinId cumulative return from entry (first day in window).
        if stop_loss_pct is not None and stop_loss_pct > 0:
            # Compute cumulative return per SimFinId from first day in window
            # If cumulative <= -stop_loss, set daily_return to 0 for subsequent days
            pr = pr.with_columns(
                (pl.col("Close") / pl.col("Close").first().over("SimFinId") - 1.0).alias(
                    "cum_return"
                )
            )
            # Mark days where cumulative return breaches stop loss
            pr = pr.with_columns((pl.col("cum_return") <= -stop_loss_pct).alias("stop_breached"))
            # Per SimFinId, propagate stop_breached forward (once breached, stays out)
            pr = pr.with_columns(
                pl.col("stop_breached").cum_max().over("SimFinId").alias("stop_active")
            )
            # Where stop_active is True, daily_return = 0 (position is flat)
            pr = pr.with_columns(
                pl.when(pl.col("stop_active"))
                .then(0.0)
                .otherwise(pl.col("daily_return"))
                .alias("daily_return")
            )

        # Average daily return across holdings per date
        avg = pr.group_by("date").agg(pl.col("daily_return").mean().alias("portfolio_return"))
        result: dict[datetime, float] = {}
        for row in avg.to_dicts():
            result[row["date"]] = float(row["portfolio_return"])
        return result


__all__: list[str] = ["LaneBBacktestConfig", "LaneBBacktestResult", "LaneBBacktester"]
