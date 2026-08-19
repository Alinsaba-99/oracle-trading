"""Run Lane D VRP signal generation for a configured underlying.

Usage:
    .venv/bin/python scripts/run_lane_d_vrp.py
    .venv/bin/python scripts/run_lane_d_vrp.py --underlying SPY
    .venv/bin/python scripts/run_lane_d_vrp.py --underlying QQQ --target-delta 0.15
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.strategy.lane_d_vrp import VRPConfig, VRPStrategy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Lane D VRP signal generation")
    parser.add_argument("--underlying", default="SPY")
    parser.add_argument("--target-dte", type=int, default=30)
    parser.add_argument("--target-delta", type=float, default=0.20)
    parser.add_argument("--position-size-pct", type=float, default=0.02)
    parser.add_argument("--max-positions", type=int, default=5)
    parser.add_argument("--ibkr-port", type=int, default=4002)
    parser.add_argument("--ibkr-client-id", type=int, default=11)
    parser.add_argument("--output-dir", default="docs/reports/lane-d")
    args = parser.parse_args()

    config = VRPConfig(
        target_dte=args.target_dte,
        target_delta=args.target_delta,
        position_size_pct=args.position_size_pct,
        max_positions=args.max_positions,
        underlying=args.underlying,
    )
    strategy = VRPStrategy(
        config=config, ibkr_port=args.ibkr_port, ibkr_client_id=args.ibkr_client_id
    )
    print(f"\n{'=' * 60}")
    print("Lane D — VRP Short Put Signal Generator")
    print(f"{'=' * 60}")
    print(f"Underlying: {args.underlying}")
    print(f"Target DTE: {args.target_dte}, target delta: {args.target_delta}")
    print(f"Max position size: {args.position_size_pct:.1%} of capital")
    print(f"Max concurrent: {args.max_positions}")
    print()

    signal = strategy.generate_signal(args.underlying)

    print(f"\n{'=' * 60}")
    print(f"Signal for {signal.underlying}")
    print(f"{'=' * 60}")
    print(f"  Underlying price: ${signal.underlying_price:.2f}")
    print(f"  Strike: ${signal.strike:.2f}")
    print(f"  DTE: {signal.dte}")
    print(f"  Estimated premium: ${signal.estimated_premium:.2f}")
    if signal.implied_vol:
        print(f"  Implied vol: {signal.implied_vol:.1%}")
    if signal.realised_vol_30d:
        print(f"  30d realised vol: {signal.realised_vol_30d:.1%}")
    if signal.vrp is not None:
        print(f"  VRP (IV - RV): {signal.vrp:+.3f}")
    print(f"  Edge signal: {signal.edge_signal}")
    print(f"  Confidence: {signal.confidence:.2f}")
    print(f"\n  Thesis: {signal.thesis}")
    print(f"\n  Invalidation: {signal.invalidation}")
    print(f"{'=' * 60}")

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")
    safe_u = args.underlying.lower().replace("/", "-")
    out_path = output_dir / f"{safe_u}-{timestamp}.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "underlying": signal.underlying,
        "underlying_price": signal.underlying_price,
        "strike": signal.strike,
        "dte": signal.dte,
        "estimated_premium": signal.estimated_premium,
        "implied_vol": signal.implied_vol,
        "realised_vol_30d": signal.realised_vol_30d,
        "vrp": signal.vrp,
        "edge_signal": signal.edge_signal,
        "confidence": signal.confidence,
        "thesis": signal.thesis,
        "invalidation": signal.invalidation,
        "config": {
            "target_dte": config.target_dte,
            "target_delta": config.target_delta,
            "position_size_pct": config.position_size_pct,
            "max_positions": config.max_positions,
            "exit_at_dte": config.exit_at_dte,
            "take_profit_pct": config.take_profit_pct,
            "roll_threshold": config.roll_threshold,
        },
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nJSON saved to: {out_path}")

    strategy.close()
    return 0 if signal.edge_signal == "SELL_PUT" else 1


if __name__ == "__main__":
    sys.exit(main())
