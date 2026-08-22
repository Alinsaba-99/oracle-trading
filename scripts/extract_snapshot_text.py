"""Extract text from firm snapshots for rules verification (BL-720)."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "docs/firm_sources"


def to_text(p: Path) -> str:
    raw = p.read_text(errors="ignore")
    raw = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<[^>]+>", "\n", raw)
    txt = html.unescape(raw)
    lines = [ln.strip() for ln in txt.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def main() -> None:
    for rel in sys.argv[1:]:
        p = SRC / rel
        text = to_text(p)
        out = SRC / (rel.replace(".html", ".txt"))
        out.write_text(text)
        print(f"{rel} -> {len(text)} chars text -> {out.name}")


if __name__ == "__main__":
    main()
