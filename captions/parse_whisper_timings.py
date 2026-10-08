#!/usr/bin/env python3
"""Merge whisper.cpp -oj JSON output per VO line into a single wordTimings.json
for Remotion's KaraokeCaption component. Usage:
  python3 parse_whisper_timings.py <out.json> <key1>=<path1.json> [<key2>=<path2.json> ...]
"""
import json
import re
import sys

PUNCT_RE = re.compile(r"^[.,!?;:\"'’]+$")


def redistribute_degenerate_clusters(words):
    """On noisy/garbled audio (e.g. VHF marine radio), whisper.cpp's per-word
    alignment sometimes collapses — several consecutive words all get stamped
    at the exact same startMs instead of spreading across the time they
    actually took to say. Left as-is, karaoke captions render that whole
    cluster as appearing/vanishing at one instant, which reads as "wrong" or
    "out of sync" even though the WORDS are usually still correct. Detect
    runs of 2+ consecutive words sharing an identical startMs and spread them
    proportionally (by character length, with a minimum floor) across the
    real gap up to the next word with a distinct startMs. Does not change
    word content, only timing."""
    i = 0
    n = len(words)
    while i < n:
        j = i
        shared_start = words[i]["startMs"]
        while j < n and words[j]["startMs"] == shared_start:
            j += 1
        group = words[i:j]
        if len(group) >= 2:
            left = shared_start
            right = words[j]["startMs"] if j < n else left + max(150 * len(group), 300)
            avail = max(right - left, 100)
            min_floor = min(80, avail / len(group))
            weights = [max(len(w["word"]), 1) for w in group]
            total_weight = sum(weights)
            raw = [max(min_floor, avail * wt / total_weight) for wt in weights]
            scale = avail / sum(raw)
            cursor = left
            for w, r in zip(group, raw):
                dur = r * scale
                w["startMs"] = round(cursor)
                cursor += dur
                w["endMs"] = round(cursor)
        i = j
    return words


def parse_one(path):
    data = json.load(open(path))
    words = []
    for entry in data["transcription"]:
        text = entry["text"]
        if text.strip() == "":
            continue
        start = entry["offsets"]["from"]
        end = entry["offsets"]["to"]
        is_new = text.startswith(" ")
        clean = text.strip()
        if PUNCT_RE.match(clean):
            if words:
                words[-1]["endMs"] = max(words[-1]["endMs"], end)
            continue
        if is_new or not words:
            words.append({"word": clean, "startMs": start, "endMs": end})
        else:
            words[-1]["word"] += clean
            words[-1]["endMs"] = end
    return redistribute_degenerate_clusters(words)


def main():
    out_path = sys.argv[1]
    result = {}
    for pair in sys.argv[2:]:
        key, path = pair.split("=", 1)
        result[key] = parse_one(path)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {out_path} with keys: {list(result.keys())}")


if __name__ == "__main__":
    main()
