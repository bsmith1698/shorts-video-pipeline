// Persistent per-video branding overlay for the "hook card" format — modeled on
// popular "post card" history Shorts channels.
// Edit CHANNEL_NAME / CHANNEL_HANDLE and public/logos/ for your own channel.
// Mounted once at the composition's top level, not per-Sequence, since it's on
// screen for the full video like the reference channels' identity cards.

import { staticFile } from "remotion";

const CHANNEL_NAME = "Everyday Shorts";
const CHANNEL_HANDLE = "@everyday_shorts-x";

const CheckBadge: React.FC = () => (
  <div
    style={{
      width: 24,
      height: 24,
      borderRadius: "50%",
      background: "#3EA9E8",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      flex: "none",
    }}
  >
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
      <path d="M4 12.5L9.5 18L20 6" stroke="#FFFFFF" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  </div>
);

export const IdentityCard: React.FC = () => (
  <div
    style={{
      position: "absolute",
      top: 260,
      left: 90,
      display: "flex",
      alignItems: "center",
      gap: 16,
    }}
  >
    <img
      src={staticFile("logos/everyday_shorts_avatar.jpg")}
      style={{
        width: 84,
        height: 84,
        borderRadius: "50%",
        boxShadow: "0 4px 14px rgba(0,0,0,0.5)",
      }}
    />
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            fontSize: 34,
            fontWeight: 900,
            fontFamily: "Arial Black, Arial, sans-serif",
            color: "#FFFFFF",
            textShadow: "0 2px 6px rgba(0,0,0,0.6)",
          }}
        >
          {CHANNEL_NAME}
        </span>
        <CheckBadge />
      </div>
      <span
        style={{
          fontSize: 24,
          fontWeight: 500,
          fontFamily: "Arial, sans-serif",
          color: "rgba(255,255,255,0.65)",
          textShadow: "0 2px 6px rgba(0,0,0,0.6)",
        }}
      >
        {CHANNEL_HANDLE}
      </span>
    </div>
  </div>
);
