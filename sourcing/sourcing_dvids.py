#!/usr/bin/env python3
"""Batch-source Coast Guard SAR candidates from DVIDS into queue.json.

Sibling to score_transcript.py (NASA/Apollo transcript grep) — same target
file, same "source" discriminator convention, same merge-not-overwrite
safety, but a completely different fetch mechanism (API search, not a local
transcript), so it lives as its own script rather than a branch inside
score_transcript.py's Apollo-specific internals.

Uses the exact-match `unit_name` search filter (not free-text `q`),
+/-7 day window (a "viable but lossy" band), loose same-unit pairing definition per the go-ahead decision.

Exclusion filtering happens in code, not at assembly time: matches get
status "excluded" with a logged reason, never deleted.

Auto-score fields (duration_ok, outcome_stated, likely_civilian_voice) are
metadata heuristics for triage, not verified facts — every guardrail in
docs/archival-funnel.md still applies: nothing ships without a human listen and
verified: true.
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_OUT = REPO_ROOT / "queue.json"
BASE = "https://api.dvidshub.net/search"
ASSET = "https://api.dvidshub.net/asset"

PAIR_WINDOW_DAYS = 7
TARGET_COUNT = 30
# Hard filter, not just a sort-priority signal (decided 2026-08-16): a candidate whose
# real DVIDS-released audio runs under this is excluded outright, not just
# deprioritized. This is the full real tape length (DVIDS' own release
# duration), not a trim this pipeline is choosing to apply, so there's no
# "extend it" fix available the way there was for the NASA-side duration
# mistake in space_archival_audio_format.
MIN_DURATION_S = 25

SEED_QUERIES = [
    "mayday",
    "distress call",
    "rescue 21 recording",
    "hoax distress call",
    "VHF channel 16",
    "command center audio",
]

FATALITY_PATTERN = re.compile(
    r"\b(died|deceased|fatality|fatalities|body (was |were )?recovered|"
    r"recovered a body|did not survive|pronounced dead|drowned|"
    r"search (was |has been )?suspended|remains (of|were) (found|recovered))\b",
    re.IGNORECASE,
)
TRAINING_PATTERN = re.compile(
    r"\b(training exercise|training scenario|simulated patient|simulation exercise|"
    r"mock (rescue|distress|casualty)|joint exercise|annual exercise|mass rescue exercise|"
    r"this is an exercise)\b",
    re.IGNORECASE,
)
# Any exercise/drill word in the TITLE specifically is a strong signal on its
# own (a DoD PAO office labeling its own release a drill), even if the
# broader TRAINING_PATTERN phrase list above doesn't happen to match — added
# after dvids-audio-42319 ("Mass Rescue Exercise - Initial Mayday") slipped
# through the quality-verification pass with exclusion_reason: null.
TITLE_EXERCISE_PATTERN = re.compile(r"\bexercise\b", re.IGNORECASE)
# Produced news-bulletin/show content (a newsreader narrating/summarizing a
# story) is a different failure mode than training audio: it's real, on-topic
# words about a real incident, but it's not the raw operational radio traffic
# this pipeline exists to source. Found via the quality-verification pass:
# dvids-audio-45896 ("Soldiers Radio News"), dvids-audio-68851 ("Pacific
# Pulse"), dvids-audio-57858 ("Muscatatuck Minute") were all this pattern,
# all with exclusion_reason: null. These are recurring DoD/service PAO show
# names/formats, checked against the title only (a real distress-call title
# is very unlikely to also match one of these).
PRODUCED_BROADCAST_PATTERN = re.compile(
    r"(\bradio news\b|\bnews in \d|\bsitrep\b|\b\w+ minute\b|\b\w+ pulse\b|"
    r"\bnews brief\b|\bnewsbrief\b)",
    re.IGNORECASE,
)
OUTCOME_PATTERN = re.compile(
    r"\b(rescued|transferred to|no reported injuries|safely|towed|returned to port|"
    r"medevac|hoisted|recovered (the|all)|brought (aboard|ashore)|assisted)\b",
    re.IGNORECASE,
)
# Best-effort proxy only — distinguishes "a caller/boater/vessel is the voice"
# from "a spokesperson narrates a PSA about a call". Not audio analysis.
CIVILIAN_VOICE_HINT = re.compile(
    r"\b(caller|boater|captain|kayaker|fisherman|mayday call from|distress call from|"
    r"sailor|crew(member)?s? (calls|called|radioed))\b",
    re.IGNORECASE,
)
PSA_ONLY_HINT = re.compile(
    r"\b(seeks? (the )?public|seeking public|identify the (caller|individual|voice)|"
    r"requests? (the )?public|community support to identify)\b",
    re.IGNORECASE,
)


def load_api_key():
    env_path = REPO_ROOT / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("DVIDS_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DVIDS_API_KEY not found in .env")


API_KEY = load_api_key()


def call(url_base, params):
    params = dict(params)
    params["api_key"] = API_KEY
    url = f"{url_base}?{urlencode(params)}"
    with urlopen(url) as resp:
        return json.loads(resp.read())


def fmt_dvids_date(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")


def parse_dvids_date(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def find_paired_video(unit, event_dt):
    from_dt = event_dt - timedelta(days=PAIR_WINDOW_DAYS)
    to_dt = event_dt + timedelta(days=PAIR_WINDOW_DAYS)
    time.sleep(0.15)
    data = call(
        BASE,
        {
            "unit_name": unit,
            "type": "video",
            "from_date": fmt_dvids_date(from_dt),
            "to_date": fmt_dvids_date(to_dt),
            "max_results": 5,
        },
    )
    return data.get("results", [])


def fetch_full_asset(asset_id):
    """short_description from search results is truncated (99% of pool items
    end in '...', almost always cutting off before the outcome/fatality
    sentence) — the exclusion filter and outcome heuristic are only safe to
    run against the full asset description. Also returns the real CDN file
    URL in the same call, so callers don't need a second lookup for it."""
    time.sleep(0.15)
    data = call(ASSET, {"id": asset_id}).get("results", {})
    return data.get("description") or "", data.get("file")


def auto_score(item, full_description):
    duration = item.get("duration") or 0
    desc = full_description
    title = item.get("title") or ""
    text = f"{title} {desc}"

    duration_ok = 15 <= duration <= 90
    outcome_stated = bool(OUTCOME_PATTERN.search(desc))

    if PSA_ONLY_HINT.search(desc) and not CIVILIAN_VOICE_HINT.search(desc):
        likely_civilian_voice = False
    elif CIVILIAN_VOICE_HINT.search(desc):
        likely_civilian_voice = True
    else:
        likely_civilian_voice = None  # unknown — needs a human listen

    exclusion_reason = None
    if FATALITY_PATTERN.search(text):
        exclusion_reason = "fatality_or_body_recovery_indicated"
    elif TRAINING_PATTERN.search(text) or TITLE_EXERCISE_PATTERN.search(title):
        exclusion_reason = "training_exercise_or_simulated_patient"
    elif PRODUCED_BROADCAST_PATTERN.search(title):
        exclusion_reason = "produced_news_broadcast_not_raw_audio"
    elif duration < MIN_DURATION_S:
        exclusion_reason = "duration_under_25s_threshold"

    return {
        "duration_ok": duration_ok,
        "outcome_stated": outcome_stated,
        "likely_civilian_voice": likely_civilian_voice,
    }, exclusion_reason


def main():
    pool = {}
    for q in SEED_QUERIES:
        data = call(BASE, {"q": q, "type": "audio", "max_results": 50})
        for item in data.get("results", []):
            pool[item["id"]] = item
    print(f"Pulled {len(pool)} unique audio items across {len(SEED_QUERIES)} seed queries.")

    print("Fetching full descriptions + file URLs for the pool (this is the part that takes a while)...")
    full_by_id = {}
    for asset_id in pool:
        full_by_id[asset_id] = fetch_full_asset(asset_id)

    scored = []
    for item in pool.values():
        full_desc, file_url = full_by_id[item["id"]]
        auto, exclusion_reason = auto_score(item, full_desc)
        scored.append((item, auto, exclusion_reason, full_desc, file_url))

    # Prioritize: not-excluded, on-spec duration, and let footage-pairing status
    # break remaining ties, before falling back to raw pool order (== relevance
    # order as returned by the API for its highest-ranked seed match).
    def sort_key(row):
        item, auto, exclusion_reason, full_desc, file_url = row
        return (
            exclusion_reason is not None,  # excluded items sort last
            not auto["duration_ok"],
        )

    scored.sort(key=sort_key)
    selected = scored[:TARGET_COUNT]
    print(f"Selected {len(selected)} for this batch (target {TARGET_COUNT}).")

    new_entries = []
    pair_count = 0
    excluded_count = 0
    civilian_true = civilian_false = civilian_unknown = 0

    for item, auto, exclusion_reason, full_desc, file_url in selected:
        unit = item.get("unit_name")
        date_raw = item.get("date") or item.get("publishdate")
        event_dt = parse_dvids_date(date_raw)

        video_results = find_paired_video(unit, event_dt) if unit else []
        auto["footage_paired"] = bool(video_results)
        if video_results:
            pair_count += 1

        if auto["likely_civilian_voice"] is True:
            civilian_true += 1
        elif auto["likely_civilian_voice"] is False:
            civilian_false += 1
        else:
            civilian_unknown += 1

        status = "excluded" if exclusion_reason else "candidate"
        if exclusion_reason:
            excluded_count += 1

        # Only keep the real CDN file URL for usable candidates.
        audio_file_url = file_url if status != "excluded" else None

        slug = "dvids-" + item["id"].replace(":", "-")

        new_entries.append({
            "slug": slug,
            "source": "dvids",
            "mission": None,
            "channel": None,
            "anchor_phrase": None,  # NASA-only concept (scored transcript phrase); N/A here
            "get_start": None,      # NASA-only concept (mission clock); N/A here
            "get_end": None,
            "score": None,
            "matched_phrases": [],
            "context": full_desc,
            "hook": "",
            "audio_local": "",
            "audio_source_url": audio_file_url,
            "audio_source_offset_s": 0,
            "audio_source_duration_s": item.get("duration"),
            "footage_local": "",
            "oral_history_ref": "",
            "verified": False,
            "status": status,
            "dvids": {
                "audio_asset_id": item["id"],
                "video_asset_ids": [v["id"] for v in video_results],
                "video_titles": [v.get("title") for v in video_results],
                "unit": unit,
                "event_date": date_raw,
                "credit": item.get("credit"),
                "title": item.get("title"),
                "dvids_url": item.get("url"),
                "auto_score": auto,
                "exclusion_reason": exclusion_reason,
            },
        })

    # Merge: preserve every non-dvids entry untouched, and preserve human
    # progress on any dvids slug we've seen before (re-running this script
    # shouldn't reset a candidate a human already listened to / verified).
    existing = json.loads(QUEUE_OUT.read_text()) if QUEUE_OUT.exists() else []
    other_source = [e for e in existing if e.get("source") != "dvids"]
    prior_dvids_by_slug = {e["slug"]: e for e in existing if e.get("source") == "dvids"}

    PRESERVE_FIELDS = ("status", "verified", "hook", "audio_local", "footage_local",
                       "quality_score", "quality_confidence", "quality_notes", "quality_transcript")
    preserved_count = 0
    for cand in new_entries:
        prior = prior_dvids_by_slug.get(cand["slug"])
        if prior:
            preserved_count += 1
            for field in PRESERVE_FIELDS:
                if field in prior:
                    cand[field] = prior[field]

    # Any prior dvids slugs not present in this run's selection stay as-is
    # (e.g. a candidate a human already promoted to "ready" that fell out of
    # this batch's top 30) rather than being dropped.
    new_slugs = {e["slug"] for e in new_entries}
    carried_over = [e for e in prior_dvids_by_slug.values() if e["slug"] not in new_slugs]

    final = other_source + new_entries + carried_over
    QUEUE_OUT.write_text(json.dumps(final, indent=2))

    print(f"\nWrote {len(new_entries)} dvids candidates ({preserved_count} with progress "
          f"preserved) + {len(carried_over)} carried over + {len(other_source)} "
          f"other-source entries to {QUEUE_OUT}")
    print(f"  candidate: {len(new_entries) - excluded_count}, excluded: {excluded_count}")
    print(f"  footage paired: {pair_count}/{len(new_entries)}")
    print(f"  likely_civilian_voice — true: {civilian_true}, false: {civilian_false}, "
          f"unknown (needs listen): {civilian_unknown}")


if __name__ == "__main__":
    main()
