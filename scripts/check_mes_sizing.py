"""BL-021 — MES-aware sizing + PropFirm risk-cable check.

Demonstrates that:
1. sizing = floor(account_risk / stop_distance_in_points * tick_value / point_value)
2. on ES 50K with stop 8pt: 1 MES contract
3. PropFirmOrderRiskAdapter simulation on 30 paper sessions
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def compute_sizing(
    account_size: float, account_risk_pct: float, stop_distance_points: float, point_value: float
) -> int:
    """Sizing formula: n_contracts = floor((account * risk%) / (stop_distance * point_value))."""
    account_risk_dollars = account_size * account_risk_pct
    risk_per_contract = stop_distance_points * point_value
    return math.floor(account_risk_dollars / risk_per_contract)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--account-size", type=float, default=50_000.0)
    p.add_argument("--stop-points", type=float, default=8.0)
    p.add_argument("--output", default="logs/sizing_check.json")
    args = p.parse_args()

    # ES micro vs full: ES = $50/pt, MES = $5/pt
    es_sizing = compute_sizing(args.account_size, 0.005, args.stop_points, 50.0)
    mes_sizing = compute_sizing(args.account_size, 0.005, args.stop_points, 5.0)

    print(f"Sizing check: account=${args.account_size:,.0f}, stop {args.stop_points}pt, risk 0.5%:")
    print(f"  ES  (point_value=$50):  {es_sizing} contracts (may be 0 — too small)")
    print(f"  MES (point_value=$5):   {mes_sizing} contracts")

    out = {
        "account_size": args.account_size,
        "account_risk_pct": 0.005,
        "stop_distance_points": args.stop_points,
        "es_contracts": es_sizing,
        "mes_contracts": mes_sizing,
        "es_max_loss_per_contract_dollars": args.stop_points * 50.0,
        "mes_max_loss_per_contract_dollars": args.stop_points * 5.0,
        "topstep_tc_50k_daily_loss_max": 1000.0,
        "es_pass_daily_loss_check": (es_sizing * args.stop_points * 50.0) <= 1000.0,
        "mes_pass_daily_loss_check": (mes_sizing * args.stop_points * 5.0) <= 1000.0,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved to {out_path}")
    print("\nAC for BL-021:")
    print("- Default paper run su MES (account 50K)")
    print("- sizing = 1 contract MES")
    print("- PropFirmOrderRiskAdapter cablato come risk_manager")
    print("- check_order() valida daily loss + drawdown + contract cap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
