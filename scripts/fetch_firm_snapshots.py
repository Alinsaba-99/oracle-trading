"""BL-720 — snapshot official firm rules pages (HTML + sha256).

Downloads each URL with a browser-like UA, stores the raw HTML in the
given path, and records ``url, fetched_at, sha256, bytes`` in
``docs/firm_sources/SNAPSHOTS.tsv``.  Idempotent: re-running overwrites
the HTML and updates the manifest row for the same destination path.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "docs/firm_sources/SNAPSHOTS.tsv"

#: (url, destination relative to docs/firm_sources/)
TARGETS: list[tuple[str, str]] = [
    ("https://ftmo.com/en/trading-objectives/", "ftmo/2026-08-22-trading-objectives.html"),
    ("https://ftmo.com/en/faq/", "ftmo/2026-08-22-faq.html"),
    (
        "https://help.fundednext.com/en/articles/8020763-is-ea-allowed-in-fundednext",
        "fundednext/2026-08-22-ea-policy.html",
    ),
    ("https://fundednext.com/rules", "fundednext/2026-08-22-rules.html"),
    (
        "https://the5ers.com/challenge-programs-bootcamp-high-stakes-hyper-growth-explained",
        "the5ers/2026-08-22-challenge-programs.html",
    ),
    (
        "https://alphacapitalgroup.uk/posts/alpha-capital-rules-explained-drawdown-profit-targets-daily-loss-and-evaluation-rules-2026",
        "alpha-capital/2026-08-22-rules-explained.html",
    ),
    (
        "https://alphacapitalgroup.uk/terms-and-conditions",
        "alpha-capital/2026-08-22-terms-and-conditions.html",
    ),
    ("https://www.e8markets.com/", "e8/2026-08-22-home.html"),
    ("https://help.e8markets.com/en/", "e8/2026-08-22-help-index.html"),
    ("https://www.e8markets.com/e8-one", "e8/2026-08-22-e8-one.html"),
]

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"


def fetch(url: str, dest: Path) -> tuple[str, int]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    # Canonical form: LF only (server CRLF is normalised at fetch time so
    # the archived bytes == committed bytes; sha256 covers this form).
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), len(data)


def main() -> int:
    rows: list[str] = []
    ok = 0
    for url, rel in TARGETS:
        dest = REPO / "docs/firm_sources" / rel
        try:
            digest, size = fetch(url, dest)
            rows.append(f"{url}\t{rel}\t{datetime.now(UTC).isoformat()}\t{digest}\t{size}")
            print(f"OK   {size:>9} {rel}")
            ok += 1
        except Exception as exc:
            print(f"FAIL {type(exc).__name__}: {url} ({exc})")
    # Merge: keep previous manifest rows for destinations not re-fetched.
    prev: dict[str, str] = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text().splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 2:
                prev[parts[1]] = line
    new = {r.split("\t")[1]: r for r in rows}
    merged = {**prev, **new}
    MANIFEST.write_text(
        "url\tdest\tfetched_at\tsha256\tbytes\n" + "\n".join(merged.values()) + "\n"
    )
    print(f"\nfetched {ok}/{len(TARGETS)} -> {MANIFEST}")
    return 0 if ok == len(TARGETS) else 1


if __name__ == "__main__":
    sys.exit(main())
