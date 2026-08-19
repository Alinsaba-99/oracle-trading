"""Diagnose LLM endpoint behavior: probe response_format support."""

from __future__ import annotations

import os
import sys

import requests


def main() -> int:
    base = os.environ.get("LLM_BASE", "https://opencode.ai/zen/go/v1")
    key = os.environ.get("LLM_KEY", "")
    model = os.environ.get("LLM_MODEL", "glm-5.3")

    print(f"Endpoint: {base}")
    print(f"Model: {model}")
    print()

    # Test 1: simple completion without response_format
    print("=== Test 1: simple completion (no response_format) ===")
    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": 'Return the JSON {"hello": "world"}'}],
                "temperature": 0.3,
                "max_tokens": 200,
            },
            timeout=60,
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            print(f"Content preview: {content[:300]}")
        else:
            print(f"Error body: {resp.text[:500]}")
    except Exception as e:
        print(f"FAIL: {e}")

    print()

    # Test 2: with response_format json_object
    print("=== Test 2: completion with response_format json_object ===")
    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": 'Return JSON {"hello": "world"}'}],
                "temperature": 0.3,
                "max_tokens": 200,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            print(f"Content preview: {content[:300]}")
        else:
            print(f"Error body: {resp.text[:500]}")
    except Exception as e:
        print(f"FAIL: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
