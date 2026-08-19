"""Introspect simfin package structure to find correct bulk loader API."""

from __future__ import annotations

import sys

import simfin as sf
import simfin.datasets as d


def main() -> int:
    print("simfin version:", sf.__version__)
    print("simfin module path:", sf.__file__)
    print()
    print("simfin dir (top-level):")
    for attr in sorted(dir(sf)):
        if not attr.startswith("_"):
            print(f"  - {attr}")
    print()
    print("simfin.datasets attrs:")
    for attr in sorted(dir(d)):
        if not attr.startswith("_"):
            print(f"  - {attr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
