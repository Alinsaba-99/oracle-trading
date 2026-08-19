#!/usr/bin/env python3
"""Build transcripts_manifest.csv from moondev_videos.tsv + transcripts/index.json."""
import csv
import json
import re
from pathlib import Path

BASE = Path("/home/alin/_repos/oracle-trading/trading-os/video-library")
TSV = BASE / "moondev_videos.tsv"
OUT = BASE / "transcripts"
INDEX = json.loads((OUT / "index.json").read_text(encoding="utf-8"))

videos = []
for line in TSV.read_text(encoding="utf-8", errors="replace").splitlines():
    parts = line.split("\t") if "\t" in line else re.split(r"\\t", line)
    if len(parts) >= 2:
        videos.append({"id": parts[0], "title": parts[1],
                       "duration": parts[2] if len(parts) > 2 else ""})

rows, counts = [], {"ok": 0, "no_subtitles": 0, "error": 0}
for v in videos:
    info = INDEX.get(v["id"], {})
    raw = info.get("status", "")
    if raw == "ok" and (OUT / f"{v['id']}.txt").exists():
        status, fname = "ok", f"transcripts/{v['id']}.txt"
    elif raw == "no_subs":
        status, fname = "no_subtitles", ""
    else:
        status, fname = "error", ""
    counts[status] += 1
    rows.append({"video_id": v["id"], "title": v["title"],
                 "duration": v["duration"], "status": status, "file": fname})

with (BASE / "transcripts_manifest.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["video_id", "title", "duration", "status", "file"])
    w.writeheader()
    w.writerows(rows)

print(f"rows={len(rows)}")
print(f"ok={counts['ok']} no_subtitles={counts['no_subtitles']} error={counts['error']}")
print(f"sum={sum(counts.values())}")
# verify: every ok row has its file
missing = [r["video_id"] for r in rows if r["status"] == "ok"
           and not (BASE / r["file"]).exists()]
print(f"missing_files_for_ok={len(missing)}")
