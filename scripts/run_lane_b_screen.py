"""BL-505 — Run Lane B monthly screening on SimFin bulk data.

Computes the TurnaroundScreen on the most recent quarterly fundamentals
from SimFin, returns the top-N candidate tickers that pass:
- Piotroski F-Score >= 7 (configurable)
- Greenblatt Magic Formula rank <= 50 (configurable)
- 12-month past return in [-20%, +50%] (configurable)

Output: JSON file at data/lane-b/screenings/<yyyy-mm>.json with the
candidate list, plus a markdown summary.

The operator then applies the qualitative overlay (catalyst + invalidation)
per ADR-019 §5 (workflow passo 2).

Usage:
    python scripts/run_lane_b_screen.py
    python scripts/run_lane_b_screen.py --as-of 2026-08-31 --top-n 30
    python scripts/run_lane_b_screen.py --min-f-score 8 --return-12m-min -0.10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import polars as pl  # noqa: E402

from analytics.fundamental.simfin_loader import SimFinLoader  # noqa: E402
from analytics.strategy.catalog.value import TurnaroundScreen  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Lane B monthly screening (BL-505)")
    parser.add_argument(
        "--as-of", default=None, help="Screen as of this date (YYYY-MM-DD). Default: today."
    )
    parser.add_argument(
        "--top-n", type=int, default=30, help="Top-N candidates to return (default 30)"
    )
    parser.add_argument("--min-f-score", type=int, default=7)
    parser.add_argument("--magic-rank-max", type=int, default=50)
    parser.add_argument("--return-12m-min", type=float, default=-0.20)
    parser.add_argument("--return-12m-max", type=float, default=0.50)
    parser.add_argument(
        "--output-dir",
        default="data/lane-b/screenings",
        help="Output directory for JSON + markdown (default data/lane-b/screenings)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("SIMFIN_API_KEY")
    if not api_key:
        print("❌ SIMFIN_API_KEY env var not set", file=sys.stderr)
        return 1

    as_of_naive = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now()
    print(f"Lane B screening as of: {as_of_naive.date()}")
    print(
        f"Config: min_f_score={args.min_f_score}, magic_rank_max={args.magic_rank_max}, "
        f"return_12m_min={args.return_12m_min}, top_n={args.top_n}"
    )
    print()

    loader = SimFinLoader(api_key=api_key)
    print("Loading SimFin bulk data...")
    income = loader.income_statements()
    balance = loader.balance_sheets()
    cashflow = loader.cash_flows()
    prices = loader.daily_prices()
    companies = loader.companies()
    print(f"  income: {income.height} rows")
    print(f"  balance: {balance.height} rows")
    print(f"  cashflow: {cashflow.height} rows")
    print(f"  prices: {prices.height} rows")
    print(f"  companies: {companies.height} rows")

    # Compute F-Score components per (SimFinId, Publish Date)
    print("\nComputing Piotroski F-Score components...")
    inc = income.rename({"Publish Date": "publish_date"})
    bal = balance.rename({"Publish Date": "publish_date"})
    cf = cashflow.rename({"Publish Date": "publish_date"})

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
    merged = merged.sort(["SimFinId", "publish_date"])
    merged = merged.with_columns(
        [
            (pl.col("Net Income") / pl.col("Total Assets")).alias("roa"),
            (pl.col("Net Cash from Operating Activities") / pl.col("Total Assets")).alias("cfo"),
            (pl.col("Total Current Assets") / pl.col("Total Current Liabilities")).alias(
                "current_ratio"
            ),
            (pl.col("Long Term Debt") / pl.col("Total Assets")).alias("leverage"),
            (pl.col("Gross Profit") / pl.col("Revenue")).alias("gross_margin"),
            (pl.col("Revenue") / pl.col("Total Assets")).alias("asset_turnover"),
        ]
    )
    merged = merged.with_columns(
        [
            pl.col("roa").shift(1).over("SimFinId").alias("roa_prev"),
            pl.col("leverage").shift(1).over("SimFinId").alias("leverage_prev"),
            pl.col("current_ratio").shift(1).over("SimFinId").alias("current_ratio_prev"),
            pl.col("gross_margin").shift(1).over("SimFinId").alias("gross_margin_prev"),
            pl.col("asset_turnover").shift(1).over("SimFinId").alias("asset_turnover_prev"),
        ]
    )
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
            pl.when(
                pl.col("Shares (Diluted)") > pl.col("Shares (Diluted)").shift(1).over("SimFinId")
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

    # Compute Greenblatt Magic Formula rank (per publish_date)
    print("Computing Greenblatt Magic Formula rank...")
    merged = merged.with_columns(
        [pl.col("Operating Income (Loss)").alias("ebit"), pl.col("Total Assets").alias("ev_proxy")]
    )
    merged = merged.with_columns((pl.col("ebit") / pl.col("ev_proxy")).alias("earnings_yield"))
    merged = merged.with_columns(
        pl.col("earnings_yield")
        .rank(method="ordinal", descending=True)
        .over("publish_date")
        .alias("magic_formula_rank")
    )

    # Compute 12-month past return per (SimFinId, date)
    print("Computing 12-month past returns from shareprices...")
    pr = prices if "date" in prices.columns else prices.rename({"Date": "date"})
    pr = pr.sort(["SimFinId", "date"])
    pr = pr.with_columns(
        (pl.col("Close") / pl.col("Close").shift(252).over("SimFinId") - 1.0).alias("return_12m")
    )

    # Attach return_12m at publish_date to merged
    merged = merged.join(
        pr.select(["SimFinId", "date", "return_12m"]),
        left_on=["SimFinId", "publish_date"],
        right_on=["SimFinId", "date"],
        how="left",
    )

    # Filter to most recent per SimFinId before as_of
    print(f"\nFiltering to most recent statement per SimFinId (as of {as_of_naive.date()})...")
    recent = merged.filter(pl.col("publish_date") <= as_of_naive)
    if recent.height == 0:
        print("❌ No statements found before as_of date", file=sys.stderr)
        return 1
    recent = recent.sort("publish_date", descending=True).group_by("SimFinId").first()
    print(f"  unique SimFinIds with recent statements: {recent.height}")

    # Apply TurnaroundScreen
    screen = TurnaroundScreen(
        min_f_score=args.min_f_score,
        max_magic_formula_rank=args.magic_rank_max,
        min_past_return_12m=args.return_12m_min,
        max_past_return_12m=args.return_12m_max,
    )
    candidates = screen.screen(recent)

    # Add company names (SimFin companies table doesn't have Ticker; we use Company Name)
    companies_subset = companies.select(["SimFinId", "Company Name"])
    candidates = candidates.join(companies_subset, on="SimFinId", how="left")

    # Sort by magic_formula_rank ascending (best first) and take top-N
    candidates = candidates.sort("magic_formula_rank").head(args.top_n)

    print(f"\n✅ {candidates.height} candidates passed the screen (top-{args.top_n}):")
    if candidates.height > 0:
        cols_to_show = [
            c
            for c in [
                "SimFinId",
                "Company Name",
                "f_score",
                "magic_formula_rank",
                "return_12m",
                "publish_date",
            ]
            if c in candidates.columns
        ]
        print(candidates.select(cols_to_show))

    # Save JSON + markdown
    out_dir = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    month_str = as_of_naive.strftime("%Y-%m")
    json_path = out_dir / f"{month_str}.json"
    md_path = out_dir / f"{month_str}.md"

    payload = {
        "as_of": str(as_of_naive.date()),
        "config": {
            "min_f_score": args.min_f_score,
            "magic_rank_max": args.magic_rank_max,
            "return_12m_min": args.return_12m_min,
            "return_12m_max": args.return_12m_max,
            "top_n": args.top_n,
        },
        "candidates": candidates.to_dicts() if candidates.height > 0 else [],
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str))

    md: list[str] = []
    md.append(f"# Lane B Monthly Screening — {month_str}\n\n")
    md.append(f"**As of**: {as_of_naive.date()}\n")
    md.append(
        f"**Config**: min_f_score={args.min_f_score}, magic_rank_max={args.magic_rank_max}, "
        f"return_12m=[{args.return_12m_min}, {args.return_12m_max}], top_n={args.top_n}\n\n"
    )
    md.append(f"**Candidates**: {candidates.height} (top-{args.top_n})\n\n")
    if candidates.height > 0:
        md.append("| SimFinId | Company | F-Score | Magic Rank | Return 12m | Publish Date |\n")
        md.append("|---|---|---|---|---|---|\n")
        for row in candidates.to_dicts():
            md.append(
                f"| {row.get('SimFinId', '')} | {row.get('Company Name', '')} | "
                f"{row.get('f_score', '')} | {row.get('magic_formula_rank', '')} | "
                f"{row.get('return_12m', 0) or 0:.1%} | {row.get('publish_date', '')} |\n"
            )
    md.append("\n## Next steps (qualitative overlay, ADR-019 §5)\n\n")
    md.append("For each candidate, the operator applies their tech knowledge to identify:\n")
    md.append("- Catalyst (new product, CEO turnaround, buyback, sector rotation)\n")
    md.append("- Invalidation (what would make the thesis wrong)\n")
    md.append("- Horizon (6mo / 1y / 2y based on catalyst)\n")
    md.append("- Sizing (2-3% of capital per idea)\n\n")
    md.append("Then pre-register via `scripts/register_thesis.py`.\n")
    md_path.write_text("".join(md))

    print(f"\nJSON saved to: {json_path}")
    print(f"Markdown saved to: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
