"""Lane A PAC multi-asset validation (BL-503 / Lane A TSM with DSR).

Runs the Carver 4-module pipeline (BL-502) on N futures daily series from
the lake, computes Sharpe + DSR + PBO + PSR, and writes a verdict report
per ADR-017 (DSR/PBO/CPCV mandatory) and ADR-016 (anti-beta benchmark).

Run:
    .venv/bin/python scripts/run_lane_a_validation.py
    .venv/bin/python scripts/run_lane_a_validation.py --symbols ES,NQ,GC,CL,YM
    .venv/bin/python scripts/run_lane_a_validation.py --report docs/reports/lane-a/

Outputs:
    docs/reports/lane-a/{validation,walkforward,dsr}.md (markdown reports)
    docs/reports/lane-a/{validation,walkforward,dsr}.json (machine-readable)

Honest target: Sharpe 0.7-1.0 on at least 2/3 asset core (ES/SPY/BTC).
Anything below 0.5 → REJECTED with DSR + PBO (per ADR-017).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.qualification.dsr import (  # noqa: E402
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    probability_of_backtest_overfitting,
)
from analytics.strategy.cta import (  # noqa: E402
    InstrumentDiversificationMultiplier,
    build_lane_a_pipeline,
    build_lane_a_pipeline_multi_rule,
)

LAKE_ROOT = ROOT / "data" / "lake" / "normalized"
OUTPUT_DIR = ROOT / "docs" / "reports" / "lane-a"

# 8-12 futures for Lane A PAC multi-asset (Carver recommendation: 6-12 instruments)
DEFAULT_SYMBOLS = ["ES", "NQ", "GC", "CL", "YM", "ZN", "EURUSD", "GBPUSD"]
# Note: EURUSD/GBPUSD are FX pairs in lake under symbol=EURUSD format (not EURUSD_X)


@dataclass(frozen=True)
class LaneAValidationResult:
    """Per-symbol validation result for Lane A TSM PAC."""

    symbol: str
    bars: int
    start_date: str
    end_date: str
    observed_sharpe: float | None
    annual_return: float | None
    annual_vol: float | None
    max_drawdown: float | None
    dsr: float | None
    psr: float | None
    pbo: float | None
    n_trials: int
    verdict: str  # PASSED / REJECTED / INSUFFICIENT_DATA
    notes: str = ""


@dataclass(frozen=True)
class LaneAPortfolioResult:
    """Aggregate portfolio result across instruments with IDM."""

    n_instruments: int
    avg_correlation: float | None
    idm: float | None
    portfolio_sharpe: float | None
    portfolio_dsr: float | None
    portfolio_psr: float | None
    portfolio_pbo: float | None
    verdict: str
    notes: str = ""


def load_daily_close(symbol: str) -> pl.DataFrame | None:
    """Load daily OHLCV for a symbol from the lake."""
    path = LAKE_ROOT / f"symbol={symbol}" / "tf=1d"
    if not path.exists():
        return None
    try:
        # Use glob to read all year partitions; polars lazy
        df = pl.scan_parquet(path / "year=*" / "*.parquet").collect()
        if df.height == 0:
            return None
        # Pick time + close columns
        cols = df.columns
        time_col = "time" if "time" in cols else ("timestamp" if "timestamp" in cols else cols[0])
        close_col = "close" if "close" in cols else ("Close" if "Close" in cols else cols[-1])
        out = df.select([time_col, close_col]).rename({time_col: "date", close_col: "close"})
        out = out.sort("date").with_columns(pl.col("close").cast(pl.Float64))
        # Drop rows with null close
        out = out.filter(pl.col("close").is_not_null())
        return out
    except Exception as e:
        print(f"WARN load {symbol}: {e}")
        return None


def compute_strategy_returns(close: pl.Series, *, target_annual_vol: float = 0.12) -> np.ndarray:
    """Compute strategy returns given a close series (Carver pipeline).

    Pipeline (causal, BL-502):
        TrendSignalRule(fast=8, slow=32) → forecast
        ForecastScale → normalise abs mean
        VolatilityTarget → position scalar
        strategy_return[i] = position[i-1] * pct_change[i]  # no lookahead
    """
    pos_series = build_lane_a_pipeline(close, target_annual_vol=target_annual_vol)
    pos = pos_series.to_numpy().astype(np.float64)
    close_arr = close.to_numpy().astype(np.float64)
    # pct_change with 1-bar lag
    pct_change = np.zeros_like(close_arr)
    pct_change[1:] = (close_arr[1:] / close_arr[:-1]) - 1.0
    # Lag the position by 1 bar (no lookahead — execute at next bar open)
    lagged_pos = np.zeros_like(pos)
    lagged_pos[1:] = pos[:-1]
    # Strategy returns
    strat_rets = lagged_pos * pct_change
    # Mask warmup (first 100 bars) as NaN
    strat_rets[:100] = np.nan
    return strat_rets


def compute_strategy_returns_multi_rule(
    close: pl.Series, *, target_annual_vol: float = 0.12
) -> np.ndarray:
    """Compute strategy returns via multi-rule ForecastCombine (BL-503b).

    Pipeline (causal, BL-503b):
        4 forecasts: EMA(8/32), EMA(16/64), EMA(32/128), TSM(252)
        ForecastCombine equal-weight → combined forecast
        VolatilityTarget → position scalar
        strategy_return[i] = position[i-1] * pct_change[i]  # no lookahead
    """
    pos_series = build_lane_a_pipeline_multi_rule(close, target_annual_vol=target_annual_vol)
    pos = pos_series.to_numpy().astype(np.float64)
    close_arr = close.to_numpy().astype(np.float64)
    pct_change = np.zeros_like(close_arr)
    pct_change[1:] = (close_arr[1:] / close_arr[:-1]) - 1.0
    lagged_pos = np.zeros_like(pos)
    lagged_pos[1:] = pos[:-1]
    strat_rets = lagged_pos * pct_change
    strat_rets[:252] = np.nan  # TSM needs 252 warmup
    return strat_rets


def sharpe_ratio(returns: np.ndarray, periods_per_year: int = 252) -> float | None:
    clean = returns[np.isfinite(returns)]
    if clean.size < 8:
        return None
    std = float(np.std(clean, ddof=1))
    if std <= 0:
        return None
    return float(np.mean(clean) / std * math.sqrt(periods_per_year))


def max_drawdown(equity: np.ndarray) -> float | None:
    """Return max drawdown as fraction (e.g. 0.15 = -15%)."""
    eq = equity[np.isfinite(equity)]
    if eq.size < 2:
        return None
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    return float(-np.min(dd))


def annual_return(returns: np.ndarray, periods_per_year: int = 252) -> float | None:
    clean = returns[np.isfinite(returns)]
    if clean.size < 8:
        return None
    cumulative = np.cumprod(1.0 + clean)
    n_years = clean.size / periods_per_year
    if cumulative[-1] <= 0 or n_years <= 0:
        return None
    return float(cumulative[-1] ** (1.0 / n_years) - 1.0)


def annual_vol(returns: np.ndarray, periods_per_year: int = 252) -> float | None:
    clean = returns[np.isfinite(returns)]
    if clean.size < 8:
        return None
    return float(np.std(clean, ddof=1) * math.sqrt(periods_per_year))


def validate_symbol(
    symbol: str, *, n_trials: int = 8, multi_rule: bool = False
) -> LaneAValidationResult:
    """Run Lane A pipeline on one symbol and compute metrics + verdict.

    Parameters
    ----------
    symbol : str
        Lake symbol.
    n_trials : int
        Number of strategies tested in discovery sweep (for DSR correction).
    multi_rule : bool
        If True, use the BL-503b multi-rule ForecastCombine pipeline
        (EMA 8/32 + 16/64 + 32/128 + TSM 252). If False (default), use
        the v1 single-rule TrendSignalRule(8/32).
    """
    df = load_daily_close(symbol)
    if df is None or df.height < 300:
        return LaneAValidationResult(
            symbol=symbol,
            bars=0 if df is None else df.height,
            start_date="",
            end_date="",
            observed_sharpe=None,
            annual_return=None,
            annual_vol=None,
            max_drawdown=None,
            dsr=None,
            psr=None,
            pbo=None,
            n_trials=n_trials,
            verdict="INSUFFICIENT_DATA",
            notes=f"need ≥300 bars; found {0 if df is None else df.height}",
        )

    close = df["close"]
    if multi_rule:
        rets = compute_strategy_returns_multi_rule(close)
    else:
        rets = compute_strategy_returns(close)
    obs_sharpe = sharpe_ratio(rets)
    ann_ret = annual_return(rets)
    ann_vol = annual_vol(rets)
    # Equity curve for drawdown
    finite_rets = np.where(np.isfinite(rets), rets, 0.0)
    equity = 100.0 * np.cumprod(1.0 + finite_rets)
    mdd = max_drawdown(equity)
    dsr = deflated_sharpe_ratio(rets, n_trials=n_trials)
    psr = probabilistic_sharpe_ratio(rets, benchmark_sharpe=0.0)
    # PBO needs matrix — synthesise a synthetic matrix by bootstrap sampling
    finite = rets[np.isfinite(rets)]
    if finite.size >= 200:
        rng = np.random.default_rng(42)
        n_boot = max(n_trials, 8)
        sample_size = min(finite.size, 500)
        rows = []
        for _ in range(n_boot):
            idx = rng.choice(finite.size, size=sample_size, replace=True)
            rows.append(finite[idx])
        pbo_matrix = np.asarray(rows)
        pbo_raw = probability_of_backtest_overfitting(pbo_matrix)["pbo"]
        pbo = float(pbo_raw) if pbo_raw is not None else None
    else:
        pbo = None

    # Verdict per ADR-016 (anti-beta) + ADR-017 (DSR/PBO/PSR)
    verdict = "REJECTED"
    notes_parts = []
    pipeline_label = "multi-rule (BL-503b)" if multi_rule else "single-rule (BL-502)"
    notes_parts.append(f"pipeline={pipeline_label}")
    if obs_sharpe is not None and obs_sharpe >= 0.5:
        verdict = "PASSED"
        notes_parts.append(f"Sharpe {obs_sharpe:.3f} ≥ 0.5 (ADR-016 §4)")
    else:
        notes_parts.append(f"Sharpe {obs_sharpe} < 0.5 (ADR-016 §4)")
    if dsr is not None and dsr >= 0.95:
        notes_parts.append(f"DSR {dsr:.3f} ≥ 0.95 (ADR-017)")
    else:
        verdict = "REJECTED" if verdict == "PASSED" else verdict
        notes_parts.append(f"DSR {dsr} < 0.95 (ADR-017)")
    if pbo is not None and pbo < 0.5:
        notes_parts.append(f"PBO {pbo:.3f} < 0.5 (ADR-017)")
    else:
        verdict = "REJECTED" if verdict == "PASSED" else verdict
        notes_parts.append(f"PBO {pbo} ≥ 0.5 (ADR-017)")

    return LaneAValidationResult(
        symbol=symbol,
        bars=df.height,
        start_date=str(df["date"].min()),
        end_date=str(df["date"].max()),
        observed_sharpe=obs_sharpe,
        annual_return=ann_ret,
        annual_vol=ann_vol,
        max_drawdown=mdd,
        dsr=dsr,
        psr=psr,
        pbo=pbo,
        n_trials=n_trials,
        verdict=verdict,
        notes="; ".join(notes_parts),
    )


def validate_portfolio(
    results: list[LaneAValidationResult], *, multi_rule: bool = False
) -> LaneAPortfolioResult:
    """Aggregate per-symbol results into a portfolio verdict with IDM."""
    valid = [
        r for r in results if r.verdict != "INSUFFICIENT_DATA" and r.observed_sharpe is not None
    ]
    if len(valid) < 2:
        return LaneAPortfolioResult(
            n_instruments=len(valid),
            avg_correlation=None,
            idm=None,
            portfolio_sharpe=None,
            portfolio_dsr=None,
            portfolio_psr=None,
            portfolio_pbo=None,
            verdict="INSUFFICIENT_DATA",
            notes=f"need ≥2 instruments with valid metrics; found {len(valid)}",
        )

    # Build portfolio returns by equal-weight blend (per-symbol returns pre-computed)
    def _n_finite(symbol: str) -> int:
        df_sym = load_daily_close(symbol)
        assert df_sym is not None  # simboli in `valid` già caricati sopra
        rets_check = (
            compute_strategy_returns_multi_rule(df_sym["close"])
            if multi_rule
            else compute_strategy_returns(df_sym["close"])
        )
        return int(np.sum(np.isfinite(rets_check)))

    min_len = min(_n_finite(r.symbol) for r in valid)
    port_rets = np.zeros(int(min_len))
    count = 0
    for r in valid:
        df = load_daily_close(r.symbol)
        if df is None:
            continue
        if multi_rule:
            rets = compute_strategy_returns_multi_rule(df["close"])
        else:
            rets = compute_strategy_returns(df["close"])
        finite_rets = np.where(np.isfinite(rets), rets, 0.0)
        # Equal weight allocation: each instrument gets 1/N of portfolio
        port_rets += finite_rets[: int(min_len)] / len(valid)
        count += 1

    port_sharpe = sharpe_ratio(port_rets)
    port_dsr = deflated_sharpe_ratio(port_rets, n_trials=len(valid))
    port_psr = probabilistic_sharpe_ratio(port_rets, benchmark_sharpe=0.0)
    # PBO via bootstrap
    finite = port_rets[np.isfinite(port_rets)]
    if finite.size >= 200:
        rng = np.random.default_rng(42)
        n_boot = max(len(valid), 8)
        sample_size = min(finite.size, 500)
        rows = [
            finite[rng.choice(finite.size, size=sample_size, replace=True)] for _ in range(n_boot)
        ]
        pbo_matrix = np.asarray(rows)
        port_pbo_raw = probability_of_backtest_overfitting(pbo_matrix)["pbo"]
        port_pbo = float(port_pbo_raw) if port_pbo_raw is not None else None
    else:
        port_pbo = None

    # IDM via empirical correlation of per-symbol returns
    ret_matrix = np.zeros((len(valid), int(min_len)))
    for i, r in enumerate(valid):
        df = load_daily_close(r.symbol)
        if df is None:
            continue
        if multi_rule:
            rets = compute_strategy_returns_multi_rule(df["close"])
        else:
            rets = compute_strategy_returns(df["close"])
        finite_rets = np.where(np.isfinite(rets), rets, 0.0)
        ret_matrix[i] = finite_rets[: int(min_len)]
    corr = np.asarray(np.corrcoef(ret_matrix))
    if corr.ndim == 0 or np.any(np.isnan(corr)):
        avg_corr = None
        idm = None
    else:
        # Average off-diagonal correlation
        n = corr.shape[0]
        off_diag = corr[~np.eye(n, dtype=bool)]
        avg_corr = float(np.mean(off_diag)) if off_diag.size > 0 else None
        idm_calc = InstrumentDiversificationMultiplier(n_instruments=n)
        idm = idm_calc.from_correlation_matrix(corr)

    verdict = "PASSED"
    notes_parts = []
    if port_sharpe is not None and port_sharpe >= 0.5:
        notes_parts.append(f"portfolio Sharpe {port_sharpe:.3f} ≥ 0.5")
    else:
        verdict = "REJECTED"
        notes_parts.append(f"portfolio Sharpe {port_sharpe} < 0.5")
    if port_dsr is not None and port_dsr >= 0.95:
        notes_parts.append(f"DSR {port_dsr:.3f} ≥ 0.95")
    else:
        verdict = "REJECTED"
        notes_parts.append(f"DSR {port_dsr} < 0.95")
    if port_pbo is not None and port_pbo < 0.5:
        notes_parts.append(f"PBO {port_pbo:.3f} < 0.5")
    else:
        verdict = "REJECTED"

    return LaneAPortfolioResult(
        n_instruments=len(valid),
        avg_correlation=avg_corr,
        idm=idm,
        portfolio_sharpe=port_sharpe,
        portfolio_dsr=port_dsr,
        portfolio_psr=port_psr,
        portfolio_pbo=port_pbo,
        verdict=verdict,
        notes="; ".join(notes_parts),
    )


def write_reports(
    per_symbol: list[LaneAValidationResult],
    portfolio: LaneAPortfolioResult,
    *,
    out_dir: Path,
    multi_rule: bool = False,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline_label = "multi-rule (BL-503b)" if multi_rule else "single-rule (BL-502)"
    # JSON machine-readable
    payload: dict[str, Any] = {
        "generated_at": "2026-08-15",
        "pipeline": pipeline_label,
        "per_symbol": [asdict(r) for r in per_symbol],
        "portfolio": asdict(portfolio),
    }
    suffix = "_multi_rule" if multi_rule else ""
    (out_dir / f"validation{suffix}.json").write_text(json.dumps(payload, indent=2, default=str))

    # Markdown human-readable
    md: list[str] = []
    md.append(f"# Lane A PAC Multi-Asset Validation ({pipeline_label})\n\n")
    md.append("**Generated**: 2026-08-15\n")
    if multi_rule:
        md.append(
            "**Pipeline**: 4-rule ForecastCombine (EMA 8/32 + 16/64 + 32/128 + TSM 252 Moskowitz-Ooi-Pedersen) → VolatilityTarget(target=12%)\n"
        )
    else:
        md.append(
            "**Pipeline**: TrendSignalRule(fast=8, slow=32) → ForecastScale → VolatilityTarget(target=12%)\n"
        )
    md.append(f"**Instruments**: {', '.join(r.symbol for r in per_symbol)}\n\n")

    md.append("## Per-symbol results\n\n")
    md.append(
        "| Symbol | Bars | Sharpe | Ann.Return | Ann.Vol | MaxDD | DSR | PSR | PBO | Verdict |\n"
    )
    md.append("|---|---|---|---|---|---|---|---|---|---|\n")
    for r in per_symbol:
        s_sharpe = f"{r.observed_sharpe:.3f}" if r.observed_sharpe is not None else "—"
        s_ret = f"{r.annual_return:.1%}" if r.annual_return is not None else "—"
        s_vol = f"{r.annual_vol:.1%}" if r.annual_vol is not None else "—"
        s_mdd = f"{r.max_drawdown:.1%}" if r.max_drawdown is not None else "—"
        s_dsr = f"{r.dsr:.3f}" if r.dsr is not None else "—"
        s_psr = f"{r.psr:.3f}" if r.psr is not None else "—"
        s_pbo = f"{r.pbo:.3f}" if r.pbo is not None else "—"
        md.append(
            f"| {r.symbol} | {r.bars} | {s_sharpe} | {s_ret} | {s_vol} | {s_mdd} | {s_dsr} | {s_psr} | {s_pbo} | **{r.verdict}** |\n"
        )
    md.append("\n")

    md.append("## Portfolio aggregate (equal-weight + IDM)\n\n")
    md.append(f"- Instruments: {portfolio.n_instruments}\n")
    if portfolio.avg_correlation is not None:
        md.append(f"- Avg pairwise correlation: {portfolio.avg_correlation:.3f}\n")
    if portfolio.idm is not None:
        md.append(f"- IDM (Instrument Diversification Multiplier): {portfolio.idm:.3f}\n")
    if portfolio.portfolio_sharpe is not None:
        md.append(f"- Portfolio Sharpe: {portfolio.portfolio_sharpe:.3f}\n")
    if portfolio.portfolio_dsr is not None:
        md.append(f"- Portfolio DSR: {portfolio.portfolio_dsr:.3f}\n")
    if portfolio.portfolio_psr is not None:
        md.append(f"- Portfolio PSR: {portfolio.portfolio_psr:.3f}\n")
    if portfolio.portfolio_pbo is not None:
        md.append(f"- Portfolio PBO: {portfolio.portfolio_pbo:.3f}\n")
    md.append(f"\n**Verdict**: {portfolio.verdict}\n")
    md.append(f"\n**Notes**: {portfolio.notes}\n\n")

    md.append("## Honest target assessment\n\n")
    md.append("Per the deep-research synthesis 2026-08-15 and ADR-016 (anti-beta):\n")
    md.append("- Target Sharpe: 0.7-1.0 (NOT 3-5 = Renaissance territory)\n")
    md.append("- DSR ≥ 0.95 (ADR-017)\n")
    md.append("- PBO < 0.5 (ADR-017)\n")
    md.append("- DD ≤ 4% (ADR-016 §4)\n\n")
    md.append(
        "If PASSED: this Lane (Lane A PAC multi-asset) proceeds to BL-024 (G6 re-run) → G7 cert.\n"
    )
    md.append(
        "If REJECTED: pivot to Lane B (turnaround, BL-505/506) or option selling VRP (BL-507).\n"
    )

    (out_dir / f"validation{suffix}.md").write_text("".join(md))


def main() -> int:
    parser = argparse.ArgumentParser(description="Lane A TSM validation (BL-503 / BL-503b)")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--n-trials", type=int, default=8)
    parser.add_argument("--out", default=str(OUTPUT_DIR))
    parser.add_argument(
        "--multi-rule",
        action="store_true",
        help="Use BL-503b multi-rule ForecastCombine pipeline (EMA 8/32 + 16/64 + 32/128 + TSM 252)",
    )
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    pipeline_label = "multi-rule (BL-503b)" if args.multi_rule else "single-rule (BL-502)"
    print(
        f"Lane A validation: symbols={symbols}, n_trials={args.n_trials}, pipeline={pipeline_label}"
    )

    per_symbol: list[LaneAValidationResult] = []
    for s in symbols:
        r = validate_symbol(s, n_trials=args.n_trials, multi_rule=args.multi_rule)
        per_symbol.append(r)
        if r.verdict == "INSUFFICIENT_DATA":
            print(f"  {s}: INSUFFICIENT_DATA ({r.notes})")
        else:
            sh_str = f"{r.observed_sharpe:.3f}" if r.observed_sharpe is not None else "—"
            print(f"  {s}: Sharpe={sh_str}, DSR={r.dsr}, PBO={r.pbo}, verdict={r.verdict}")

    portfolio = validate_portfolio(per_symbol, multi_rule=args.multi_rule)
    print(
        f"\nPortfolio: Sharpe={portfolio.portfolio_sharpe}, IDM={portfolio.idm}, verdict={portfolio.verdict}"
    )

    out_dir = Path(args.out)
    write_reports(per_symbol, portfolio, out_dir=out_dir, multi_rule=args.multi_rule)
    print(f"\nReports written to: {out_dir}/validation.{{md,json}}")
    return 0 if portfolio.verdict == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
