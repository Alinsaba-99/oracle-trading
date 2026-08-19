#!/usr/bin/env python3
"""Retry missing transcripts with cookies + rate limiting."""

import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path(__file__).resolve().parent
COOKIES = "C:/Users/Administrator/trading-os/video-library/edge_cookies.txt"
OUT = BASE / "transcripts"
INDEX = OUT / "index.json"

YDL = [
    sys.executable,
    "-m",
    "yt_dlp",
    "--cookies",
    COOKIES,
    "--skip-download",
    "--write-auto-subs",
    "--sub-lang",
    "en",
    "--sub-format",
    "srt",
    "--convert-subs",
    "srt",
    "--output",
    "%(id)s",
    "--sleep-requests",
    "0.5",
    "--no-playlist",
]

# Load missing videos from plan
plan = json.loads((BASE / "reading_plan.json").read_text(encoding="utf-8"))
index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
missing = [v for v in plan if v["id"] not in index or index[v["id"]].get("status") != "ok"]
print(f"Missing from plan: {len(missing)}")


def fetch_one(video_id: str, title: str) -> dict:
    result = {"id": video_id, "title": title, "status": "pending"}
    srt_path = OUT / f"{video_id}.en.srt"
    txt_path = OUT / f"{video_id}.txt"
    try:
        r = subprocess.run(
            YDL + [f"https://www.youtube.com/watch?v={video_id}"],
            cwd=str(OUT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if srt_path.exists():
            srt_text = srt_path.read_text(encoding="utf-8", errors="replace")
            txt = parse_srt(srt_text)
            txt_path.write_text(txt, encoding="utf-8")
            result["status"] = "ok"
            result["chars"] = len(txt)
        else:
            result["status"] = "no_subs"
            result["log"] = r.stderr[-500:]
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:200]
    return result


def parse_srt(srt_text: str) -> str:
    lines = []
    cur_time = None
    for raw in srt_text.splitlines():
        line = raw.strip()
        m = re.match(r"(\d{2}:\d{2}:\d{2})[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}", line)
        if m:
            cur_time = m.group(1)
            continue
        if line and not line.isdigit() and "<" not in line:
            lines.append(f"[{cur_time}] {line}" if cur_time else line)
    return "\n".join(lines)


done = 0
ok = 0
fail = 0
with ThreadPoolExecutor(max_workers=3) as ex:
    futs = {ex.submit(fetch_one, v["id"], v["title"]): v for v in missing}
    for fut in as_completed(futs):
        info = fut.result()
        done += 1
        idx = info["id"]
        status = info["status"]
        stored = index.get(idx, {})
        stored.update(
            {
                "id": idx,
                "title": info["title"],
                "status": status,
                "chars": info.get("chars", 0),
                "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        index[idx] = stored
        if status == "ok":
            ok += 1
            print(
                f"[{done}/{len(missing)}] OK  {idx} {info['chars']:>6} chars  {info['title'][:55]}"
            )
        else:
            fail += 1
            print(f"[{done}/{len(missing)}] {status.upper()} {idx}  {info['title'][:55]}")
        if done % 5 == 0:
            INDEX.write_text(json.dumps(index, indent=1), encoding="utf-8")

INDEX.write_text(json.dumps(index, indent=1), encoding="utf-8")
print(f"\nDONE: {ok} ok, {fail} failed, {len(missing)} total")
