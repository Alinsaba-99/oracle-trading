"""Probe candidate firm rule URLs for BL-720 (which paths exist)."""

from __future__ import annotations

import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

CANDIDATES = [
    "https://help.e8markets.com/en/collections/9852270-products-rules",
    "https://help.e8markets.com/en/collections/products-rules",
    "https://help.e8markets.com/en/articles/consistency-rule",
    "https://www.e8markets.com/e8-one",
    "https://www.e8markets.com/e8-track",
    "https://www.e8markets.com/pricing",
    "https://www.e8markets.com/prop-firm-accounts",
]


def main() -> None:
    for u in CANDIDATES:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                print("OK", r.status, len(r.read()), u)
        except Exception as e:
            print("FAIL", u, type(e).__name__)


if __name__ == "__main__":
    main()
