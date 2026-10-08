// Top-level composition for the "hook card" archival-audio format. Structurally
// different from this channel's other Remotion projects (trash-companies-short,
// powder-toy-short): those are N independent self-contained beats, each with its
// own VO and local timeline, so Footage/Logo/KaraokeCaption/<Audio> all nest
// inside one <Sequence> per beat. This format has ONE continuous real archival
// audio track but 2-3 visual cuts between real footage clips used as
// authenticity evidence underneath it. So: IdentityCard, HookHeadline,
// KaraokeCaption, and the real audio/music-bed <Audio> tags are top-level
// siblings reading the global frame directly — only the footage cuts go inside
// <Sequence>s. Keeps each beat cut from re-triggering a fresh audio decode
// (which risked pops at cut points under the nested pattern).
//
// This file itself never changes per video — every video-specific value
// (hook text, audio file, footage list, brand) comes from public/video.json,
// read in Root.tsx's calculateMetadata. See _templates/archival-hook-card/README.md.

import { AbsoluteFill, Sequence, staticFile } from "remotion";
import { Audio } from "@remotion/media";
import { IdentityCard } from "./scenes/IdentityCard";
import { HookHeadline, HookSegment } from "./scenes/HookHeadline";
import { FootageWindow } from "./scenes/FootageWindow";
import { KaraokeCaption } from "./scenes/KaraokeCaption";
import wordTimings from "./data/wordTimings.json";

export type FootageBeat = {
  src: string;
  trimBefore: number;
  trimAfter: number;
  fromFrame: number;
  durationInFrames: number;
};

export type ArchivalHookCardProps = {
  audioSrc: string;
  musicBedSrc?: string;
  musicBedVolume?: number;
  wordTimingsKey: string;
  beats: FootageBeat[];
  hook: HookSegment[];
};

export const ArchivalHookCard: React.FC<ArchivalHookCardProps> = ({
  audioSrc,
  musicBedSrc,
  musicBedVolume,
  wordTimingsKey,
  beats,
  hook,
}) => {
  const words = (wordTimings as Record<string, { word: string; startMs: number; endMs: number }[]>)[wordTimingsKey] ?? [];

  return (
    <AbsoluteFill style={{ background: "#000000" }}>
      {beats.map((beat, i) => (
        <Sequence key={i} from={beat.fromFrame} durationInFrames={beat.durationInFrames} layout="none">
          <FootageWindow src={beat.src} trimBefore={beat.trimBefore} trimAfter={beat.trimAfter} />
        </Sequence>
      ))}

      <IdentityCard />
      <HookHeadline segments={hook} />
      <KaraokeCaption words={words} voStartFrame={0} />

      <Audio src={staticFile(audioSrc)} volume={1} />
      {musicBedSrc && <Audio src={staticFile(musicBedSrc)} volume={musicBedVolume ?? 0.15} />}
    </AbsoluteFill>
  );
};
