#!/usr/bin/env python3
"""Download missing Moon Dev transcripts via yt-dlp CLI.

Fixes vs original:
- uses yt-dlp binary (python -m yt_dlp is not installed)
- also writes official --write-subs, not only auto-subs
- accepts vtt if srt conversion fails
- sequential with 2 retries, rate-limit sleep
- writes transcripts_manifest.csv for all 356 videos
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/home/alin/_repos/oracle-trading/trading-os/video-library")
TSV = BASE / "moondev_videos.tsv"
OUT = BASE / "transcripts"
MANIFEST = BASE / "transcripts_manifest.csv"
OUT.mkdir(exist_ok=True)

YTDLP = shutil.which("yt-dlp") or str(Path.home() / ".local/bin/yt-dlp")
MAX_RETRIES = 2
SLEEP_BETWEEN = 1.5
TIMEOUT = 180


def parse_srt_or_vtt(text: str) -> str:
    lines: list[str] = []
    cur_time = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if line.startswith("NOTE"):
            continue
        m = re.match(
            r"(\d{2}:\d{2}:\d{2})[,.](\d{3})\s*-->\s*\d{2}:\d{2}:\d{2}",
            line,
        )
        if m:
            cur_time = m.group(1)
            continue
        # drop cue settings / alignment tags
        line = re.sub(r"<[^>]+>", "", line)
        line = line.replace("&nbsp;", " ").replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<")
        if line and not line.isdigit() and "align:" not in line and "position:" not in line:
            lines.append(f"[{cur_time}] {line}" if cur_time else line)
    # collapse consecutive duplicate caption lines (common in auto-subs)
    collapsed: list[str] = []
    prev_text = None
    for ln in lines:
        text_only = re.sub(r"^\[\d{2}:\d{2}:\d{2}\]\s*", "", ln)
        if text_only == prev_text:
            continue
        collapsed.append(ln)
        prev_text = text_only
    return "\n".join(collapsed)


def find_caption_file(video_id: str) -> Path | None:
    candidates = [
        OUT / f"{video_id}.en.srt",
        OUT / f"{video_id}.en.vtt",
        OUT / f"{video_id}.srt",
        OUT / f"{video_id}.vtt",
        OUT / f"{video_id}.en-orig.srt",
        OUT / f"{video_id}.en-orig.vtt",
        OUT / f"{video_id}.en-US.srt",
        OUT / f"{video_id}.en-US.vtt",
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return p
    # glob leftovers yt-dlp may write
    for p in OUT.glob(f"{video_id}*"):
        if p.suffix.lower() in {".srt", ".vtt"} and p.stat().st_size > 0:
            return p
    return None


def ytdlp_cmd(video_id: str) -> list[str]:
    return [
        YTDLP,
        "--skip-download",
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs",
        "en.*,en",
        "--convert-subs",
        "srt",
        "--no-playlist",
        "--no-warnings",
        "--retries",
        "2",
        "--fragment-retries",
        "2",
        "--socket-timeout",
        "30",
        "-o",
        str(OUT / "%(id)s"),
        f"https://www.youtube.com/watch?v={video_id}",
    ]


def fetch_one(video_id: str) -> tuple[str, str]:
    """Return (status, log_tail). status in ok|no_subtitles|error."""
    txt_path = OUT / f"{video_id}.txt"
    last_log = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = subprocess.run(
                ytdlp_cmd(video_id),
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
            last_log = ((r.stderr or "") + "\n" + (r.stdout or ""))[-800:]
        except subprocess.TimeoutExpired:
            last_log = "timeout"
            time.sleep(SLEEP_BETWEEN * attempt)
            continue
        except Exception as e:
            last_log = str(e)[:400]
            time.sleep(SLEEP_BETWEEN * attempt)
            continue

        cap = find_caption_file(video_id)
        if cap is not None:
            raw = cap.read_text(encoding="utf-8", errors="replace")
            txt = parse_srt_or_vtt(raw)
            if txt.strip():
                txt_path.write_text(txt, encoding="utf-8")
                return "ok", ""
            last_log = "caption file empty after parse"
        else:
            combined = last_log.lower()
            if any(
                s in combined
                for s in (
                    "has no subtitles",
                    "no subtitles",
                    "there are no subtitles",
                    "subtitles are disabled",
                    "did not get any",
                )
            ):
                return "no_subtitles", last_log
        time.sleep(SLEEP_BETWEEN * attempt)

    combined = last_log.lower()
    if any(
        s in combined
        for s in (
            "has no subtitles",
            "no subtitles",
            "there are no subtitles",
            "subtitles are disabled",
            "did not get any",
        )
    ):
        return "no_subtitles", last_log
    if find_caption_file(video_id) is None:
        # no file after retries: treat as no_subtitles unless network/error signals
        if any(s in combined for s in ("http error", "unavailable", "private", "sign in", "403", "429", "blocked")):
            return "error", last_log
        return "no_subtitles", last_log
    return "error", last_log


def load_videos() -> list[dict]:
    videos = []
    with TSV.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            parts = line.split("\t") if "\t" in line else re.split(r"\\t", line)
            if len(parts) >= 2:
                videos.append(
                    {
                        "id": parts[0].strip(),
                        "title": parts[1].strip() if len(parts) > 1 else "",
                        "duration": parts[2].strip() if len(parts) > 2 else "",
                    }
                )
    return videos


def write_manifest(rows: list[dict]) -> None:
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "title", "duration", "status", "file"])
        for r in rows:
            w.writerow([r["id"], r["title"], r["duration"], r["status"], r["file"]])


def main() -> int:
    if not Path(YTDLP).exists():
        print(f"yt-dlp not found at {YTDLP}", file=sys.stderr)
        return 2
    videos = load_videos()
    print(f"yt-dlp={YTDLP} videos={len(videos)}", flush=True)

    statuses: dict[str, dict] = {}
    todo = []
    for v in videos:
        txt = OUT / f"{v['id']}.txt"
        if txt.exists() and txt.stat().st_size > 0:
            statuses[v["id"]] = {**v, "status": "ok", "file": f"transcripts/{v['id']}.txt"}
        else:
            todo.append(v)

    print(f"already_ok={len(statuses)} todo={len(todo)}", flush=True)

    ok = nsub = err = 0
    for i, v in enumerate(todo, 1):
        status, log = fetch_one(v["id"])
        file_rel = f"transcripts/{v['id']}.txt" if status == "ok" else ""
        statuses[v["id"]] = {**v, "status": status, "file": file_rel}
        if status == "ok":
            ok += 1
        elif status == "no_subtitles":
            nsub += 1
        else:
            err += 1
        extra = ""
        if status != "ok":
            extra = " | " + log.replace("\n", " ")[:180]
        print(f"[{i}/{len(todo)}] {status} {v['id']} {v['title'][:50]}{extra}", flush=True)
        time.sleep(SLEEP_BETWEEN)

        # incremental manifest so a kill still leaves a usable file
        if i % 10 == 0 or i == len(todo):
            rows = []
            for vv in videos:
                s = statuses.get(vv["id"], {**vv, "status": "error", "file": ""})
                rows.append(s)
            write_manifest(rows)

    rows = []
    counts = {"ok": 0, "no_subtitles": 0, "error": 0}
    for v in videos:
        s = statuses.get(v["id"])
        if s is None:
            s = {**v, "status": "error", "file": ""}
        if s["status"] not in counts:
            s["status"] = "error"
        counts[s["status"]] += 1
        rows.append(s)
    write_manifest(rows)
    print(
        f"DONE ok={counts['ok']} no_subtitles={counts['no_subtitles']} error={counts['error']} total={len(rows)}",
        flush=True,
    )
    print(f"manifest={MANIFEST}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
