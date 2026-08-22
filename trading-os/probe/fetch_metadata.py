"""BL-719 pre-step — probe GitHub metadata for every catalog repo.

Reads ``repo_slugs.txt`` (one ``owner/repo`` per line), queries the
GitHub REST API (authenticated via ``gh auth token`` when available),
and writes ``metadata.tsv``:

    slug<TAB>stars<TAB>pushed_at<TAB>license<TAB>archived<TAB>language

Rate-limit aware: sequential calls, tolerant of per-repo errors
(network/404 → ``API_ERROR`` row) so one bad slug never aborts the sweep.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://api.github.com/repos/"


def _token() -> str | None:
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=10, check=True
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def fetch(slug: str, token: str | None) -> tuple[str, ...]:
    req = urllib.request.Request(
        API + slug, headers={"Accept": "application/vnd.github+json", "User-Agent": "bom-probe"}
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    lic = (data.get("license") or {}).get("spdx_id") or "NONE"
    return (
        data.get("full_name", slug),
        str(data.get("stargazers_count", "")),
        data.get("pushed_at", ""),
        lic,
        str(data.get("archived", "")),
        data.get("language") or "?",
    )


def main() -> int:
    slugs = [
        line.strip() for line in (HERE / "repo_slugs.txt").read_text().splitlines() if line.strip()
    ]
    token = _token()
    print(f"probing {len(slugs)} repos (token: {'yes' if token else 'NO — 60 req/h limit!'})")
    rows: list[tuple[str, ...]] = []
    for i, slug in enumerate(slugs, 1):
        for attempt in range(3):
            try:
                rows.append(fetch(slug, token))
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429):  # rate limit — back off once
                    retry_after = int(exc.headers.get("Retry-After", "60") or 60)
                    print(f"  rate-limited on {slug}; sleeping {retry_after}s", flush=True)
                    time.sleep(min(retry_after, 120))
                    continue
                rows.append((slug, "API_ERROR", "", "", "", ""))
                break
            except Exception:
                if attempt == 2:
                    rows.append((slug, "API_ERROR", "", "", "", ""))
                time.sleep(1)
        if i % 25 == 0:
            print(f"  {i}/{len(slugs)}", flush=True)
    out = HERE / "metadata.tsv"
    out.write_text("\n".join("\t".join(r) for r in rows) + "\n")
    errors = sum(1 for r in rows if r[1] == "API_ERROR")
    print(f"done: {len(rows)} rows, {errors} errors -> {out}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
