"""List available models on the configured OpenAI-compatible LLM endpoint."""

from __future__ import annotations

import os
import sys

import requests


def main() -> int:
    base = os.environ.get("LLM_BASE", "https://opencode.ai/zen/go/v1")
    key = os.environ.get("LLM_KEY", "")
    print(f"Endpoint: {base}")
    print(f"Key: {key[:8]}...{key[-4:] if len(key) > 12 else '***'}")
    print()
    try:
        resp = requests.get(
            f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30
        )
        if resp.status_code != 200:
            print(f"FAIL: status {resp.status_code}: {resp.text[:500]}")
            return 1
        data = resp.json()
        models = data.get("data", []) if isinstance(data, dict) else data
        if not models:
            print(f"Empty models list. Raw response: {data}")
            return 1
        print(f"Available models ({len(models)}):")
        for m in models[:50]:
            mid = m.get("id") if isinstance(m, dict) else m
            print(f"  - {mid}")
    except Exception as e:
        print(f"FAIL: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
