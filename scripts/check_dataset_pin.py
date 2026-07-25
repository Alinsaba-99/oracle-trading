"""BL-003 — Dataset pinning check script.

Fails (exit 1) if data/ohlcv/ES_1d.parquet is not byte-identical to
data/pinned/ES_1d_m31.parquet. Passes (exit 0) otherwise.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIN_PATH = REPO_ROOT / "data" / "pinned" / "ES_1d_m31.parquet"
WORK_PATH = REPO_ROOT / "data" / "ohlcv" / "ES_1d.parquet"
EXPECTED_SHA = "09a22268d2a7fa815beed6788917663771c7af7b347b7b49db6c2a1318f26b42"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not PIN_PATH.exists():
        print(f"FATAL: pinned file missing at {PIN_PATH}")
        return 2
    if not WORK_PATH.exists():
        print(f"FATAL: working file missing at {WORK_PATH}")
        return 2

    pin_hash = sha256(PIN_PATH)
    work_hash = sha256(WORK_PATH)

    if pin_hash != EXPECTED_SHA:
        print(f"FATAL: pinned file hash mismatch. expected={EXPECTED_SHA} actual={pin_hash}")
        return 3

    if pin_hash != work_hash:
        print("FAIL: ES_1d.parquet differs from pinned M31.")
        print(f"  pinned sha256: {pin_hash}")
        print(f"  working sha256: {work_hash}")
        print("  Recovery: cp data/pinned/ES_1d_m31.parquet data/ohlcv/ES_1d.parquet")
        return 1

    print(f"PASS: ES_1d.parquet matches pinned M31 (sha256={pin_hash[:12]}...).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
