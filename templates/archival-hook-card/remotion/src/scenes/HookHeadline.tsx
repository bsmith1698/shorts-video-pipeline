// The written "hook" sentence — this format's only narration, since the rest of
// the video runs on real, unscripted archival audio instead of a voiceover.
// Phrase-colored per the role convention documented in hook_card_format_study:
// yellow = the named subject, red = the twist/danger, cyan = the title/proper
// noun, white = connective tissue. Persistent for the full video, matching direct
// observation of the reference channels (not a fade-in/fade-out beat).
//
// Segments come from public/video.json per video — write the hook directly from
// the verified transcript's own words where possible, so it echoes straight into
// the real audio that plays right after it. This component itself never changes
// per video; only the video.json content does.

export type HookSegment = { text: string; color: string };

const wordStyle: React.CSSProperties = {
  fontSize: 58,
  fontWeight: 900,
  fontFamily: "Arial Black, Arial, sans-serif",
  lineHeight: 1.15,
  textShadow: "0 3px 8px rgba(0,0,0,0.7)",
};

export const HookHeadline: React.FC<{ segments: HookSegment[] }> = ({ segments }) => (
  <div
    style={{
      position: "absolute",
      top: 380,
      left: 90,
      right: 90,
      textAlign: "left",
    }}
  >
    {segments.map((seg, i) => (
      <span key={i} style={{ ...wordStyle, color: seg.color }}>
        {seg.text}
      </span>
    ))}
  </div>
);
