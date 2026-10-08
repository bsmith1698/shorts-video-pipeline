#!/usr/bin/env python3
"""Cheap first-pass triage over DVIDS `type=video` results by title/short_description
text alone — no per-item API calls, no audio/video downloads. A manual
"skim the titles first" workflow formalized into a repeatable script.

This is a *shortlist* step, not a candidate-ready step: output entries still need the
full pipeline (full description fetch, real listen-through/transcribe of the video's
own audio track, footage legibility check) before anything counts as verified — see
`sourcing_dvids.py` and `verify_footage.py` for that half. Severe-but-no-deaths only,
per the 2026-08-16 scope decision: reuses FATALITY_PATTERN/TRAINING_PATTERN/
PRODUCED_BROADCAST_PATTERN from sourcing_dvids.py to drop the same categories that
pass already excludes, applied here at the cheap title/short_description stage instead
of after a full-description fetch.

Usage: python3 scripts/triage_titles.py --unit "U.S. Coast Guard" --queries fire,explosion,capsized,...
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcing_dvids import (  # noqa: E402
    call, BASE, FATALITY_PATTERN, TRAINING_PATTERN, TITLE_EXERCISE_PATTERN,
    PRODUCED_BROADCAST_PATTERN,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

SEVERITY_WORDS = [
    "fire", "explosion", "capsize", "capsized", "capsizing", "sinking", "sank",
    "flooding", "flooded", "abandon ship", "collision", "collides", "collided",
    "grounding", "grounded", "adrift", "overboard", "life raft", "mayday",
    "distress", "engine room fire", "hull breach", "taking on water",
    "lost power", "disabled vessel", "storm", "hurricane", "hoax", "threat",
    "swept out to sea", "clinging", "stranded", "trapped", "multiple",
]
MUNDANE_WORDS = [
    "training", "exercise", "interview", "b-roll", "broll", "stand watch",
    "stands watch", "returns to port", "conducts tour", "anniversary",
    "change of command", "graduation", "ceremony", "portrait", "media day",
    "sitrep", "symposium", "town hall", "press conference",
]

SEVERITY_PATTERN = re.compile("|".join(re.escape(w) for w in SEVERITY_WORDS), re.IGNORECASE)
MUNDANE_PATTERN = re.compile("|".join(re.escape(w) for w in MUNDANE_WORDS), re.IGNORECASE)


def score_item(item):
    text = f"{item.get('title','')} {item.get('short_description','')}"
    hits = SEVERITY_PATTERN.findall(text)
    mundane_hits = MUNDANE_PATTERN.findall(text)
    return len(set(h.lower() for h in hits)) - len(set(m.lower() for m in mundane_hits))


def is_excluded(item):
    title = item.get("title") or ""
    text = f"{title} {item.get('short_description','')}"
    if FATALITY_PATTERN.search(text):
        return "fatality_or_body_recovery_indicated"
    if TRAINING_PATTERN.search(text) or TITLE_EXERCISE_PATTERN.search(title):
        return "training_exercise_or_simulated_patient"
    if PRODUCED_BROADCAST_PATTERN.search(title):
        return "produced_news_broadcast_not_raw_audio"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", help='DVIDS unit_name filter (exact sub-unit, e.g. "U.S. Coast Guard Oceania")')
    ap.add_argument("--branch", help='DVIDS branch filter (top-level, e.g. "Coast Guard") — use this for broad scans, --unit is for one specific sub-unit')
    ap.add_argument("--type", default="video", choices=["video", "audio"])
    ap.add_argument("--queries", required=True, help="comma-separated search terms")
    ap.add_argument("--max-per-query", type=int, default=50)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--out", default=None, help="output JSON path (default: _archive/title_triage_<unit-slug>.json)")
    args = ap.parse_args()

    if not args.unit and not args.branch:
        ap.error("pass --unit or --branch")

    filter_params = {}
    if args.unit:
        filter_params["unit_name"] = args.unit
    if args.branch:
        filter_params["branch"] = args.branch

    queries = [q.strip() for q in args.queries.split(",") if q.strip()]
    pool = {}
    for q in queries:
        time.sleep(0.15)
        data = call(BASE, {**filter_params, "q": q, "type": args.type,
                            "max_results": args.max_per_query})
        results = data.get("results", [])
        for item in results:
            pool[item["id"]] = item
        print(f"  q={q!r}: {len(results)} results (pool now {len(pool)})")

    label = args.unit or args.branch
    print(f"\n{len(pool)} unique {args.type} items pulled across {len(queries)} queries ({label!r}).")

    scored = []
    excluded_count = 0
    for item in pool.values():
        reason = is_excluded(item)
        if reason:
            excluded_count += 1
            continue
        scored.append((score_item(item), item))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:args.top]

    print(f"{excluded_count} excluded (fatality/training/produced-broadcast patterns).")
    print(f"Top {len(top)} by severity-title score:\n")
    shortlist = []
    for score, item in top:
        print(f"  [{score:+d}] {item['id']} | {item.get('date','')[:10]} | {item['title']}")
        if item.get("short_description"):
            print(f"        {item['short_description'][:150]}")
        shortlist.append({
            "id": item["id"],
            "type": item["type"],
            "title": item.get("title"),
            "short_description": item.get("short_description"),
            "date": item.get("date"),
            "unit_name": item.get("unit_name"),
            "duration": item.get("duration"),
            "url": item.get("url"),
            "title_score": score,
        })

    out_path = Path(args.out) if args.out else REPO_ROOT / "_archive" / f"title_triage_{label.replace(' ', '_')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(shortlist, indent=2))
    print(f"\nWrote shortlist ({len(shortlist)} entries) to {out_path}")


if __name__ == "__main__":
    main()
