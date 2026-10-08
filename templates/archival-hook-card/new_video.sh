#!/bin/bash
# Scaffold a new video project from the archival-hook-card template.
# Usage: ./new_video.sh <slug>
# Creates <repo>/projects/<slug>-short/remotion, symlinking node_modules back
# to the template (663MB — reinstalling per video would blow the time budget)
# instead of copying or reinstalling it.
set -e
SLUG="$1"
if [ -z "$SLUG" ]; then
  echo "Usage: ./new_video.sh <slug>"
  exit 1
fi

TEMPLATE_DIR="$(cd "$(dirname "$0")" && pwd)"
SHORTS_ROOT="$(dirname "$(dirname "$TEMPLATE_DIR")")"
PROJECT_DIR="$SHORTS_ROOT/projects/${SLUG}-short"

if [ -e "$PROJECT_DIR" ]; then
  echo "Already exists: $PROJECT_DIR"
  exit 1
fi

if [ ! -d "$TEMPLATE_DIR/remotion/node_modules" ]; then
  echo "Run npm install in $TEMPLATE_DIR/remotion first."
  exit 1
fi

mkdir -p "$PROJECT_DIR/remotion"
rsync -a --exclude node_modules "$TEMPLATE_DIR/remotion/" "$PROJECT_DIR/remotion/"
ln -s "$TEMPLATE_DIR/remotion/node_modules" "$PROJECT_DIR/remotion/node_modules"

mkdir -p "$PROJECT_DIR/remotion/public/audio" "$PROJECT_DIR/remotion/public/footage"
mkdir -p "$PROJECT_DIR/audio_work" "$PROJECT_DIR/out"

echo "Created $PROJECT_DIR"
echo ""
echo "Next steps (run from $PROJECT_DIR unless noted):"
echo "  1. Drop the trimmed archival audio into remotion/public/audio/mission_audio.wav"
echo "  2. Drop footage clips into remotion/public/footage/"
echo "  3. Run whisper-cli + parse_whisper_timings.py, write output to remotion/src/data/wordTimings.json"
echo "  4. Edit remotion/public/video.json: footage list, hook segments"
echo "  5. cd remotion && npx remotion render ArchivalHookCard ../out/raw.mp4 && cd .."
echo "  6. $SHORTS_ROOT/audio/audio_archival.sh . FINAL_NAME.mp4   (final file lands in out/FINAL_NAME.mp4)"
