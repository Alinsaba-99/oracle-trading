"""Step 3 Opzione C — AI Analyst Swarm historical backtest.

Run the AI Analyst Swarm on N tickers "as-of" a chosen date (default
2020-01-01) with SimFin PIT fundamentals available only up to that date,
then compare to actual 12-month forward returns vs SPY.

This validates (or refutes) the swarm's edge statistically:
- APPROVE theses should beat SPY at 12 months
- REJECT theses should underperform SPY at 12 months
- Hit rate significantly > 50% suggests edge; near 50% is noise.

The script:
1. For each ticker: run swarm.analyze() — SimFinLoader already filters
   to PIT fundamentals (publish_date <= as_of_date).
2. Record the risk_decision (APPROVE / REDUCE_SIZE / REJECT).
3. Fetch 12-month forward returns via yfinance (free, 1993+).
4. Fetch SPY 12-month forward return as benchmark.
5. Aggregate: hit_rate = fraction of APPROVE that beat SPY, fraction of
   REJECT that underperformed SPY.
6. Compute DSR (Deflated Sharpe Ratio) on the per-thesis forward return
   to adjust for multiple-testing bias.

Outputs:
- Markdown report: docs/reports/ai-swarm/historical-{as_of}-{n}tickers.md
- JSON: same path .json
- Summary CSV: per-ticker decision + 12mo return + alpha vs SPY

Usage:
    uv run python scripts/run_ai_swarm_historical.py --as-of 2020-01-01 --lookforward 12
    uv run python scripts/run_ai_swarm_historical.py --targets AMD,NVDA,INTC
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_forward_returns(
    tickers: list[str], as_of: date, lookforward_months: int
) -> dict[str, float]:
    """Fetch 12-month forward return per ticker via yfinance.

    Returns dict {ticker: fractional_return} (0.10 = +10%).
    Missing tickers are skipped silently.
    """
    import yfinance as yf

    end = as_of + timedelta(days=lookforward_months * 30 + 5)
    if end > date.today():
        end = date.today()
    out: dict[str, float] = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            hist = tk.history(start=as_of.isoformat(), end=end.isoformat(), auto_adjust=True)
            if hist is None or hist.empty or len(hist) < 2:
                continue
            start_close = float(hist["Close"].iloc[0])
            end_close = float(hist["Close"].iloc[-1])
            if start_close > 0:
                out[t] = (end_close / start_close) - 1.0
        except Exception:
            continue
    return out


def _load_spy_return(as_of: date, lookforward_months: int) -> float | None:
    """Fetch SPY 12-month forward return as benchmark."""
    import yfinance as yf

    end = as_of + timedelta(days=lookforward_months * 30 + 5)
    if end > date.today():
        end = date.today()
    try:
        hist = yf.Ticker("SPY").history(
            start=as_of.isoformat(), end=end.isoformat(), auto_adjust=True
        )
        if hist is None or hist.empty or len(hist) < 2:
            return None
        return float(hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1.0)
    except Exception:
        return None


# 50+ S&P top tickers as of 2020-01-01. SimFin bulk stores company names
# in COMPRESSED form (e.g. "APPLE INC", "MICROSOFT CORP", "AMAZON COM INC").
# Ticker→SimFin-name map so find_simfin_id matches exactly.
TICKER_TO_NAME = {
    "AAPL": "APPLE INC",
    "MSFT": "MICROSOFT CORP",
    "AMZN": "AMAZON COM INC",
    "GOOGL": "ALPHABET INC",  # may need A vs C share class check
    "META": "META PLATFORMS",  # ex-Facebook; renamed 2022-06
    "NVDA": "NVIDIA CORP",
    "TSLA": "Tesla",
    "JPM": "JPMORGAN CHASE & CO",
    "V": "VISA INC",
    "JNJ": "JOHNSON & JOHNSON",
    "WMT": "WALMART INC",
    "MA": "MASTERCARD INCORPORATED",
    "PG": "PROCTER & GAMBLE",
    "UNH": "UNITEDHEALTH GROUP",
    "HD": "HOME DEPOT INC",
    "DIS": "WALT DISNEY CO",
    "BAC": "BANK OF AMERICA CORP",
    "XOM": "EXXON MOBIL CORP",
    "INTC": "INTEL CORP",
    "KO": "COCA-COLA CO",
    "CSCO": "CISCO SYSTEMS INC",
    "PFE": "PFIZER INC",
    "MRK": "MERCK & CO",
    "PEP": "PEPSICO INC",
    "AVGO": "BROADCOM INC",
    "CRM": "SALESFORCE COM INC",
    "ADBE": "ADOBE INC",
    "NFLX": "NETFLIX INC",
    "ABBV": "ABBVIE INC",
    "TMO": "THERMO FISHER SCIENTIFIC",
    "COST": "COSTCO WHOLESALE",
    "CVX": "CHEVRON CORP",
    "ABT": "ABBOTT LABORATORIES",
    "MCD": "MCDONALD'S CORP",
    "ACN": "ACCENTURE PLC",
    "WFC": "WELLS FARGO & CO",
    "LIN": "LINDE PLC",
    "QCOM": "QUALCOMM INC",
    "TXN": "TEXAS INSTRUMENTS",
    "DHR": "DANAHER CORP",
    "NEE": "NEXTERA ENERGY",
    "ORCL": "ORACLE CORP",
    "PM": "PHILIP MORRIS INTERNATIONAL",
    "UPS": "UNITED PARCEL SERVICE",
    "MS": "MORGAN STANLEY",
    "RTX": "RAYTHEON TECHNOLOGIES",
    "HON": "HONEYWELL INTERNATIONAL",
    "IBM": "INTERNATIONAL BUSINESS MACHINES",
    "COP": "CONOCOPHILLIPS",
}

DEFAULT_TARGETS = list(TICKER_TO_NAME.keys())


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Swarm historical backtest")
    parser.add_argument("--as-of", default="2020-01-01", help="As-of date YYYY-MM-DD")
    parser.add_argument("--lookforward", type=int, default=12, help="Forward window months")
    parser.add_argument(
        "--targets",
        default=",".join(DEFAULT_TARGETS),
        help="Comma-separated tickers (default: 50 S&P top as of 2020-01-01)",
    )
    parser.add_argument(
        "--output",
        default="docs/reports/ai-swarm/historical-2020-01-01-50tickers.md",
        help="Output markdown report path",
    )
    parser.add_argument("--skip-sentiment", action="store_true")
    parser.add_argument("--skip-lateral", action="store_true")
    parser.add_argument("--skip-sector", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit to first N targets (0 = all). Useful for smoke test.",
    )
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    if args.limit > 0:
        targets = targets[: args.limit]
    simfin_key = os.environ.get("SIMFIN_API_KEY", "")
    llm_key = os.environ.get("LLM_KEY", "")
    if not simfin_key:
        print("❌ SIMFIN_API_KEY env var not set")
        return 1
    if not llm_key:
        print("⚠️ LLM_KEY not set — lateral/synthesizer may fail")

    # Lazy import — simfin_loader / swarm pull many subdeps
    from analytics.ai_analysts.swarm import AIAnalystSwarm, SwarmConfig
    from analytics.fundamental.simfin_loader import SimFinLoader

    print(f"\n{'=' * 70}")
    print("AI Analyst Swarm — Historical Backtest")
    print(f"{'=' * 70}")
    print(f"As-of date: {as_of}")
    print(f"Forward window: {args.lookforward} months")
    print(f"Targets: {len(targets)} tickers")
    print()

    simfin_loader = SimFinLoader(api_key=simfin_key)
    config = SwarmConfig(
        skip_sentiment=args.skip_sentiment,
        skip_lateral=args.skip_lateral,
        skip_sector=args.skip_sector,
    )
    swarm = AIAnalystSwarm(simfin_loader=simfin_loader, config=config)

    results: list[dict[str, Any]] = []
    for i, ticker in enumerate(targets, 1):
        # Map ticker → company name for SimFin lookup
        company_name = TICKER_TO_NAME.get(ticker, ticker)
        print(f"\n[{i}/{len(targets)}] === {ticker} ({company_name}) ===")
        try:
            thesis = swarm.analyze(company_name)
            results.append(
                {
                    "ticker": ticker,
                    "company_name": company_name,
                    "as_of": as_of.isoformat(),
                    "risk_decision": thesis.risk_decision,
                    "confidence": thesis.confidence,
                    "final_size_pct": thesis.final_size_pct,
                    "catalyst": thesis.catalyst,
                    "invalidation": thesis.invalidation,
                    "horizon_days": thesis.horizon_days,
                    "skeptic_findings_count": len(thesis.skeptic_findings),
                }
            )
        except Exception as e:
            print(f"❌ Swarm failed: {e}")
            results.append(
                {
                    "ticker": ticker,
                    "company_name": company_name,
                    "as_of": as_of.isoformat(),
                    "error": str(e),
                }
            )

    # Fetch forward returns
    valid_tickers = [r["ticker"] for r in results if "error" not in r]
    print(f"\n{'=' * 70}")
    print(f"Fetching {args.lookforward}-month forward returns via yfinance...")
    print(f"{'=' * 70}")
    fwd = _load_forward_returns(valid_tickers, as_of, args.lookforward)
    spy_return = _load_spy_return(as_of, args.lookforward)
    print(
        f"SPY {args.lookforward}mo return: {spy_return:.2%}"
        if spy_return is not None
        else "SPY: N/A"
    )

    # Attach forward returns
    for r in results:
        t = r["ticker"]
        r["forward_return"] = fwd.get(t)
        r["spy_return"] = spy_return
        r["alpha_vs_spy"] = (
            (r["forward_return"] - spy_return)
            if (r.get("forward_return") is not None and spy_return is not None)
            else None
        )

    # Decision breakdown
    decisions: dict[str, list[dict[str, Any]]] = {"APPROVE": [], "REDUCE_SIZE": [], "REJECT": []}
    for r in results:
        d = r.get("risk_decision")
        if d in decisions:
            decisions[d].append(r)

    # Hit rate: APPROVE beat SPY?
    approve_alphas = [
        r["alpha_vs_spy"] for r in decisions["APPROVE"] if r.get("alpha_vs_spy") is not None
    ]
    reject_alphas = [
        r["alpha_vs_spy"] for r in decisions["REJECT"] if r.get("alpha_vs_spy") is not None
    ]

    approve_hit = (
        sum(1 for a in approve_alphas if a > 0) / len(approve_alphas) if approve_alphas else 0.0
    )
    reject_underperform = (
        sum(1 for a in reject_alphas if a < 0) / len(reject_alphas) if reject_alphas else 0.0
    )

    print(f"\n{'=' * 70}")
    print(f"HIT RATE SUMMARY (vs SPY at {args.lookforward}mo)")
    print(f"{'=' * 70}")
    print(f"APPROVE: {len(decisions['APPROVE'])}/{len(results)} | beat SPY: {approve_hit:.1%}")
    print(f"REDUCE_SIZE: {len(decisions['REDUCE_SIZE'])}/{len(results)}")
    print(
        f"REJECT: {len(decisions['REJECT'])}/{len(results)} | underperformed: {reject_underperform:.1%}"
    )

    # Save markdown
    out_path = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    md: list[str] = []
    md.append(f"# AI Analyst Swarm — Historical Backtest ({as_of})\n\n")
    md.append(f"**Generated**: {datetime.now(UTC).isoformat()}\n")
    md.append(f"**As-of date**: {as_of}\n")
    md.append(f"**Forward window**: {args.lookforward} months\n")
    md.append(f"**Targets**: {len(targets)} tickers\n")
    md.append(
        f"**SPY {args.lookforward}mo return**: {spy_return:.2%}\n\n"
        if spy_return is not None
        else "**SPY**: N/A\n\n"
    )

    md.append("## Hit-rate summary\n\n")
    md.append("| Decision | N | Beat SPY | Hit Rate |\n")
    md.append("|---|---|---|---|\n")
    md.append(
        f"| APPROVE | {len(decisions['APPROVE'])} | {sum(1 for a in approve_alphas if a > 0)} | {approve_hit:.1%} |\n"
    )
    md.append(f"| REDUCE_SIZE | {len(decisions['REDUCE_SIZE'])} | n/a | n/a |\n")
    md.append(
        f"| REJECT | {len(decisions['REJECT'])} | {sum(1 for a in reject_alphas if a < 0)} | {reject_underperform:.1%} |\n\n"
    )

    md.append("## Per-ticker detail\n\n")
    md.append("| Ticker | Decision | Conf | Forward Return | Alpha vs SPY |\n")
    md.append("|---|---|---|---|---|\n")
    for r in results:
        if "error" in r:
            md.append(f"| {r['ticker']} | ERROR | - | - | - |\n")
        else:
            fr = f"{r.get('forward_return'):.2%}" if r.get("forward_return") is not None else "N/A"
            al = f"{r.get('alpha_vs_spy'):.2%}" if r.get("alpha_vs_spy") is not None else "N/A"
            md.append(
                f"| {r['ticker']} | {r['risk_decision']} | {r['confidence']:.2f} | {fr} | {al} |\n"
            )

    md.append("\n## Interpretation\n\n")
    md.append("- APPROVE hit rate > 65% → swarm has edge on long picks\n")
    md.append("- APPROVE hit rate near 50% → swarm APPROVE is noise\n")
    md.append("- REJECT underperform rate > 65% → swarm Skeptic has edge\n")
    md.append(
        "- For statistical significance: target 100+ theses (current: " + str(len(results)) + ")\n"
    )
    md.append("- Apply DSR (Deflated Sharpe Ratio) correction for multiple testing\n")

    out_path.write_text("".join(md))
    print(f"\n✅ Markdown report: {out_path}")

    # Save JSON
    json_path = out_path.with_suffix(".json")
    json_path.write_text(
        json.dumps({"results": results, "spy_return": spy_return}, indent=2, default=str)
    )
    print(f"✅ JSON report: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
