"""Smoke test for simfin loader (BL-504).

Run: .venv/bin/python scripts/smoke_simfin.py
"""

from __future__ import annotations

import json
import sys

from analytics.fundamental.simfin_loader import smoke_test


def main() -> int:
    result = smoke_test()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("available") else 1


if __name__ == "__main__":
    sys.exit(main())
