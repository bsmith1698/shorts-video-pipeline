#!/usr/bin/env python3
"""
Mechanical half of the quality-verification pass: for each queue.json candidate,
extract the real audio clip and transcribe it with whisper large-v3. Writes one
JSONL line per candidate to a checkpoint file as it goes, so it can be killed
and resumed without redoing work already done.

This script does NOT judge quality. Scoring against the real transcript is a
separate, human/LLM judgment step (see docs/archival-funnel.md for
why: a keyword/heuristic scorer is what got us here). This script's only job is
turning audio_source_url into a real transcript.

Extraction method note: ffmpeg's own "-ss before -i" remote seek against the
apolloinrealtime.org CDN turned out NOT to be the ~2000x-realtime range-seek
earlier notes described for deep offsets -- debug logging
showed it issuing "Range: bytes=0-" and reading the file linearly from byte 0
up to the seek target every time (confirmed reproducible, ~5 min for a seek
90% into a 120MB file). A raw HTTP Range request at the same deep byte offset
via curl took 0.8s. So this script computes the byte range itself (from each
unique URL's real CBR bitrate, probed once via ffprobe and cached) and lets
curl do the seek; whisper-cli decodes the mp3 segment directly (mp3 decoders
resync on frame boundaries, so a non-frame-aligned start is harmless -- no
local ffmpeg re-encode step needed). DVIDS URLs are just downloaded whole
(they're already short, single clips at offset 0).

Usage:
  python3 quality_extract_transcribe.py --slugs slug1,slug2,...
  python3 quality_extract_transcribe.py --source nasa
  python3 quality_extract_transcribe.py --all
  python3 quality_extract_transcribe.py --all --force   # redo even if checkpointed
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "queue.json"
CHECKPOINT_PATH = ROOT / "_archive" / "quality_pass" / "transcripts_checkpoint.jsonl"
BITRATE_CACHE_PATH = ROOT / "_archive" / "quality_pass" / "bitrate_cache.json"
AUDIO_DIR = ROOT / "_archive" / "quality_pass" / "audio"
WHISPER_BIN = "whisper-cli"
WHISPER_MODEL = str(Path.home() / "whisper-models" / "ggml-large-v3.bin")
PAD_S = 1.0  # seconds of safety padding on each side of the byte-range fetch


def load_checkpoint_done():
    done = {}
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                done[rec["slug"]] = rec
    return done


def append_checkpoint(rec):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")


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


def extract_audio(cand, out_mp3, bitrate_cache):
    url = cand["audio_source_url"]
    if cand["source"] == "nasa":
        offset = cand.get("audio_source_offset_s") or 0
        dur = cand.get("audio_source_duration_s") or 30
        bit_rate = get_bitrate(url, bitrate_cache)
        if not bit_rate:
            return False, f"could not determine bitrate for {url}"
        bytes_per_sec = bit_rate / 8
        start_byte = max(0, int(bytes_per_sec * max(0, offset - PAD_S)))
        end_byte = int(bytes_per_sec * (offset + dur + PAD_S))
        return curl_range(url, start_byte, end_byte, out_mp3)
    else:
        return curl_full(url, out_mp3)


def transcribe(mp3_path, out_prefix):
    cmd = [
        WHISPER_BIN,
        "-m", WHISPER_MODEL,
        "-f", str(mp3_path),
        "-otxt",
        "-of", str(out_prefix),
        "-nt",  # no timestamps in the text output
        "-l", "en",
        "-np",  # no extra prints, keep stdout clean
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    txt_path = Path(str(out_prefix) + ".txt")
    if not txt_path.exists():
        return None, f"whisper produced no output (rc={r.returncode}, stderr: {r.stderr.strip()[-1000:]})"
    text = txt_path.read_text().strip()
    return text, None


def process_one(cand, force, done, bitrate_cache):
    slug = cand["slug"]
    if not force and slug in done and done[slug].get("transcript") is not None:
        return "skip"

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    mp3_path = AUDIO_DIR / f"{slug}.mp3"
    out_prefix = AUDIO_DIR / slug

    ok, err = extract_audio(cand, mp3_path, bitrate_cache)
    if not ok:
        append_checkpoint({
            "slug": slug, "source": cand["source"], "transcript": None,
            "error": f"extract_failed: {err}", "ts": time.time(),
        })
        return "extract_fail"

    text, terr = transcribe(mp3_path, out_prefix)
    if terr:
        append_checkpoint({
            "slug": slug, "source": cand["source"], "transcript": None,
            "error": f"whisper_failed: {terr}", "ts": time.time(),
        })
        # keep the mp3 for a manual retry, don't clean up on failure
        return "whisper_fail"

    append_checkpoint({
        "slug": slug, "source": cand["source"], "transcript": text,
        "error": None, "ts": time.time(),
    })

    # clean up scratch audio now that we have the transcript
    try:
        mp3_path.unlink()
        Path(str(out_prefix) + ".txt").unlink()
    except OSError:
        pass

    return "ok"


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slugs", help="comma-separated list of slugs")
    g.add_argument("--source", choices=["nasa", "dvids"])
    g.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true", help="redo even if checkpointed")
    args = ap.parse_args()

    queue = json.loads(QUEUE_PATH.read_text())
    if args.slugs:
        wanted = set(args.slugs.split(","))
        candidates = [c for c in queue if c["slug"] in wanted]
        missing = wanted - {c["slug"] for c in candidates}
        if missing:
            print(f"WARNING: slugs not found in queue.json: {missing}", file=sys.stderr)
    elif args.source:
        candidates = [c for c in queue if c["source"] == args.source]
    else:
        candidates = queue

    done = load_checkpoint_done()
    bitrate_cache = load_bitrate_cache()
    print(f"Processing {len(candidates)} candidates ({len(done)} already checkpointed)...")

    counts = {"ok": 0, "skip": 0, "extract_fail": 0, "whisper_fail": 0}
    t0 = time.time()
    for i, cand in enumerate(candidates, 1):
        result = process_one(cand, args.force, done, bitrate_cache)
        counts[result] += 1
        elapsed = time.time() - t0
        print(f"[{i}/{len(candidates)}] {cand['slug']} -> {result}  (elapsed {elapsed:.0f}s)", flush=True)

    print(f"\nDone. {counts}")
    print(f"Checkpoint file: {CHECKPOINT_PATH}")


if __name__ == "__main__":
    main()
