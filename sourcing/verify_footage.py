#!/usr/bin/env python3
"""Verify DVIDS footage pairings before a candidate can be trusted as
"real matching footage" — automates the two checks that have been done by
hand (inconsistently) and have each caused a shipped-video problem:

1. Incident match: `footage_paired: true` from sourcing_dvids.py only means
   "a video exists from the same unit within +/-7 days" — an early audit
   found 9 of 11 "paired" candidates are same-unit B-roll
   about a *different* story, not the incident on the audio. This script
   checks for an actual title match, not just presence.
2. Legibility: a confirmed same-incident match can still be visually
   unusable (dvids-audio-45403's Predator fire matched real footage that was
   a 720x480 low-bitrate night shot nobody could read once cropped). DVIDS'
   own `/asset` response includes a real timestamped frame thumbnail plus a
   `files` list of every encoded resolution, so both the "is there real
   detail" and "what's the resolution ceiling" checks are free API calls,
   no video download needed for the metadata half.

Downloads a thumbnail frame + two mp4-extracted frames per matched
candidate into _archive/footage_verify/<slug>/ for a human/Claude visual
read — this script only computes the objective signals (title match tier,
resolution ceiling, black-frame brightness check). It does not make the
final legible/not-legible call; that still needs eyes on the frames.

Idempotent: skips any entry that already has a `footage_check` block unless
--recheck is passed. Never mutates status/verified/hook — only adds the
footage_check field, same PRESERVE_FIELDS-safe pattern as the other queue
writers.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcing_dvids import call, ASSET, load_api_key  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = REPO_ROOT / "queue.json"
FRAMES_DIR = REPO_ROOT / "_archive" / "footage_verify"

STOPWORDS = {
    "a", "an", "the", "of", "off", "from", "for", "to", "in", "on", "near",
    "coast", "guard", "coastguard", "responds", "response", "rescue",
    "rescues", "rescued", "assists", "assisted", "assist", "call", "calls",
    "mayday", "distress", "vessel", "boat", "crew", "u.s.",
}


def normalize_title(title):
    words = re.findall(r"[a-z0-9']+", (title or "").lower())
    return [w for w in words if w not in STOPWORDS]


def title_match_tier(audio_title, video_title):
    """'exact' = same normalized token set (after stripping generic Coast
    Guard boilerplate words) — the only tier Finding #3 found to be a real
    same-incident signal in practice. 'none' otherwise; a deliberately high
    bar since every false positive so far has been a same-unit coincidence,
    not a near-miss wording difference."""
    a = set(normalize_title(audio_title))
    v = set(normalize_title(video_title))
    if not a or not v:
        return "none"
    if a == v:
        return "exact"
    # allow one distinctive word of drift either way (e.g. a trailing state name)
    if len(a - v) <= 1 and len(v - a) <= 1 and len(a & v) >= max(2, len(a) - 1):
        return "exact"
    return "none"


def fetch_video_asset(video_id):
    time.sleep(0.15)
    data = call(ASSET, {"id": video_id})
    return data.get("results", {})


def pick_frame_encode(files):
    """Smallest encode that's still >=480px wide — enough to judge
    legibility without downloading the full-res file."""
    candidates = [f for f in (files or []) if (f.get("width") or 0) >= 480]
    pool = candidates or (files or [])
    if not pool:
        return None
    return min(pool, key=lambda f: f.get("width") or 99999)


def max_resolution(files):
    if not files:
        return None
    best = max(files, key=lambda f: f.get("width") or 0)
    return f"{best.get('width')}x{best.get('height')}"


def download(url, out_path, timeout=30):
    try:
        subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-o", str(out_path), url],
            check=True, timeout=timeout + 5,
        )
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception as e:
        print(f"    thumbnail download failed: {e}")
        return False


def extract_frame(video_url, offset_s, out_path, timeout=40):
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(offset_s), "-i", video_url,
             "-frames:v", "1", "-q:v", "2", str(out_path)],
            check=True, timeout=timeout,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception as e:
        print(f"    frame extract failed at {offset_s}s: {e}")
        return False


def brightness(path):
    try:
        from PIL import Image
        import numpy as np
        arr = np.array(Image.open(path).convert("L"))
        return round(float(arr.mean()), 1)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recheck", action="store_true",
                     help="re-run even for entries that already have footage_check")
    ap.add_argument("--slug", help="only process this one slug (debugging)")
    args = ap.parse_args()

    queue = json.loads(QUEUE_PATH.read_text())

    targets = [
        e for e in queue
        if e.get("source") == "dvids"
        and e.get("status") == "candidate"
        and e.get("dvids", {}).get("video_asset_ids")
        and (args.recheck or "footage_check" not in e)
        and (not args.slug or e["slug"] == args.slug)
    ]
    print(f"{len(targets)} DVIDS candidates with a paired video to check.")

    needs_review = []

    for entry in targets:
        slug = entry["slug"]
        d = entry["dvids"]
        audio_title = d.get("title") or ""
        video_ids = d.get("video_asset_ids") or []
        video_titles = d.get("video_titles") or []

        print(f"\n{slug}: audio title = {audio_title!r}")

        best = None  # (tier, video_id, title)
        for vid, vtitle in zip(video_ids, video_titles):
            tier = title_match_tier(audio_title, vtitle)
            print(f"    {vid}  [{tier}]  {vtitle!r}")
            if tier == "exact":
                best = (tier, vid, vtitle)
                break  # first exact match wins, matches sourcing order

        if not best:
            entry["footage_check"] = {
                "incident_match": "none",
                "note": "no video title matched the audio's incident closely enough — "
                        "treat footage_paired as a same-unit coincidence, not usable footage",
            }
            print("    -> no incident-matched video. Not usable as-is.")
            continue

        tier, video_id, video_title = best
        asset = fetch_video_asset(video_id)
        files = asset.get("files") or []
        thumb_url = asset.get("image")
        duration = asset.get("duration") or 0

        out_dir = FRAMES_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        frame_paths = []
        brightness_vals = []

        if thumb_url:
            p = out_dir / "thumb.jpg"
            if download(thumb_url, p):
                frame_paths.append(str(p))
                brightness_vals.append(brightness(p))

        encode = pick_frame_encode(files)
        if encode and duration:
            for label, frac in (("mid", 0.5), ("late", 0.8)):
                p = out_dir / f"{label}.jpg"
                if extract_frame(encode["src"], duration * frac, p):
                    frame_paths.append(str(p))
                    brightness_vals.append(brightness(p))

        valid_brightness = [b for b in brightness_vals if b is not None]
        likely_black = bool(valid_brightness) and max(valid_brightness) < 15

        entry["footage_check"] = {
            "incident_match": tier,
            "matched_video_asset_id": video_id,
            "matched_video_title": video_title,
            "max_resolution": max_resolution(files),
            "frame_paths": frame_paths,
            "frame_brightness": brightness_vals,
            "likely_black_track": likely_black,
            "needs_visual_review": not likely_black and bool(frame_paths),
        }
        print(f"    -> exact match: {video_title!r} | max_res {max_resolution(files)} "
              f"| black_track={likely_black} | frames saved: {len(frame_paths)}")

        if not likely_black and frame_paths:
            needs_review.append(slug)

    QUEUE_PATH.write_text(json.dumps(queue, indent=2))
    print(f"\nWrote footage_check for {len(targets)} candidates to {QUEUE_PATH}")
    print(f"{len(needs_review)} candidates have real frames saved and need a visual legibility read:")
    for s in needs_review:
        print(f"  {s}  ->  {FRAMES_DIR / s}")


if __name__ == "__main__":
    main()
