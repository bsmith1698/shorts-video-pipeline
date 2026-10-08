# Production standards

Specs every video follows, whatever the format. Sourced from platform documentation (YouTube, TikTok, Instagram), EBU R128 loudness practice, and Derek Muller's research on misconception-first teaching, then tuned against real renders.

## Frame and safe zone

- Output 1080x1920 (9:16), 30 fps.
- Keep burned-in text inside a centered 900x1400 zone. That clears the like/comment/share UI on every major platform, so one render works everywhere.
- Frame 1 already has motion. No static title card before the content starts.

## Captions

- On every video. Most people watch muted.
- At most 30 characters per line and 2 lines on screen.
- Word-by-word highlight rather than block reveal.
- [`captions/KaraokeCaption.tsx`](../captions/KaraokeCaption.tsx) is the source of truth for the look (52 px Arial Black, 3 px black stroke, 3-word chunks, pop and glow on the active word). The only thing that changes per video is the `HIGHLIGHT` color.

## Audio

Target **-14 LUFS integrated, -1.5 dBTP true peak.** YouTube, TikTok and Instagram all normalize toward this, so louder just gets turned down.

The filter values live in [`audio/audio_post.sh`](../audio/audio_post.sh) (voiceover) and [`audio/audio_archival.sh`](../audio/audio_archival.sh) (real archival tape), not here, so the two can't drift apart.

- **Two-pass loudnorm.** Pass 1 measures with `print_format=json`; pass 2 feeds the `measured_*` values back with `linear=true`. Always verify with `ffmpeg -i out.mp4 -filter:a ebur128 -f null -`.
- **Never put `alimiter` after `loudnorm`.** Its `level` option defaults to true and re-maximizes the output (measured -12.4 LUFS instead of -14). If a limiter is needed, put it before `loudnorm` with `level=false`.
- **Measure every sound effect before picking a volume.** Two "soft" ElevenLabs SFX from the same session came back about 10 dB apart. Get the RMS with `ffmpeg -i sfx.mp3 -af astats=metadata=0 -f null -`, aim about 10 dB under the voiceover's RMS, and set `volume = 10^(gain_dB/20)`.
- **Keep the compressor threshold above the quiet SFX peaks.** Downward compression still narrows the gap between two signals that are both over threshold, which makes SFX sound as loud as the voice. The threshold in `audio_post.sh` went from 0.05 (-26 dBFS) to 0.14 (-17 dBFS) for this reason.
- **Peaky mixes can land 1 LU under target.** `loudnorm` refuses a linear gain that would break the true-peak ceiling. -15 LUFS is an acceptable result.
- **Leave archival tape alone.** Hiss, wow and flutter are the point. `audio_archival.sh` only removes sub-40 Hz rumble before normalizing.

## Script craft

- **Misconception first.** State the common wrong belief before the real answer. Muller's PhD research found this beats leading with the correct fact.
- **"But" and "therefore," never "and then."** Beats connected by a twist or a consequence form a chain the viewer has to follow. "And then" is a list.
- **Write the last line first.** Shorts loop, so the closing line is also the setup for the replay.
- **Keep a question open at every reveal.** Each answer should raise the next question as it lands.
- **Say the subject's name early.** Don't hold it back as a curiosity gap.

## Voiceover (ElevenLabs)

- Use `<break time="1.5s"/>` for exact pauses at question-to-answer boundaries, once or twice per generation at most.
- Short sentences keep TTS prosody lively. Long compound sentences flatten it.
- Real delivery runs about 2.2 to 2.9 words per second. Each sentence-ending pause costs time, so fragment-heavy lines run slower. Generate first, check durations with `ffprobe`, then trim.

## Remotion gotchas

- `<Video trimAfter={N}>` past the end of the source clip doesn't error cleanly. It hangs and then times out mid-render. `ffprobe` every clip first.
- Before a full render, check a few stills against the safe zone:

  ```bash
  npx remotion still src/index.ts <CompositionId> frame.png --frame=<N>
  ```
