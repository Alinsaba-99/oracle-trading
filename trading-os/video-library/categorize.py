#!/usr/bin/env python3
"""Generate a categorized reading plan for Moon Dev's core videos."""

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
TSV = BASE / "moondev_videos.tsv"
INDEX = BASE / "transcripts" / "index.json"

# Load video list
videos = []
with TSV.open(encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        parts = line.split("\t") if "\t" in line else re.split(r"\\t", line)
        if len(parts) >= 2:
            videos.append(
                {"id": parts[0], "title": parts[1], "duration": parts[2] if len(parts) > 2 else "?"}
            )

# Load index if exists
index = {}
if INDEX.exists():
    index = json.loads(INDEX.read_text(encoding="utf-8"))


# Categorize core videos (Batch 1)
def find_videos(patterns, exclude=[]):
    results = []
    for v in videos:
        title_lower = v["title"].lower()
        if any(p in title_lower for p in patterns):
            if not any(e in title_lower for e in exclude):
                results.append(v)
    return results


# Category 1: RBI + Methodology
rbi = find_videos(
    [
        "rbi",
        "research",
        "backtest",
        "incubate",
        "alpha decay",
        "framework",
        "methodology",
        "system",
        "machine learning",
        "how to actually",
        "full course",
        "a-z from zero",
        "no bullshit",
        "official process",
        "zero to algo",
        "proof of",
        "edge",
        "strategy",
    ]
)
# Remove duplicates & shorts
rbi = [
    v
    for v in rbi
    if len(v["title"]) > 30 and v["duration"] not in ("?") and int(v["duration"]) > 30
]

# Category 2: Fable 5
fable5 = find_videos(["fable 5", "fable5"])
fable5 = [v for v in fable5 if int(v["duration"]) > 60][:20]

# Category 3: Beginner Tutorials (building a bot)
beginner = find_videos(
    [
        "stop trading with your feelings",
        "build a bot",
        "trading bot",
        "full tutorial",
        "from zero to",
        "how to build",
        "guide to making",
        "automate your trading",
        "trading bot course",
        "multiple trading bots",
        "run in the cloud",
        "how to actually use ai",
        "how to build a trading bot",
    ]
)
beginner = [v for v in beginner if int(v["duration"]) > 180][:20]

# Category 4: Architecture (OpenClaw, Quant App, system design)
arch = find_videos(
    [
        "openclaw",
        "claude code",
        "quant app",
        "moon dev app",
        "ai agents",
        "claude code built",
        "claude code just",
        "claude code made",
        "claude code found",
        "claude code +",
        "claude skills",
        "swarm of ai",
        "ai agents for",
        "claude code goals",
        "claude code changed",
        "claude code broke",
        "ai agents that",
    ]
)
arch = [v for v in arch if int(v["duration"]) > 300][:20]

# Category 5: Data & Edge (Hyperliquid, liquidations, HFT, ML)
data = find_videos(
    [
        "hyperliquid",
        "liquidation",
        "hft",
        "high frequency",
        "machine learning",
        "predicts stock",
        "prop firm",
        "backtest",
        "tick data",
        "whale",
        "everyone's position",
        "see everybody",
    ]
)
data = [v for v in data if int(v["duration"]) > 300][:20]

# De-duplicate
seen = set()
all_core = []
for cat, name, vlist in [
    ("RBI", "RBI Framework", rbi),
    ("FABLE", "Fable 5", fable5),
    ("BEGIN", "Beginner", beginner),
    ("ARCH", "Architecture", arch),
    ("DATA", "Data & Edge", data),
]:
    for v in vlist:
        if v["id"] not in seen:
            seen.add(v["id"])
            all_core.append(
                {
                    "cat": cat,
                    "name": name,
                    "id": v["id"],
                    "title": v["title"],
                    "duration": v["duration"],
                    "has_transcript": v["id"] in index,
                }
            )

# Write plan
plan_path = BASE / "reading_plan.json"
with open(plan_path, "w") as f:
    json.dump(all_core, f, indent=1)

print(f"=== CORE READING PLAN ({len(all_core)} videos) ===")
print()
current_cat = None
for v in all_core:
    if v["cat"] != current_cat:
        current_cat = v["cat"]
        print(f"\n{'=' * 60}")
        print(f"  {v['name']} ({len([x for x in all_core if x['cat'] == v['cat']])} videos)")
        print(f"{'=' * 60}")
    dur_m = int(v["duration"]) // 60
    dur_s = int(v["duration"]) % 60
    status = "✓" if v["has_transcript"] else " "
    print(f"  [{status}] {v['id']}  {dur_m:3d}:{dur_s:02d}  {v['cat']}  {v['title'][:80]}")

print(f"\n\nTotal core: {len(all_core)} videos")
print(f"With transcripts: {sum(1 for v in all_core if v['has_transcript'])}")
