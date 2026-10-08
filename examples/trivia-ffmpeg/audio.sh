#!/bin/bash
set -e
SRC="${CLIPS_DIR:?Set CLIPS_DIR to your clip library (with VO/ and SFX/ subfolders)}"
VO="$SRC/VO"
SFX="$SRC/SFX"
R="${WORK_DIR:-$PWD/render}"
FF="${FFMPEG:-ffmpeg}"
mkdir -p "$R" && cd "$R"

TOTAL=52.967

# ElevenLabs VO cleanup: HPF clears rumble, EQ cuts mud/de-esses, 3:1 comp evens
# out TTS dynamics. Applied identically to every VO track below.
VOCHAIN="highpass=f=90,equalizer=f=500:t=q:w=1:g=-3,equalizer=f=3500:t=q:w=1.5:g=3,equalizer=f=7000:t=q:w=2:g=-2,acompressor=threshold=0.05:ratio=3:attack=3:release=15:makeup=1.4"

# inputs: file, delay_ms, volume
$FF -y \
  -i "$SFX/intro_whoosh.wav" \
  -i "$VO/02_q1_sun.mp3" \
  -i "$SFX/answer_reveal.wav" \
  -i "$VO/03_a1_sun.mp3" \
  -i "$VO/04_q2_shark.mp3" \
  -i "$SFX/answer_reveal.wav" \
  -i "$VO/05_a2_shark.mp3" \
  -i "$VO/06_q3_venus.mp3" \
  -i "$SFX/answer_reveal.wav" \
  -i "$VO/07_a3_venus.mp3" \
  -i "$VO/08_q4_globe.mp3" \
  -i "$SFX/answer_reveal.wav" \
  -i "$VO/09_a4_globe.mp3" \
  -i "$VO/10_q5_honey.mp3" \
  -i "$SFX/answer_reveal.wav" \
  -i "$VO/11_a5_honey.mp3" \
  -i "$SFX/reveal_ding.wav" \
  -i "$VO/12_outro.mp3" \
  -stream_loop 9 -i "$SFX/suspense_bed.mp3" \
  -i "$VO/01_intro.mp3" \
  -filter_complex "
[0:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=0:all=1,volume=1.0[a0];
[1:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=6900:all=1,volume=1.0[a1];
[2:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=12430:all=1,volume=0.65[a2];
[3:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=12550:all=1,volume=1.0[a3];
[4:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=14767:all=1,volume=1.0[a4];
[5:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=20637:all=1,volume=0.65[a5];
[6:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=20757:all=1,volume=1.0[a6];
[7:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=22533:all=1,volume=1.0[a7];
[8:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=28403:all=1,volume=0.65[a8];
[9:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=28523:all=1,volume=1.0[a9];
[10:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=31267:all=1,volume=1.0[a10];
[11:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=36487:all=1,volume=0.65[a11];
[12:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=36607:all=1,volume=1.0[a12];
[13:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=38500:all=1,volume=1.0[a13];
[14:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=45340:all=1,volume=0.65[a14];
[15:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=45460:all=1,volume=1.0[a15];
[16:a]aformat=sample_rates=44100:channel_layouts=stereo,adelay=49300:all=1,volume=0.7[a16];
[17:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=49420:all=1,volume=1.0[a17];
[18:a]aformat=sample_rates=44100:channel_layouts=stereo,atrim=0:42.3,adelay=6500:all=1,volume=0.12[a18];
[19:a]${VOCHAIN},aformat=sample_rates=44100:channel_layouts=stereo,adelay=100:all=1,volume=1.0[a19];
[a0][a1][a2][a3][a4][a5][a6][a7][a8][a9][a10][a11][a12][a13][a14][a15][a16][a17][a18][a19]amix=inputs=20:duration=longest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[mixed]
" -map "[mixed]" -t $TOTAL audio_mix.wav

echo "audio mix done"
${FFPROBE:-ffprobe} -v error -show_entries format=duration -of csv=p=0 audio_mix.wav
