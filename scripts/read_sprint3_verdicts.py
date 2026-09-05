#!/usr/bin/env python3
"""BL-742 — Read programmatic verdicts of BL-739/740/741 from JSON reports.

Prereg: la condizione di integrazione del Task 5 ("se ≥1 famiglia è GO")
deve essere letta dai JSON prodotti dai runner dei Task 2/3/4, NON
hardcoded. Questo script è l'unica fonte di lettura dei verdetti per il
report sprint-3.md.

Reads:
- docs/reports/edge-factory/overnight-drift-sprint.json   (BL-739)
- docs/reports/edge-factory/fx-carry-policy-rate.json    (BL-740)
- docs/reports/edge-factory/pillar-conditioning-sprint.json (BL-741)

Exit code 0 sempre (informativo). Stampa tabella + verdetto aggregato.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs" / "reports" / "edge-factory"


def _load(name: str) -> dict[str, Any]:
    path = REPORTS / name
    with path.open(encoding="utf-8") as fh:
        result: dict[str, Any] = json.load(fh)
        return result


def main() -> int:
    od = _load("overnight-drift-sprint.json")
    fx = _load("fx-carry-policy-rate.json")
    pc = _load("pillar-conditioning-sprint.json")

    # Campi letti (prereg): vedi tabella nel report sprint-3.md
    od_verdict = od.get("verdict")  # "NO_GO" | "GO"
    od_passing = od.get("n_passing_assets")  # int
    od_total_assets = len({r["asset"] for r in od.get("results", [])})

    fx_verdict = fx.get("verdict")
    fx_passing = fx.get("n_passing_pairs")
    fx_missing = len(fx.get("data", {}).get("missing_currencies", []))

    pc_overall = pc.get("overall")  # "REJECTED" | "APPROVED"
    pc_negative = pc.get("n_pillars_negative")
    pc_total_pillars = pc.get("n_pillars_total")

    print(f"{'Famiglia':<35} {'BL':<8} {'Verdict field':<22} {'Valore'}")
    print("-" * 90)
    print(
        f"{'EF-004 overnight-drift':<35} "
        f"{'BL-739':<8} "
        f"{'verdict':<22} "
        f"{od_verdict}  (passing={od_passing}/{od_total_assets} asset)"
    )
    print(
        f"{'EF-004 fx-carry-policy-rate':<35} "
        f"{'BL-740':<8} "
        f"{'verdict':<22} "
        f"{fx_verdict}  (passing={fx_passing}/7 coppie, FRED missing={fx_missing})"
    )
    print(
        f"{'EF-004 cross-pillar-conditioning':<35} "
        f"{'BL-741':<8} "
        f"{'overall':<22} "
        f"{pc_overall}  (negative={pc_negative}/{pc_total_pillars} pilastri)"
    )
    print("-" * 90)

    # Aggregato
    n_go_families = sum(1 for v in (od_verdict, fx_verdict, pc_overall) if v in ("GO", "APPROVED"))
    print(f"Famiglie GO/qualificate: {n_go_families}/3")
    if n_go_families == 0:
        print("→ nessuna gamba da aggiungere a LEGS in run_portfolio_sr_max.py")
        print("→ report sprint-3.md = NO-GO complessivo onesto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
