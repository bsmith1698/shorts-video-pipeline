# Trivia Short, pure ffmpeg

A complete 5-question trivia Short built with nothing but ffmpeg `drawtext`, `concat` and `amix`. No Remotion. It is kept as a worked example: the questions, timings and clip names are from one real video, so edit them for your own.

Run order (from any directory; output goes to `$WORK_DIR`, default `./render`):

```bash
export CLIPS_DIR=/path/to/clips   # b-roll mp4s, plus VO/ and SFX/ subfolders
./build.sh      # writes the on-screen text files
./intro.sh      # 5-clip flash intro with title text
./segments.sh   # one segment per question: question text, answer reveal, score pips
./audio.sh      # VO + SFX + ducked suspense bed, cleaned and normalized to -14 LUFS
```

Then concat the segments in order (`seg/A_intro.mp4`, `seg/B.mp4` … `seg/G.mp4`) and mux with `audio_mix.wav`.

Fonts default to the macOS system Arial, Arial Bold and Impact paths. Override `FB`/`FI`/`FR` in the scripts on other systems. `FFMPEG`/`FFPROBE` env vars select a specific ffmpeg build.
