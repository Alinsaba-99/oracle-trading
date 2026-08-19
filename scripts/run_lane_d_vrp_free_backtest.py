"""Lane D VRP backtest — FREE tier, no IBKR subscription required.

Validates the Variance Risk Premium (VRP) edge using:
1. CBOE VIX index historical data (free via CBOE website)
2. Realised S&P 500 volatility (computed from yfinance SPY daily)
3. VIX futures historical (free via Quandl/AlphaVantage/yfinance)

Strategy (theoretical):
- "Sell" VIX at average implied vol
- "Buy" back at realised vol (30d forward)
- P&L = VIX_t - RV_30d_forward
- Positive average P&L = VRP exists

This backtest does NOT place live orders. It validates whether VRP > 0
historically, and what the implied Sharpe would be.

References
----------
- Carr & Wu (2009). "Variance Risk Premiums." Review of Financial Studies.
- Bollerslev, Tauchen, Zhou (2009). "Expected Stock Returns and Variance Risk Premia."
- AQR white paper "Selling Volatility" — long-term track record.

Output:
- Annualised VRP (avg IV - avg RV)
- Historical Sharpe of short-variance strategy
- Worst drawdown
- Per-year breakdown
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fetch_vix_history(start: str = "2010-01-01", end: str | None = None) -> pl.DataFrame:
    """Fetch VIX index historical daily close via yfinance (^VIX)."""
    ticker = yf.Ticker("^VIX")
    end_str = end or datetime.now().strftime("%Y-%m-%d")
    df_pd = ticker.history(start=start, end=end_str)
    if df_pd.empty:
        raise RuntimeError(f"No VIX data fetched for {start} to {end_str}")
    df = pl.from_pandas(df_pd.reset_index())
    cols = {c: c.lower() for c in df.columns if c[0].isupper()}
    df = df.rename(cols)
    df = df.select(["date", "close"]).rename({"close": "vix_close"})
    df = df.with_columns(pl.col("vix_close").cast(pl.Float64))
    df = df.filter(pl.col("vix_close").is_not_null() & (pl.col("vix_close") > 0))
    # Normalise date to date-only (strip timezone)
    df = df.with_columns(pl.col("date").dt.replace_time_zone(None).dt.date().cast(pl.Date))
    return df.sort("date")


def fetch_spy_history(start: str = "2010-01-01", end: str | None = None) -> pl.DataFrame:
    """Fetch SPY daily close for realised vol computation."""
    ticker = yf.Ticker("SPY")
    end_str = end or datetime.now().strftime("%Y-%m-%d")
    df_pd = ticker.history(start=start, end=end_str)
    if df_pd.empty:
        raise RuntimeError("No SPY data fetched")
    df = pl.from_pandas(df_pd.reset_index())
    cols = {c: c.lower() for c in df.columns if c[0].isupper()}
    df = df.rename(cols)
    df = df.select(["date", "close"]).rename({"close": "spy_close"})
    df = df.with_columns(pl.col("spy_close").cast(pl.Float64))
    df = df.filter(pl.col("spy_close").is_not_null() & (pl.col("spy_close") > 0))
    df = df.with_columns(pl.col("date").dt.replace_time_zone(None).dt.date().cast(pl.Date))
    return df.sort("date")


def compute_realised_vol_30d(spy_close: pl.Series, *, lookback: int = 30) -> pl.Series:
    """Compute 30-day rolling realised vol (annualised) from SPY close."""
    arr = spy_close.to_numpy().astype(np.float64)
    if arr.size < lookback + 1:
        return pl.Series("rv_30d", np.full(arr.size, np.nan))
    # Daily returns
    rets = np.diff(arr, prepend=np.nan) / arr
    # Rolling std (30-day window), annualised
    rv = np.full(arr.size, np.nan)
    for i in range(lookback, arr.size):
        window = rets[i - lookback + 1 : i + 1]
        finite = window[np.isfinite(window)]
        if finite.size > 5:
            std = float(np.std(finite, ddof=1))
            rv[i] = std * math.sqrt(252)  # annualised vol (fraction, not %)
    return pl.Series("rv_30d", rv)


def compute_vrp_backtest(vix_df: pl.DataFrame, spy_df: pl.DataFrame) -> dict[str, Any]:
    """Compute VRP edge + Sharpe over the overlapping period.

    Strategy: at each day t, "short" VIX at level VIX_t (= implied vol in %).
    The realised vol over the next 30 days = forward RV.
    P&L per day = (VIX_t - RV_forward_30d) / 100  (as fraction of notional).

    Annualised Sharpe = mean(daily P&L) / std(daily P&L) × sqrt(252).

    Returns
    -------
    dict
        Contains avg_vrp, sharpe, total_return_pct, max_dd_pct,
        per_year_breakdown, n_obs.
    """
    # Align on date
    merged = vix_df.join(spy_df, on="date", how="inner").sort("date")
    if merged.height == 0:
        raise RuntimeError("No overlap between VIX and SPY dates")

    # Compute realised vol (30-day rolling)
    rv_series = compute_realised_vol_30d(merged["spy_close"], lookback=30)
    # Convert to percentage to match VIX scale (VIX is in %)
    rv_pct = rv_series * 100.0
    merged = merged.with_columns(rv_pct.alias("rv_30d"))

    # Forward 30-day realised vol: shift RV forward by 30 days
    # (we want to know the RV that actually materialised over the next 30 days
    #  from the day we sold the variance)
    forward_rv = merged["rv_30d"].shift(-30)
    merged = merged.with_columns(forward_rv.alias("rv_forward_30d"))

    # Daily VRP P&L: sell VIX at day t, realised = forward 30d RV
    # Simplified: P&L_t = (VIX_t - RV_forward_30d) / 100 (per 1 unit of variance notional)
    merged = merged.with_columns(
        ((pl.col("vix_close") - pl.col("rv_forward_30d")) / 100.0).alias("vrp_pnl")
    )

    # Drop rows with NaN (last 30 days + first 30 days of warmup)
    clean = merged.filter(pl.col("vrp_pnl").is_not_null() & pl.col("vix_close").is_not_null())
    if clean.height == 0:
        raise RuntimeError("No clean VRP P&L data after filtering")

    pnls = clean["vrp_pnl"].to_numpy()
    n_obs = len(pnls)
    avg_vrp = float(np.mean(pnls))
    std_pnl = float(np.std(pnls, ddof=1)) if n_obs > 1 else 1.0
    sharpe = float(np.mean(pnls) / std_pnl * math.sqrt(252)) if std_pnl > 0 else 0.0

    # Cumulative P&L equity curve (assume $1 notional per trade)
    equity = np.cumsum(pnls)
    total_return_pct = float(equity[-1] * 100.0)
    # Max drawdown
    peak = np.maximum.accumulate(equity)
    dd = equity - peak
    max_dd_pct = float(-np.min(dd) * 100.0) if dd.size > 0 else 0.0

    # Per-year breakdown
    clean = clean.with_columns(pl.col("date").dt.year().alias("year"))
    per_year = (
        clean.group_by("year")
        .agg(
            [
                pl.len().alias("n_days"),
                pl.col("vrp_pnl").mean().alias("avg_vrp"),
                pl.col("vrp_pnl").sum().alias("total_pnl"),
                pl.col("vix_close").mean().alias("avg_vix"),
                pl.col("rv_30d").mean().alias("avg_rv"),
            ]
        )
        .sort("year")
    )

    return {
        "start_date": str(clean["date"].min()),
        "end_date": str(clean["date"].max()),
        "n_obs": n_obs,
        "avg_vrp_pct": avg_vrp * 100.0,
        "avg_vix": float(clean["vix_close"].mean()),  # type: ignore[arg-type]
        "avg_rv_30d": float(clean["rv_30d"].mean()),  # type: ignore[arg-type]
        "sharpe": sharpe,
        "total_return_pct": total_return_pct,
        "max_dd_pct": max_dd_pct,
        "per_year": per_year.to_dicts(),
    }


def main() -> int:
    parser = __import__("argparse").ArgumentParser(description="Lane D VRP free-tier backtest")
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--output", default="docs/reports/lane-d/vrp-free-tier-backtest.json")
    parser.add_argument("--report", default="docs/reports/lane-d/vrp-free-tier-backtest.md")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print("Lane D VRP Free-Tier Backtest (VIX + SPY via yfinance)")
    print(f"{'=' * 60}")
    print(f"Period: {args.start} → {args.end or 'today'}")
    print()

    print("Fetching VIX history via yfinance (^VIX)...")
    vix_df = fetch_vix_history(start=args.start, end=args.end)
    print(f"  VIX bars: {vix_df.height}")
    vix_min = float(vix_df["vix_close"].min())  # type: ignore[arg-type]
    vix_max = float(vix_df["vix_close"].max())  # type: ignore[arg-type]
    print(f"  VIX range: {vix_min:.2f} - {vix_max:.2f}")

    print("\nFetching SPY history via yfinance...")
    spy_df = fetch_spy_history(start=args.start, end=args.end)
    print(f"  SPY bars: {spy_df.height}")

    print("\nComputing VRP backtest...")
    result = compute_vrp_backtest(vix_df, spy_df)

    print(f"\n{'=' * 60}")
    print("VRP Backtest Result")
    print(f"{'=' * 60}")
    print(f"  Period: {result['start_date']} → {result['end_date']}")
    print(f"  Observations: {result['n_obs']}")
    print(f"  Avg VIX: {result['avg_vix']:.2f}%")
    print(f"  Avg 30d RV: {result['avg_rv_30d']:.2f}%")
    print(f"  Avg VRP (IV - RV): {result['avg_vrp_pct']:+.3f}%")
    print(f"  Sharpe: {result['sharpe']:.3f}")
    print(f"  Total return: {result['total_return_pct']:+.2f}%")
    print(f"  Max DD: {result['max_dd_pct']:.2f}%")

    print("\nPer-year breakdown:")
    print(f"  {'Year':<6} {'N':<6} {'AvgVRP':<10} {'TotalPnL':<10} {'AvgVIX':<8} {'AvgRV':<8}")
    for row in result["per_year"]:
        print(
            f"  {row['year']:<6} {row['n_days']:<6} "
            f"{row['avg_vrp'] * 100:+.3f}%   "
            f"{row['total_pnl'] * 100:+.2f}%   "
            f"{row['avg_vix']:.2f}    "
            f"{row['avg_rv']:.2f}"
        )

    # Save JSON + markdown
    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"\n✅ JSON: {out_path}")

    md_path = ROOT / args.report
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md: list[str] = []
    md.append("# Lane D VRP Free-Tier Backtest\n\n")
    md.append(f"**Generated**: {datetime.now(UTC).isoformat()}\n")
    md.append(f"**Period**: {result['start_date']} → {result['end_date']}\n")
    md.append("**Data source**: yfinance (^VIX + SPY) — FREE, no subscription\n\n")
    md.append("## Summary\n\n")
    md.append(f"- Avg VIX (implied): {result['avg_vix']:.2f}%\n")
    md.append(f"- Avg 30d realised vol: {result['avg_rv_30d']:.2f}%\n")
    md.append(f"- **Avg VRP (IV - RV)**: {result['avg_vrp_pct']:+.3f}% per day\n")
    md.append(f"- **Sharpe**: {result['sharpe']:.3f}\n")
    md.append(
        f"- Total return (per 1 unit variance notional): {result['total_return_pct']:+.2f}%\n"
    )
    md.append(f"- Max DD: {result['max_dd_pct']:.2f}%\n")
    md.append(f"- Observations: {result['n_obs']}\n\n")
    md.append("## Per-year breakdown\n\n")
    md.append("| Year | N days | Avg VRP | Total PnL | Avg VIX | Avg RV |\n")
    md.append("|---|---|---|---|---|---|\n")
    for row in result["per_year"]:
        md.append(
            f"| {row['year']} | {row['n_days']} | "
            f"{row['avg_vrp'] * 100:+.3f}% | "
            f"{row['total_pnl'] * 100:+.2f}% | "
            f"{row['avg_vix']:.2f} | "
            f"{row['avg_rv']:.2f} |\n"
        )
    md.append("\n## Verdict\n\n")
    if result["avg_vrp_pct"] > 0.0 and result["sharpe"] > 0.5:
        md.append("✅ **VRP edge confirmed** — short variance is positive-EV on average.\n")
        md.append(f"Sharpe {result['sharpe']:.2f} is in the documented range (AQR ~1.0).\n")
        md.append("Recommend: implement short-put strategy with IBKR options subscription.\n")
    elif result["avg_vrp_pct"] > 0.0:
        md.append("⚠️ VRP positive but Sharpe below 0.5 — edge exists but noisy.\n")
    else:
        md.append("❌ VRP not positive in this period — short variance negative-EV.\n")
    md_path.write_text("".join(md))
    print(f"✅ Markdown: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
