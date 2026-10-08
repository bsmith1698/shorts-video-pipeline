#!/bin/bash
set -e
SRC="${CLIPS_DIR:?Set CLIPS_DIR to your clip library (with VO/ and SFX/ subfolders)}"
R="${WORK_DIR:-$PWD/render}"
FB="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
CROP="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
FF="${FFMPEG:-ffmpeg}"
FP="${FFPROBE:-ffprobe}"

mkdir -p "$R" && cd "$R"

# 5 flash clips, 1.31s each (last one 1.30s to hit exactly 6.55 total)
$FF -y -i "$SRC/space_2.mp4"  -t 1.31 -vf "$CROP" -an seg/i1.mp4
$FF -y -i "$SRC/shark_3.mp4"  -t 1.31 -vf "$CROP" -an seg/i2.mp4
$FF -y -i "$SRC/sun_2.mp4"    -t 1.31 -vf "$CROP" -an seg/i3.mp4
$FF -y -i "$SRC/globe_2.mp4"  -t 1.31 -vf "$CROP" -an seg/i4.mp4
$FF -y -i "$SRC/honey_2.mp4"  -t 1.31 -vf "$CROP" -an seg/i5.mp4

$FF -y -i seg/i1.mp4 -i seg/i2.mp4 -i seg/i3.mp4 -i seg/i4.mp4 -i seg/i5.mp4 \
  -filter_complex "[0:v][1:v][2:v][3:v][4:v]concat=n=5:v=1:a=0[outv]" \
  -map "[outv]" -an seg/intro_base.mp4

$FF -y -i seg/intro_base.mp4 -vf "
drawtext=fontfile='$FB':textfile='txt/intro1.txt':fontcolor=white:fontsize=76:line_spacing=14:borderw=6:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0.10,2.50)',
drawtext=fontfile='$FB':textfile='txt/intro2.txt':fontcolor=white:fontsize=76:line_spacing=14:borderw=6:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,2.50,4.50)',
drawtext=fontfile='$FB':textfile='txt/intro3.txt':fontcolor=white:fontsize=76:line_spacing=14:borderw=6:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,4.50,6.55)'
" -an seg/A_intro.mp4

echo "intro segment done"
$FP -v error -show_entries format=duration -of csv=p=0 seg/A_intro.mp4
