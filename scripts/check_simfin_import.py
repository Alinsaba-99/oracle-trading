"""Verify simfin import works after uv add."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        import simfin as sf
        from simfin.bulk import BulkData

        print(f"OK simfin version: {sf.__version__}")
        print(f"OK BulkData class: {BulkData}")
        print(f"OK simfin module path: {sf.__file__}")
        return 0
    except ImportError as e:
        print(f"FAIL simfin import: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
