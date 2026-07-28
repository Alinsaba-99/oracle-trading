"""Print data lake coverage per symbol/timeframe."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
COVERAGE = _ROOT / "data" / "lake" / "metadata" / "coverage.json"
WANT = ["1m", "1h", "4h", "1d"]
SEARCH_TFS = ["1h", "4h", "1d"]


def main() -> int:
    if not COVERAGE.exists():
        print("no coverage.json")
        return 1
    cov = json.loads(COVERAGE.read_text())

    symbols: dict[str, dict[str, dict]] = {}
    for key, entry in cov.items():
        sym, _, tf = key.partition("|")
        symbols.setdefault(sym, {})[tf] = entry

    print(f"{len(symbols)} symbols, {len(cov)} symbol/timeframe series\n")
    header = f"{'symbol':<10}" + "".join(f"{tf:>12}" for tf in WANT) + "   earliest"
    print(header)
    print("-" * len(header))

    total_rows = 0
    for sym in sorted(symbols):
        tfs = symbols[sym]
        cells = ""
        for tf in WANT:
            entry = tfs.get(tf)
            if entry is None:
                cells += f"{'—':>12}"
            else:
                rows = int(entry.get("rows", 0))
                total_rows += rows
                cells += f"{rows:>12,}"
        earliest = min(
            (str(e.get("earliest", ""))[:10] for e in tfs.values() if e.get("earliest")),
            default="?",
        )
        print(f"{sym:<10}{cells}   {earliest}")

    ready = [s for s in sorted(symbols) if all(t in symbols[s] for t in SEARCH_TFS)]
    print(f"\ntotal rows: {total_rows:,}")
    print(f"search-ready (1h+4h+1d): {len(ready)}/{len(symbols)}")
    print("  " + ", ".join(ready))

    gaps = {
        s: [t for t in SEARCH_TFS if t not in symbols[s]]
        for s in sorted(symbols)
        if any(t not in symbols[s] for t in SEARCH_TFS)
    }
    if gaps:
        print("\ngaps:")
        for sym, missing in gaps.items():
            print(f"  {sym}: missing {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
