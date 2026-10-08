#!/bin/bash
# Audio post-process for the archival-audio format (Space Archival Audio Shorts).
# Usage: ./audio_archival.sh <project_dir> <output_final_name> [music_bed_path]
#
# Unlike audio_post.sh's VOCHAIN (highpass/EQ/de-ess/compression tuned to smooth
# ElevenLabs TTS), the archival tape gets NO EQ or compression — the wow/flutter,
# hiss, and radio clipping are the reason this format works ("that happened" is
# the whole sell, the format's core rule). The only touch is a sub-40Hz
# highpass to kill inaudible rumble/DC offset that would otherwise skew the
# loudnorm measurement — that's below anything perceptible as "tape character."
#
# gemini8-short (this format's proof-of-concept, channel-best at 81.8%
# stayed-to-watch) shipped its raw archival file completely unprocessed, no
# music bed, no explicit loudness pass — measured after the fact at -17.6 LUFS
# integrated, under the channel's -14 LUFS/-1.5dBTP spec (docs/production-standards.md).
# This script formalizes that same "don't smooth it" instinct into a repeatable
# pass that also actually hits spec, and adds an optional ducked music bed for
# videos that want one (gemini8 didn't need it — dead air on real tape can be
# tenser than a music cue).
set -e
PROJ="$1"
OUT_NAME="$2"
MUSIC_BED="$3"  # optional

if [ -z "$PROJ" ] || [ -z "$OUT_NAME" ]; then
  echo "Usage: ./audio_archival.sh <project_dir> <output_final_name> [music_bed_path]"
  exit 1
fi

cd "$PROJ"

FF=ffmpeg
FP=ffprobe

ARCHIVAL_CHAIN="highpass=f=40"

DUR=$($FP -v error -show_entries format=duration -of csv=p=0 out/raw.mp4)
echo "Video duration: $DUR"

if [ -n "$MUSIC_BED" ]; then
  FILTER="
[0:a]${ARCHIVAL_CHAIN},aformat=sample_rates=44100:channel_layouts=stereo[tape];
[1:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:${DUR},volume=0.12[music];
[music][tape]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=300:makeup=1[ducked];
[tape][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.65:level=false:attack=1:release=50,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[mixed]
"
  INPUTS=(-i out/raw.mp4 -i "$MUSIC_BED")
else
  FILTER="
[0:a]${ARCHIVAL_CHAIN},aformat=sample_rates=44100:channel_layouts=stereo,alimiter=limit=0.65:level=false:attack=1:release=50,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[mixed]
"
  INPUTS=(-i out/raw.mp4)
fi

# Pass 1: measure
$FF -y "${INPUTS[@]}" -filter_complex "$FILTER" -map "[mixed]" -t "$DUR" -f null - 2> /tmp/loudnorm_measure.txt

MEASURE=$(python3 -c "
import re
text = open('/tmp/loudnorm_measure.txt').read()
m = re.search(r'\{\s*\"input_i\".*?\}', text, re.DOTALL)
print(m.group(0) if m else '')
")
echo "Measured: $MEASURE"

INPUT_I=$(echo "$MEASURE" | python3 -c "import json,sys; print(json.load(sys.stdin)['input_i'])")
INPUT_TP=$(echo "$MEASURE" | python3 -c "import json,sys; print(json.load(sys.stdin)['input_tp'])")
INPUT_LRA=$(echo "$MEASURE" | python3 -c "import json,sys; print(json.load(sys.stdin)['input_lra'])")
INPUT_THRESH=$(echo "$MEASURE" | python3 -c "import json,sys; print(json.load(sys.stdin)['input_thresh'])")

echo "input_i=$INPUT_I input_tp=$INPUT_TP input_lra=$INPUT_LRA input_thresh=$INPUT_THRESH"

FILTER2="${FILTER//print_format=json/measured_I=${INPUT_I}:measured_TP=${INPUT_TP}:measured_LRA=${INPUT_LRA}:measured_thresh=${INPUT_THRESH}:linear=true:print_format=summary}"

# Pass 2: apply measured values precisely, remux with video (no -shortest)
$FF -y "${INPUTS[@]}" -filter_complex "$FILTER2" -map 0:v -map "[mixed]" -c:v copy -c:a aac -b:a 192k -t "$DUR" "out/${OUT_NAME}"

echo "Final file: out/${OUT_NAME}"
$FF -i "out/${OUT_NAME}" -filter:a ebur128 -f null - 2>&1 | tail -20
