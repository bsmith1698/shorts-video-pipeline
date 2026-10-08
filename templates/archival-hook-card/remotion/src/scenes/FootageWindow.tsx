// Letterboxed, rounded-corner inset video window — the "black bars top and
// bottom" framing observed on both reference channels. Unlike every other
// project on this channel (which runs Footage full-bleed via AbsoluteFill),
// this format deliberately insets the clip so it reads as "found footage in a
// frame" rather than native vertical video.
//
// Pre-crop source clips in ffmpeg to a subject-centered window BEFORE handing
// them here — @remotion/media's <Video> objectFit="cover" always center-crops
// with no objectPosition override (confirmed against the compiled source this
// session), so a wide source fed in raw will crop to the wrong part of frame.

import { AbsoluteFill, staticFile } from "remotion";
import { Video } from "@remotion/media";

export type FootageWindowProps = {
  src: string;
  trimBefore: number;
  trimAfter: number;
};

// Sized to match the real sourced clips' native 1080x1920 aspect (~0.5625) so
// objectFit="cover" needs almost no cropping — the agent's own framing choices
// (verified by eye) are preserved instead of getting re-cropped into a mismatched
// box. This also means generous black margins on both sides, not just top/bottom.
const WINDOW_TOP = 704;
const WINDOW_WIDTH = 538;
const WINDOW_HEIGHT = 956;
const WINDOW_LEFT = (1080 - WINDOW_WIDTH) / 2;

export const FootageWindow: React.FC<FootageWindowProps> = ({ src, trimBefore, trimAfter }) => (
  <AbsoluteFill>
    <div
      style={{
        position: "absolute",
        top: WINDOW_TOP,
        left: WINDOW_LEFT,
        width: WINDOW_WIDTH,
        height: WINDOW_HEIGHT,
        borderRadius: 28,
        overflow: "hidden",
        boxShadow: "0 12px 40px rgba(0,0,0,0.6)",
      }}
    >
      <Video
        src={staticFile(src)}
        muted
        trimBefore={trimBefore}
        trimAfter={trimAfter}
        objectFit="cover"
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  </AbsoluteFill>
);
