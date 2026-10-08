# Archival Hook Card template

Reusable Remotion template for the archival-audio format: an X/Twitter-style post card,
an embedded video window and 3-word karaoke captions over real archival audio, with no
voiceover. The visual system stays identical across every video.

## What varies per video vs. what doesn't

Per-video (edit `public/video.json` and drop in assets — never edit `.tsx` files):
- `audioSrc` — the trimmed archival clip
- `footage` — list of real footage clips, auto-measured and auto-cycled to fill the audio's duration
- `hook` — array of `{text, color}` segments for the headline
- `wordTimingsKey` / `src/data/wordTimings.json` — caption timing from whisper-cli output

Locked, do not touch per video (this is the brand):
- `IdentityCard.tsx` — channel name/handle/avatar
- `KaraokeCaption.tsx` — caption visual style (per docs/production-standards.md, same file as every other format on the channel)
- `HookHeadline.tsx`, `FootageWindow.tsx`, `ArchivalHookCard.tsx`, `Root.tsx` — layout/logic

## New video workflow

```
./new_video.sh <slug>
```

Run `npm install` in `remotion/` once first. `new_video.sh` then creates
`projects/<slug>-short/` with `remotion/node_modules` symlinked back to this template
(about 660 MB, so it is never reinstalled or copied per video). Then:

1. Drop trimmed archival audio into `remotion/public/audio/mission_audio.wav`
2. Drop footage clips into `remotion/public/footage/`
3. `whisper-cli` the audio, run `parse_whisper_timings.py`, write to `remotion/src/data/wordTimings.json`
4. Edit `remotion/public/video.json`: footage file list, hook segments
5. `cd remotion && npx remotion render ArchivalHookCard ../out/raw.mp4`
6. `../../audio/audio_archival.sh . FINAL_NAME.mp4` (run from the project dir; no VO-tuned EQ/compression — see that script's header comment for why)

## Design notes

- Footage duration is measured live via `mediabunny` in `calculateMetadata`
  (same mechanism as audio duration) — no more hand-typing frame counts per
  clip the way gemini8-short's original `REAL_CLIP_FRAMES` did. Drop clips in,
  the beat list builds itself and cycles if footage is shorter than the audio.
- `HookHeadline` takes a `segments` prop instead of hardcoded JSX spans —
  color convention (yellow=subject, red=twist/danger, cyan=title/proper noun,
  white=connective) still applies, just authored in `video.json` now.
