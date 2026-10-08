#!/bin/bash
# Usage: ./audio_post.sh <project_dir> <output_final_name>
set -e
PROJ="$1"
OUT_NAME="$2"
cd "$PROJ"

FF=ffmpeg
FP=ffprobe

VOCHAIN="highpass=f=90,equalizer=f=500:t=q:w=1:g=-3,equalizer=f=3500:t=q:w=1.5:g=3,equalizer=f=7000:t=q:w=2:g=-2,acompressor=threshold=0.14:ratio=3:attack=3:release=15:makeup=1.25"

DUR=$($FP -v error -show_entries format=duration -of csv=p=0 out/raw.mp4)
echo "Video duration: $DUR"

# Pass 1: build the mix (VO+SFX cleaned + ducked music bed) and measure loudness
$FF -y -i out/raw.mp4 -i public/sfx/music_bed.mp3 -filter_complex "
[0:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo[voclean];
[1:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:${DUR},volume=0.22[music];
[music][voclean]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=300:makeup=1[ducked];
[voclean][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.65:level=false:attack=1:release=50,loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[mixed]
" -map "[mixed]" -t "$DUR" -f null - 2> /tmp/loudnorm_measure.txt

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

# Pass 2: apply the measured loudnorm precisely, remux with video (no -shortest)
$FF -y -i out/raw.mp4 -i public/sfx/music_bed.mp3 -filter_complex "
[0:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo[voclean];
[1:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:${DUR},volume=0.22[music];
[music][voclean]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=300:makeup=1[ducked];
[voclean][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.65:level=false:attack=1:release=50,loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=${INPUT_I}:measured_TP=${INPUT_TP}:measured_LRA=${INPUT_LRA}:measured_thresh=${INPUT_THRESH}:linear=true:print_format=summary[mixed]
" -map 0:v -map "[mixed]" -c:v copy -c:a aac -b:a 192k -t "$DUR" "out/${OUT_NAME}"

echo "Final file: out/${OUT_NAME}"
$FF -i "out/${OUT_NAME}" -filter:a ebur128 -f null - 2>&1 | tail -20
