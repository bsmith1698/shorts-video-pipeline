// Canonical signature caption style for this channel — used in every video.
// Copy this file verbatim into each new project's src/scenes/KaraokeCaption.tsx.
// The ONLY thing that should change per video is the HIGHLIGHT color below —
// font, stroke, motion, chunking, and position stay fixed so every video
// reads as the same recognizable style. See docs/production-standards.md > Captions.

import { useCurrentFrame, interpolate } from "remotion";

const HIGHLIGHT = "#FFD700"; // set per video to match its topic/palette
const CHUNK_SIZE = 3;
const FPS = 30;
// Real archival audio has genuine silences (unlike tightly-paced TTS VO) — once a
// gap since the last word exceeds this, captions clear instead of freezing on
// whatever word is nearest. Also governs the delay before the very first word.
const GAP_HIDE_MS = 450;

export type WordTiming = { word: string; startMs: number; endMs: number };

export const KaraokeCaption: React.FC<{ words: WordTiming[]; voStartFrame: number }> = ({ words, voStartFrame }) => {
  const frame = useCurrentFrame();
  const localMs = ((frame - voStartFrame) / FPS) * 1000;

  // Currently mid-word: highlight it, no gap logic needed.
  let activeIndex = words.findIndex((w) => localMs >= w.startMs && localMs < w.endMs);

  if (activeIndex === -1) {
    // Between words (or before the first / after the last). Find the most
    // recently FINISHED word — never jump ahead to a word that hasn't been
    // said yet, and never keep rendering past a real silence.
    let lastEndedIndex = -1;
    for (let i = 0; i < words.length; i++) {
      if (words[i].endMs <= localMs) lastEndedIndex = i;
      else break;
    }
    if (lastEndedIndex === -1) return null; // before the first word starts
    const gapMs = localMs - words[lastEndedIndex].endMs;
    if (gapMs > GAP_HIDE_MS) return null; // silence long enough — clear captions
    activeIndex = lastEndedIndex; // brief natural trailing highlight, then gone
  }

  const chunkStart = Math.floor(activeIndex / CHUNK_SIZE) * CHUNK_SIZE;
  const chunk = words.slice(chunkStart, chunkStart + CHUNK_SIZE);

  if (chunk.length === 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        left: 80,
        right: 80,
        bottom: 420,
        textAlign: "center",
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "0 16px",
      }}
    >
      {chunk.map((w, i) => {
        const wordIndex = chunkStart + i;
        const isActive = wordIndex === activeIndex;
        const wordStartFrame = voStartFrame + (w.startMs / 1000) * FPS;
        const pop = interpolate(frame, [wordStartFrame, wordStartFrame + 6], [0.75, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        return (
          <span
            key={wordIndex}
            style={{
              fontSize: 52,
              fontWeight: 900,
              fontFamily: "Arial Black, Arial, sans-serif",
              color: isActive ? HIGHLIGHT : "#FFFFFF",
              WebkitTextStroke: "3px #000000",
              paintOrder: "stroke fill",
              scale: isActive ? pop : 1,
              textShadow: isActive ? `0 0 30px ${HIGHLIGHT}99` : "none",
              textTransform: "capitalize",
            }}
          >
            {w.word}
          </span>
        );
      })}
    </div>
  );
};
