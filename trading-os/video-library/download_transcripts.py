#!/usr/bin/env python3
"""Bulk transcript downloader for Moon Dev YouTube videos.

Reads moondev_videos.tsv (id\ttitle\tduration), downloads auto-subs (en)
for each video via yt-dlp, converts to clean text, writes:
  transcripts/<video_id>.txt          (clean readable text)
  transcripts/<video_id>.srt          (timestamped captions)
  transcripts/index.json              (metadata for all videos)
"""

import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path(__file__).resolve().parent
TSV = BASE / "moondev_videos.tsv"
OUT = BASE / "transcripts"
OUT.mkdir(exist_ok=True)

YDL_ARGS = [
    sys.executable,
    "-m",
    "yt_dlp",
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
    "--no-playlist",
]


def sanitize_title(title: str) -> str:
    """Short, filesystem-safe title fragment."""
    t = re.sub(r"[^\w\s-]", "", title).strip()
    t = re.sub(r"\s+", "_", t)
    return t[:60] or "untitled"


def parse_srt(srt_text: str) -> str:
    """Strip SRT numbering/timestamps -> readable transcript with timecodes."""
    lines = []
    cur_time = None
    for raw in srt_text.splitlines():
        line = raw.strip()
        m = re.match(r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})", line)
        if m:
            cur_time = m.group(1).replace(",", ".")[:8]
            continue
        if line and not line.isdigit() and "<" not in line and "&" not in line:
            lines.append(f"[{cur_time}] {line}" if cur_time else line)
    return "\n".join(lines)


def fetch_one(video_id: str, title: str) -> dict:
    """Download subs for one video. Returns status info."""
    result = {"id": video_id, "title": title, "status": "pending", "chars": 0}
    srt_path = OUT / f"{video_id}.en.srt"
    txt_path = OUT / f"{video_id}.txt"
    try:
        r = subprocess.run(
            YDL_ARGS + [f"https://www.youtube.com/watch?v={video_id}"],
            cwd=str(OUT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if srt_path.exists():
            srt_text = srt_path.read_text(encoding="utf-8", errors="replace")
            txt = parse_srt(srt_text)
            txt_path.write_text(txt, encoding="utf-8")
            result["status"] = "ok"
            result["chars"] = len(txt)
            result["srt_bytes"] = len(srt_text.encode())
        else:
            result["status"] = "no_subs"
            result["log_tail"] = (r.stderr or "")[-300:]
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:200]
    return result


def main():
    videos = []
    with TSV.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            # Handle literal '\t' (file was written with printf '\t' escape) or real tab
            parts = line.split("\t") if "\t" in line else re.split(r"\\t", line)
            if len(parts) >= 2:
                videos.append({"id": parts[0], "title": parts[1]})
    print(f"Loaded {len(videos)} videos")

    # Only fetch videos that don't already have a transcript
    todo = [v for v in videos if not (OUT / f"{v['id']}.txt").exists()]
    print(f"To fetch: {len(todo)} (already have {len(videos) - len(todo)})")

    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    if not isinstance(index, dict):
        index = {}

    done = 0
    ok = 0
    fail = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_one, v["id"], v["title"]): v for v in todo}
        for fut in as_completed(futs):
            info = fut.result()
            done += 1
            idx = info["id"]
            stored = index.get(idx, {})
            stored.update(
                {
                    "id": idx,
                    "title": info["title"],
                    "status": info["status"],
                    "chars": info.get("chars", 0),
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            index[idx] = stored
            if info["status"] == "ok":
                ok += 1
                print(
                    f"[{done}/{len(todo)}] OK  {idx} {info['chars']:>6} chars  {info['title'][:50]}"
                )
            else:
                fail += 1
                print(f"[{done}/{len(todo)}] {info['status'].upper()} {idx} {info['title'][:50]}")
            if done % 20 == 0:
                index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")

    index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"\nDONE: {ok} ok, {fail} failed/missing, {len(videos)} total")
    print(f"Transcripts dir: {OUT}")


if __name__ == "__main__":
    main()
