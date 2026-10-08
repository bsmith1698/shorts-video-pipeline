#!/usr/bin/env python3
"""
Extracts real audio clips for a batch of queue.json candidates to local mp3
files, using the same curl-range-against-cached-bitrate method proven in
quality_extract_transcribe.py (remote ffmpeg -ss seeking against
apolloinrealtime.org does NOT range-seek -- see that script's docstring).

Unlike quality_extract_transcribe.py, this does NOT transcribe -- it just
extracts, so the resulting mp3s can be batch-uploaded to a rented GPU for
faster-whisper transcription instead of running whisper-cli locally on CPU.

Usage:
  python3 bulk_extract_audio.py --source nasa --unscored-only
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "queue.json"
BITRATE_CACHE_PATH = ROOT / "_archive" / "quality_pass" / "bitrate_cache.json"
OUT_DIR = ROOT / "_archive" / "quality_pass" / "bulk_audio"
PAD_S = 1.0


def load_bitrate_cache():
    if BITRATE_CACHE_PATH.exists():
        return json.loads(BITRATE_CACHE_PATH.read_text())
    return {}


def save_bitrate_cache(cache):
    BITRATE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BITRATE_CACHE_PATH.write_text(json.dumps(cache, indent=2))


def get_bitrate(url, cache):
    if url in cache:
        return cache[url]
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=bit_rate",
         "-of", "default=noprint_wrappers=1:nokey=1", url],
        capture_output=True, text=True, timeout=30,
    )
    bit_rate = int(r.stdout.strip()) if r.stdout.strip().isdigit() else None
    cache[url] = bit_rate
    save_bitrate_cache(cache)
    return bit_rate


def curl_range(url, start_byte, end_byte, out_path):
    r = subprocess.run(
        ["curl", "-s", "-f", "-H", f"Range: bytes={start_byte}-{end_byte}",
         "-o", str(out_path), url],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        return False, f"curl range fetch failed (rc={r.returncode}): {r.stderr.strip()[-500:]}"
    if not out_path.exists() or out_path.stat().st_size < 500:
        return False, "curl produced no/tiny output"
    return True, None


def curl_full(url, out_path):
    r = subprocess.run(
        ["curl", "-s", "-f", "-o", str(out_path), url],
        capture_output=True, text=True, timeout=90,
    )
    if r.returncode != 0:
        return False, f"curl full fetch failed (rc={r.returncode}): {r.stderr.strip()[-500:]}"
    if not out_path.exists() or out_path.stat().st_size < 500:
        return False, "curl produced no/tiny output"
    return True, None


def extract_one(cand, bitrate_cache):
    slug = cand["slug"]
    out_path = OUT_DIR / f"{slug}.mp3"
    if out_path.exists() and out_path.stat().st_size > 500:
        return "skip"
    url = cand["audio_source_url"]
    if cand["source"] == "nasa":
        offset = cand.get("audio_source_offset_s") or 0
        dur = cand.get("audio_source_duration_s") or 30
        bit_rate = get_bitrate(url, bitrate_cache)
        if not bit_rate:
            return f"FAIL(no bitrate): {slug}"
        bytes_per_sec = bit_rate / 8
        start_byte = max(0, int(bytes_per_sec * max(0, offset - PAD_S)))
        end_byte = int(bytes_per_sec * (offset + dur + PAD_S))
        ok, err = curl_range(url, start_byte, end_byte, out_path)
    else:
        ok, err = curl_full(url, out_path)
    if not ok:
        return f"FAIL({err}): {slug}"
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["nasa", "dvids"], required=True)
    ap.add_argument("--unscored-only", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    queue = json.loads(QUEUE_PATH.read_text())
    candidates = [c for c in queue if c["source"] == args.source]
    if args.unscored_only:
        candidates = [c for c in candidates if not c.get("quality_score")]

    bitrate_cache = load_bitrate_cache()
    print(f"Extracting {len(candidates)} candidates...")
    counts = {"ok": 0, "skip": 0, "fail": 0}
    fails = []
    for i, cand in enumerate(candidates, 1):
        result = extract_one(cand, bitrate_cache)
        if result == "ok":
            counts["ok"] += 1
        elif result == "skip":
            counts["skip"] += 1
        else:
            counts["fail"] += 1
            fails.append(result)
        if i % 25 == 0 or i == len(candidates):
            print(f"[{i}/{len(candidates)}] {counts}", flush=True)

    print(f"\nDone. {counts}")
    if fails:
        print("Failures:", file=sys.stderr)
        for f in fails:
            print(f"  {f}", file=sys.stderr)


if __name__ == "__main__":
    main()
