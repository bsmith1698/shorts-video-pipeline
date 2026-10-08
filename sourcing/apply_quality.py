#!/usr/bin/env python3
"""
Merges quality-pass results into queue.json ADDITIVELY: only ever adds/updates
the four new fields (quality_score, quality_confidence, quality_notes,
quality_transcript) on entries matched by slug. Never touches any other field
(status, verified, hook, etc. are left exactly as they were) and never blind-
overwrites the file -- reads the current queue.json, patches matched entries,
writes it back. Matches the merge-by-slug pattern already used by
score_transcript.py / sourcing_dvids.py.

Input: a JSON file mapping slug -> {quality_score, quality_confidence,
quality_notes, quality_transcript}. Entries in queue.json whose slug isn't in
the input file are left completely untouched.

Usage:
  python3 apply_quality.py results.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE_PATH = ROOT / "queue.json"

FIELDS = ("quality_score", "quality_confidence", "quality_notes", "quality_transcript")


def main():
    if len(sys.argv) != 2:
        print("usage: apply_quality.py results.json", file=sys.stderr)
        sys.exit(1)

    results = json.loads(Path(sys.argv[1]).read_text())
    queue = json.loads(QUEUE_PATH.read_text())

    updated = 0
    missing = set(results.keys())
    for cand in queue:
        r = results.get(cand["slug"])
        if r is None:
            continue
        missing.discard(cand["slug"])
        for field in FIELDS:
            if field in r:
                cand[field] = r[field]
        updated += 1

    QUEUE_PATH.write_text(json.dumps(queue, indent=2))
    print(f"Updated {updated} entries in {QUEUE_PATH}")
    if missing:
        print(f"WARNING: {len(missing)} slugs in results file not found in queue.json: {missing}", file=sys.stderr)


if __name__ == "__main__":
    main()
