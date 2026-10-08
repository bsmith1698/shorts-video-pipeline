#!/bin/bash
set -e
SRC="${CLIPS_DIR:?Set CLIPS_DIR to your clip library (with VO/ and SFX/ subfolders)}"
R="${WORK_DIR:-$PWD/render}"
FB="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FI="/System/Library/Fonts/Supplemental/Impact.ttf"
FR="/System/Library/Fonts/Supplemental/Arial.ttf"
FF="${FFMPEG:-ffmpeg}"
FP="${FFPROBE:-ffprobe}"
CROP="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"

mkdir -p "$R" && cd "$R"

Q="fontfile='$FB':fontcolor=white:fontsize=58:line_spacing=12:box=1:boxcolor=black@0.45:boxborderw=24:borderw=3:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2"
REV="fontfile='$FI':fontcolor=0xFFD700:fontsize=84:line_spacing=14:box=1:boxcolor=black@0.45:boxborderw=24:borderw=3:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2"
PIP="fontfile='$FR':fontcolor=white:fontsize=50:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.82"

build_seg () {
  NAME=$1; SRCFILE=$2; SS=$3; LEN=$4; QFILE=$5; QEND=$6; RFILE=$7; PIPBEFORE=$8; PIPAFTER=$9

  $FF -y -ss "$SS" -i "$SRCFILE" -t "$LEN" -vf "$CROP" -an "seg/${NAME}_base.mp4"

  $FF -y -i "seg/${NAME}_base.mp4" -vf "
drawtext=${Q}:textfile='txt/${QFILE}':enable='between(t,0.40,${QEND})',
drawtext=${REV}:textfile='txt/${RFILE}':enable='between(t,${QEND},${LEN})',
drawtext=${PIP}:textfile='txt/${PIPBEFORE}':enable='between(t,0,${QEND})',
drawtext=${PIP}:textfile='txt/${PIPAFTER}':enable='between(t,${QEND},${LEN})'
" -an "seg/${NAME}.mp4"

  DUR=$($FP -v error -show_entries format=duration -of csv=p=0 "seg/${NAME}.mp4")
  echo "$NAME done, duration=$DUR"
}

build_seg B "$SRC/sun_1.mp4"   0 7.85 q1.txt 5.93 r1.txt pip0.txt pip1.txt
build_seg C "$SRC/shark_1.mp4" 0 7.77 q2.txt 6.27 r2.txt pip1.txt pip2.txt
build_seg D "$SRC/space_1.mp4" 0 8.74 q3.txt 6.27 r3.txt pip2.txt pip3.txt
build_seg E "$SRC/globe_1.mp4" 0 7.23 q4.txt 5.62 r4.txt pip3.txt pip4.txt
build_seg F "$SRC/honey_1.mp4" 0 10.70 q5.txt 7.24 r5.txt pip4.txt pip5.txt

# outro: continue honey_1 from where segment F left off
$FF -y -ss 10.70 -i "$SRC/honey_1.mp4" -t 4.16 -vf "$CROP" -an seg/G_base.mp4
$FF -y -i seg/G_base.mp4 -vf "
drawtext=${Q}:textfile='txt/outro1.txt':fontsize=64:y=(h-text_h)/2-140:enable='between(t,0.30,4.16)',
drawtext=${Q}:textfile='txt/outro2.txt':fontsize=64:y=(h-text_h)/2+140:enable='between(t,0.30,4.16)',
drawtext=${PIP}:textfile='txt/pip5.txt':enable='between(t,0,4.16)'
" -an seg/G.mp4
DUR=$($FP -v error -show_entries format=duration -of csv=p=0 seg/G.mp4)
echo "G done, duration=$DUR"

echo "ALL SEGMENTS DONE"
