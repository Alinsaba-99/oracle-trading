"""Check installed libs: litellm, langgraph, ib_insync."""

from __future__ import annotations

import sys


def main() -> int:
    libs = [
        ("litellm", "import litellm"),
        ("langgraph", "import langgraph"),
        ("ib_insync", "import ib_insync"),
        ("openai", "import openai"),
        ("anthropic", "from anthropic import Anthropic"),
        ("transformers", "from transformers import pipeline"),
        ("yfinance", "import yfinance"),
        ("feedparser", "import feedparser"),
        ("beautifulsoup4", "from bs4 import BeautifulSoup"),
        ("requests", "import requests"),
    ]
    for name, stmt in libs:
        try:
            exec(stmt)
            print(f"✅ {name}")
        except ImportError as e:
            print(f"❌ {name}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
