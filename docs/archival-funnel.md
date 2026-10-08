# Archival audio sourcing funnel

How the `sourcing/` scripts turn huge public archives (NASA mission audio, DVIDS military/Coast Guard releases) into a short list of clips worth building a video around.

## The four tiers

Only tier 4 is ever treated as "ready to build."

1. **Raw pool.** Anything a search returns: a transcript phrase hit or a DVIDS search result. Noisy on purpose.
2. **Title and description triage.** Text only. No downloads. `triage_titles.py` for DVIDS, phrase scoring in `score_transcript.py` for NASA transcripts. Drops fatalities, training exercises, produced broadcasts and clips that are too short.
3. **Deep analysis.** Only spent on tier-2 survivors. `quality_extract_transcribe.py` pulls the real audio and transcribes it with whisper large-v3; a person (or an LLM reading the transcript) scores it, and `apply_quality.py` merges the scores back. `verify_footage.py` checks that any paired footage is from the same incident and is legible once cropped to 9:16.
4. **Candidate list.** `quality_score >= 4`, at least 25 seconds of real audio, and real footage of the same incident.

Every writer merges into `queue.json` by `slug` and only adds its own fields, so the scripts can run in any order and be re-run safely.

## Lessons that shaped the code

- **Check the transcript's time format against known events.** The Apollo 13 transcript's time field looks like seconds but is a colon-less clock string (`0555517` = GET 055:55:17, the "Houston, we've had a problem" call). Parsing it as an integer gave plausible but wrong timestamps. `parse_get()` in `score_transcript.py` handles it.
- **Pull audio from the channel the phrase was said on.** Merging hits across channels once produced clips that never contained the phrase that scored them.
- **Phrase hits find real audio, not drama.** Most top keyword hits were routine radio traffic. Scoring is a shortlist step, never a substitute for listening.
- **Use HTTP Range requests for deep seeks.** ffmpeg's remote `-ss` read the file linearly from byte 0 (about 5 minutes for a deep seek). Computing the byte offset from the file's constant bitrate and letting curl fetch the range took under a second.
- **"Footage exists from the same unit that week" is not "footage of this incident."** An audit found most such pairings were unrelated b-roll, hence the title-match tiers in `verify_footage.py`.

## Guardrails

1. Whisper can hallucinate. Every clip is listened to end to end before it is used.
2. Nothing ships unless its queue entry is `verified: true`.
3. Keep the visual system identical every video. Only audio, footage and hook text change.
4. No audio of real deaths (Apollo 1, Challenger, Columbia are excluded).

## Data sources

- Apollo 13 Mission Control audio and transcripts: [apolloinrealtime.org](https://apolloinrealtime.org). Channel names and tape URLs are reverse-engineered from the site's own player (see `CHANNEL_NAMES` and `audio_url_for()` in `score_transcript.py`). The transcript file itself is not included; place it at `_archive/unzipped/A13_all_channels.txt` with `_archive/tape_ranges.csv`.
- DVIDS: [api.dvidshub.net](https://api.dvidshub.net). Needs a free API key in `.env`.
