"""Follow GitHub 301 redirects for the 404 slugs (repo renamed/moved)."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://api.github.com/repos/"

SLUGS = [
    "alpacahq/marketstore",
    "butor/blackbird",
    "caoruicn/openalpha",
    "connerlambden/helium-mcp",
    "cryptoSUN2049/openFinclaw",
    "DebuggingMax/solana-sdk-tools",
    "focus1691/chart-patterns",
    "moxiespirit/MyClone",
    "perpetual-protocol/perp-arbitrageur",
    "sher1096/klinepic-agent-api-examples",
    "twopirllc/pandas-ta",
]


def _token() -> str | None:
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=10, check=True
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def probe(slug: str, token: str | None) -> str:
    req = urllib.request.Request(API + slug, headers={"User-Agent": "bom-probe"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
    try:
        with opener.open(req, timeout=30) as resp:
            data = json.loads(resp.read())
            final = data.get("full_name", slug)
            lic = (data.get("license") or {}).get("spdx_id") or "NONE"
            note = "MOVED->" + final if final.lower() != slug.lower() else "OK"
            return (
                f"{slug}\t{data.get('stargazers_count', '')}\t{data.get('pushed_at', '')}"
                f"\t{lic}\t{data.get('archived', '')}\t{data.get('language', '?')}\t{note}"
            )
    except urllib.error.HTTPError as exc:
        loc = exc.headers.get("Location", "")
        return f"{slug}\tHTTP {exc.code}\t\t\t\t\t{'redirect:' + loc if loc else 'gone'}"
    except Exception as exc:
        return f"{slug}\tERR\t\t\t\t\t{type(exc).__name__}"


def main() -> None:
    token = _token()
    for s in SLUGS:
        print(probe(s, token))


if __name__ == "__main__":
    main()
