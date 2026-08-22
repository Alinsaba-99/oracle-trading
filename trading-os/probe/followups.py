"""Follow-ups: hummingbot org move, alphalens fork health, cryptofeed license,
ib_insync fork landscape, pandas-ta new location."""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
API = "https://api.github.com"


def _token() -> str | None:
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=10, check=True
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def get(path: str, token: str | None) -> dict[str, Any] | None:
    req = urllib.request.Request(API + path, headers={"User-Agent": "bom-probe"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data: dict[str, Any] = json.loads(resp.read())
            return data
    except Exception as exc:
        print(f"  ERR {path}: {type(exc).__name__}")
        return None


def repo_line(slug: str, token: str | None) -> str:
    d = get(f"/repos/{slug}", token)
    if not d:
        return f"{slug}: NOT FOUND"
    lic = (d.get("license") or {}).get("spdx_id") or "NONE"
    return (
        f"{slug}: {d.get('stargazers_count')} stars, pushed {str(d.get('pushed_at'))[:10]}, "
        f"license={lic}, archived={d.get('archived')}, lang={d.get('language')}"
    )


def main() -> None:
    token = _token()

    print("== Hummingbot org move ==")
    print(repo_line("hummingbot/hummingbot", token))

    print("== alphalens forks ==")
    for slug in ("stefan-jansen/alphalens", "quantopian/alphalens"):
        print(repo_line(slug, token))

    print("== cryptofeed license text ==")
    d = get("/repos/bmoscon/cryptofeed/license", token)
    if d:
        print((d.get("license") or {}).get("spdx_id"))

    print("== ib_insync fork landscape (api query) ==")
    d = get("/search/repositories?q=ib+async+insync&sort=stars&order=desc&per_page=6", token)
    if d:
        for item in d.get("items", []):
            print(
                f"  {item['full_name']}: {item['stargazers_count']} stars, "
                f"pushed {str(item.get('pushed_at'))[:10]}, "
                f"license={(item.get('license') or {}).get('spdx_id') or 'NONE'}"
            )

    print("== pandas-ta search ==")
    d = get("/search/repositories?q=pandas-ta+in:name&sort=stars&per_page=5", token)
    if d:
        for item in d.get("items", []):
            print(f"  {item['full_name']}: {item['stargazers_count']} stars")

    out = {"note": "follow-up results recorded in eval/VERIFICA-A.md"}
    (HERE / "followups_done.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
