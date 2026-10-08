#!/usr/bin/env python3
"""Grep + score the Apollo 13 MOCR transcript for candidate Shorts clips.

Source: _archive/unzipped/A13_all_channels.txt, one line per utterance:
  <GET_seconds>|CH<channel_number>|<text>
GET_seconds is Ground Elapsed Time (seconds, launch = 0), file is sorted ascending.

Channel numbers and real audio tape URLs come from apolloinrealtime.org's own
MOCRviz tool (js/MOCRviz.js + data/tape_ranges.csv), reverse-engineered rather
than guessed — see CHANNEL_NAMES and audio_url_for() below.

Output: queue.json in the repo root, top N scored candidates.
"""

import bisect
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPT = REPO_ROOT / "_archive" / "unzipped" / "A13_all_channels.txt"
TAPE_RANGES_CSV = REPO_ROOT / "_archive" / "tape_ranges.csv"
QUEUE_OUT = REPO_ROOT / "queue.json"

TOP_N = 400
WINDOW_SECONDS = 120  # +/- context window for cluster/channel/turnover scoring
MERGE_GAP_SECONDS = 25  # hits closer than this (in time) get merged into one candidate

# Restrict candidates to in-flight GET (liftoff to splashdown, ~142:54:41). Pre-launch
# countdown chatter uses "abort"/"verify"/"say again" as routine callout vocabulary with
# every channel active in lockstep, which dominated the scorer on volume alone without
# being a real "moment going wrong" in flight. Post-splashdown chatter is post-mission
# wrap-up, same issue. First scoring pass caught this empirically (see queue.json v1).
MIN_GET_SECONDS = 0
MAX_GET_SECONDS = 143 * 3600

# --- Channel numbers -> MOCR position names, from apolloinrealtime.org's MOCRviz.js cTrackInfo ---
CHANNEL_NAMES = {
    1: "HR1 Datastream", 2: "FLIGHT OPS DIR", 3: "MISSION DIRECTOR", 4: "DOD MANAGER",
    5: "PROCEDURES", 6: "ASST FLIGHT DIR", 7: "FLIGHT DIRECTOR [L]", 8: "FLIGHT DIRECTOR [R]",
    9: "FLIGHT ACTIVITIES OFFICER", 10: "NETWORK CTRLR [L]", 11: "NETWORK CTRLR [R]",
    12: "SURGEON [L]", 13: "SURGEON [R]", 14: "CAPCOM [L]", 15: "CAPCOM [R]",
    16: "CSM EECOM", 17: "POS EECOM", 18: "CSM GNC", 19: "RETRO", 20: "FIDO",
    21: "GUIDO [L]", 22: "GUIDO [R]", 23: "CCATS LOAD CONTROL", 24: "CCATS RTC",
    25: "CCATS CMD", 26: "CCATS TIC", 27: "CCATS TM", 28: "TRACK [L]", 29: "TRACK [R]",
    30: "HR1 VOICE ANNOTATION", 31: "HR2 Datastream", 32: "RECOVERY",
    33: "ASST NASA RCVY COORD", 34: "RECOVERY STATUS", 35: "RECOVERY EVALUATOR",
    36: "DOD COORD", 37: "DOD PRIMARY OP", 38: "DOD MANAGER [RCVY]", 39: "DOD EXEC",
    40: "DOD ASST FOR COMM 1", 41: "DOD PIO", 42: "COMM TECH [3RD FL]",
    43: "COMM CTRLR [3RD FL]", 44: "SPACE ENVIRONMENT", 45: "COMPUTER SUPERVISOR",
    46: "SPAN", 47: "BOOSTER [L]", 48: "BOOSTER [C]", 49: "BOOSTER [R]",
    50: "FLIGHT DIRECTOR LOOP", 51: "AFD CONF LOOP", 52: "GOSS 2 LOOP", 53: "INCO",
    54: "MOCR DYN LOOP", 55: "GOSS CONF LOOP", 56: "GOSS 4 LOOP", 57: "LM GNC",
    58: "TELMU", 59: "EXPMT ACTIVITIES OFSR", 60: "HR2 VOICE ANNOTATION",
}

# --- Tension-language phrase lists, weighted by stated priority ---
PHRASE_CATEGORIES = {
    "human_moments": (4.0, [
        "don't tell", "off the loop", "is this being recorded", "the crew doesn't know",
        "keep it quiet",
    ]),
    "decision_pressure": (3.0, [
        "your call", "we need a decision", "how long do we have", "abort", "go/no-go",
        "i don't like", "i'm not happy",
    ]),
    "uncertainty": (2.0, [
        "i don't know", "i'm not sure", "that doesn't make sense", "that can't be right",
        "say again", "verify that", "are you sure", "what the hell", "stand by one",
    ]),
    "alarm_failure": (1.0, [
        "master alarm", "caution and warning", "we just lost", "we've lost", "no data",
        "hardover", "off scale", "out of limits", "red line", "we have a problem",
        "malfunction", "failed", "runaway",
    ]),
}


def fmt_get(seconds: int) -> str:
    sign = "-" if seconds < 0 else ""
    s = abs(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{h:03d}:{m:02d}:{s:02d}"


def parse_get(s: str) -> int:
    s = s.strip()
    sign = -1 if s.startswith("-") else 1
    s = s.lstrip("-")
    h, m, sec = s.split(":")
    return sign * (int(h) * 3600 + int(m) * 60 + int(sec))


def parse_transcript_time(t_str: str) -> int:
    """Decode the transcript's own GET field.

    Despite the docstring's original assumption, this is NOT raw seconds-since-
    launch — it's a concatenated clock string (sign + H(H)(H) + MM + SS, no
    colons: negative/pre-launch entries are 6 digits wide (HH+MM+SS), positive/
    in-flight entries are 7 digits wide (HHH+MM+SS)). Confirmed 2026-08-13 by
    decoding known, precisely-documented Apollo 13 moments straight from this
    file and checking them against history:
      - '0555517' -> 055:55:17, matches the real "Houston, we've had a
        problem" call almost to the second. Read as raw seconds it's
        555517s = GET 154:18:37 -- past splashdown, impossible.
      - '0000601' -> 000:06:01, matches the real, tape-verified GET of the
        S-II inboard-engine-early CAPCOM call (see apollo13-inboard-out-short/
        SOURCING.md's independently-confirmed true window). Read as raw
        seconds it lands at GET 000:10:01 -- the exact wrong range that
        SOURCING.md already flagged as drifted off the real tape.
      - '-351712' -> -035:17:12, matches tape_ranges.csv's own stated
        earliest coverage (-35:17:25) within 13s. Read as raw seconds it's
        -097:41:52 -- earlier than the tape even starts.
    Last 4 digits are always MM+SS (2+2, fixed width); everything before that
    is the hour count, however many digits (no padding assumption needed).
    """
    sign = -1 if t_str.startswith("-") else 1
    s = t_str.lstrip("-")
    hh, mm, ss = s[:-4] or "0", s[-4:-2], s[-2:]
    return sign * (int(hh) * 3600 + int(mm) * 60 + int(ss))


def load_transcript():
    times, chans, texts = [], [], []
    with open(TRANSCRIPT, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("|", 2)
            if len(parts) != 3:
                continue
            t_str, ch_str, text = parts
            try:
                t = parse_transcript_time(t_str)
            except ValueError:
                continue
            ch = int(ch_str[2:]) if ch_str.startswith("CH") else None
            times.append(t)
            chans.append(ch)
            texts.append(text)
    return times, chans, texts


def load_tape_ranges():
    """channel<=30 -> HR1 ranges, channel>30 -> HR2 ranges. Each range: (tape_id, hr_label, start, end)."""
    hr1, hr2 = [], []
    if not TAPE_RANGES_CSV.exists():
        return hr1, hr2
    for line in TAPE_RANGES_CSV.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        tape, hr_label, start, end = line.split("|")
        rec = (tape, hr_label, parse_get(start), parse_get(end))
        (hr1 if "HR1" in hr_label else hr2).append(rec)
    hr1.sort(key=lambda r: r[2])
    hr2.sort(key=lambda r: r[2])
    return hr1, hr2


def audio_url_for(get_seconds: int, channel: int, hr1, hr2):
    """Returns (url, offset_seconds_into_tape_file) or (None, None)."""
    ranges = hr1 if channel <= 30 else hr2
    for tape, hr_label, start, end in ranges:
        if start <= get_seconds <= end:
            norm_ch = channel - 30 if channel > 30 else channel
            base = f"DA13_{tape}_{hr_label}_16khz_mp3_16"
            fname = f"DA13_{tape}_{hr_label}_CH{norm_ch}.mp3"
            url = f"https://media.apolloinrealtime.org/A13/MOCR_audio/{base}/{fname}"
            return url, get_seconds - start
    return None, None


def main():
    print("Loading transcript...")
    times, chans, texts = load_transcript()
    lower_texts = [t.lower() for t in texts]
    n = len(times)
    print(f"{n} lines loaded, GET range {fmt_get(times[0])} to {fmt_get(times[-1])}")

    hr1, hr2 = load_tape_ranges()

    print("Scanning for tension-language phrases...")
    raw_hits = []  # (index, category, weight, phrase)
    for category, (weight, phrases) in PHRASE_CATEGORIES.items():
        for phrase in phrases:
            for i, lt in enumerate(lower_texts):
                if phrase in lt:
                    raw_hits.append((i, category, weight, phrase))
    raw_hits = [h for h in raw_hits if MIN_GET_SECONDS <= times[h[0]] <= MAX_GET_SECONDS]
    raw_hits.sort(key=lambda h: times[h[0]])
    print(f"{len(raw_hits)} raw phrase hits (in-flight) across {len(set(h[0] for h in raw_hits))} lines")

    hit_times = [times[h[0]] for h in raw_hits]

    print("Scoring hits...")
    scored = []
    for hit_idx, (i, category, weight, phrase) in enumerate(raw_hits):
        t = times[i]
        lo = bisect.bisect_left(times, t - WINDOW_SECONDS)
        hi = bisect.bisect_right(times, t + WINDOW_SECONDS)

        window_chans = set(c for c in chans[lo:hi] if c is not None)
        channel_count = len(window_chans)

        turnover = sum(
            1 for j in range(lo + 1, hi) if chans[j] != chans[j - 1]
        )

        hlo = bisect.bisect_left(hit_times, t - WINDOW_SECONDS)
        hhi = bisect.bisect_right(hit_times, t + WINDOW_SECONDS)
        cluster_density = (hhi - hlo) - 1  # exclude self

        gap = times[i + 1] - t if i + 1 < n else 0
        silence_bonus = min(gap, 30) * 0.5

        score = (
            weight * 10
            + cluster_density * 3
            + channel_count * 2
            + turnover * 1
            + silence_bonus
        )

        scored.append({
            "index": i,
            "time": t,
            "category": category,
            "weight": weight,
            "phrase": phrase,
            "channel": chans[i],
            "channel_count": channel_count,
            "turnover": turnover,
            "cluster_density": cluster_density,
            "silence_gap_s": gap,
            "score": round(score, 2),
        })

    print("Merging nearby hits into candidates...")
    scored.sort(key=lambda h: h["time"])
    candidates = []
    cluster = []
    for h in scored:
        if cluster and h["time"] - cluster[-1]["time"] > MERGE_GAP_SECONDS:
            candidates.append(cluster)
            cluster = []
        cluster.append(h)
    if cluster:
        candidates.append(cluster)

    print(f"{len(candidates)} merged candidates from {len(scored)} scored hits")

    # Clip-audio window: pre/post-roll around the anchor hit's OWN timestamp, on its OWN
    # channel only. A merged cluster spans multiple channels/times (real for scoring —
    # "genuine crisis" shows up as many loops going active at once) but a single audio
    # file can only be one channel's tape. Extracting audio for the full cluster span on
    # just the top-scoring hit's channel silently omits whatever phrase fired on a
    # *different* channel in that window — confirmed empirically in the first spot-check
    # pass (a "we've lost" hit attributed to a cluster came from a different channel than
    # the one actually extracted). So: audio_source_* always points at the anchor hit's
    # own channel/time; the wider multi-channel "context" field stays for human scene-
    # setting (hook writing, spotting a better line said on a neighboring loop) but is not
    # assumed to be on-tape in the extracted clip.
    CLIP_PRE_ROLL = 5
    CLIP_POST_ROLL = 25

    queue = []
    for cluster in candidates:
        best = max(cluster, key=lambda h: h["score"])
        total_score = round(sum(h["score"] for h in cluster) / len(cluster) + len(cluster) * 2, 2)

        ctx_min = min(h["time"] for h in cluster) - 10
        ctx_max = max(h["time"] for h in cluster) + 15
        if ctx_max - ctx_min > 90:
            ctx_max = ctx_min + 90

        lo = bisect.bisect_left(times, ctx_min)
        hi = bisect.bisect_right(times, ctx_max)
        context_lines = [
            {"get": fmt_get(times[j]), "channel": chans[j],
             "channel_name": CHANNEL_NAMES.get(chans[j], "?"), "text": texts[j]}
            for j in range(lo, hi)
        ]

        primary_channel = best["channel"]
        channel_name = CHANNEL_NAMES.get(primary_channel, f"CH{primary_channel}")
        slug_bits = re.sub(r"[^a-z0-9]+", "-", channel_name.lower()).strip("-")
        slug = f"a13-{slug_bits}-{abs(best['time'])}"

        anchor_t = best["time"]
        clip_start = anchor_t - CLIP_PRE_ROLL
        clip_end = anchor_t + CLIP_POST_ROLL

        audio_url, tape_offset = (
            audio_url_for(anchor_t, primary_channel, hr1, hr2) if primary_channel else (None, None)
        )
        clip_offset = tape_offset - CLIP_PRE_ROLL if tape_offset is not None else None

        queue.append({
            "slug": slug,
            "source": "nasa",
            "mission": "Apollo 13",
            "channel": channel_name,
            "anchor_phrase": best["phrase"],
            "get_start": fmt_get(clip_start),
            "get_end": fmt_get(clip_end),
            "score": total_score,
            "matched_phrases": sorted(set(f"{h['category']}:{h['phrase']}" for h in cluster)),
            "context": context_lines,
            "hook": "",
            "audio_local": "",
            "audio_source_url": audio_url,
            "audio_source_offset_s": clip_offset,
            "audio_source_duration_s": (CLIP_PRE_ROLL + CLIP_POST_ROLL) if clip_offset is not None else None,
            "footage_local": "assets/video/a13-mocr.mp4",
            "oral_history_ref": "",
            "verified": False,
            "status": "candidate",
        })

    queue.sort(key=lambda c: c["score"], reverse=True)
    top = queue[:TOP_N]

    # Merge rather than overwrite: queue.json can hold candidates from other
    # sources (e.g. DVIDS), and human curation progress (status/verified/hook/
    # audio_local) on previously-scored NASA candidates must survive a rescore.
    existing = json.loads(QUEUE_OUT.read_text()) if QUEUE_OUT.exists() else []
    other_source = [e for e in existing if e.get("source", "nasa") != "nasa"]
    prior_nasa_by_slug = {e["slug"]: e for e in existing if e.get("source", "nasa") == "nasa"}

    PRESERVE_FIELDS = ("status", "verified", "hook", "audio_local",
                       "quality_score", "quality_confidence", "quality_notes", "quality_transcript")
    preserved_count = 0
    for cand in top:
        prior = prior_nasa_by_slug.get(cand["slug"])
        if prior:
            preserved_count += 1
            for field in PRESERVE_FIELDS:
                if field in prior:
                    cand[field] = prior[field]

    final = other_source + top
    QUEUE_OUT.write_text(json.dumps(final, indent=2))
    print(
        f"Wrote {len(top)} NASA candidates ({preserved_count} with progress preserved from "
        f"a prior run) + {len(other_source)} other-source entries to {QUEUE_OUT}"
    )


if __name__ == "__main__":
    main()
