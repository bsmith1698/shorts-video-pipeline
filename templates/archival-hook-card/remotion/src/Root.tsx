import "./index.css";
import { CalculateMetadataFunction, Composition, staticFile } from "remotion";
import { ArchivalHookCard, ArchivalHookCardProps, FootageBeat } from "./ArchivalHookCard";
import { getAudioDuration } from "./get-audio-duration";
import videoConfig from "../public/video.json";

const FPS = 30;

type VideoConfig = {
  audioSrc: string;
  wordTimingsKey: string;
  musicBedSrc?: string;
  musicBedVolume?: number;
  footage: string[];
  hook: { text: string; color: string }[];
};

const config = videoConfig as VideoConfig;

// Cycles through public/video.json's footage list to fill the real audio's
// duration, measuring each clip's real length instead of hand-typing frame
// counts per video (gemini8-short's original REAL_CLIP_FRAMES/BEAT_SRCS
// constants — this replaces that manual step). If footage runs shorter than
// the audio, clips repeat in order, same as documentary b-roll commonly is
// under a longer audio bed.
const calculateMetadata: CalculateMetadataFunction<ArchivalHookCardProps> = async () => {
  const audioDuration = await getAudioDuration(staticFile(config.audioSrc));
  const durationInFrames = Math.round(audioDuration * FPS);

  const footageDurationsSec = await Promise.all(
    config.footage.map((src) => getAudioDuration(staticFile(src)))
  );
  const footageFrames = footageDurationsSec.map((d) => Math.round(d * FPS));

  let cursor = 0;
  let clipIndex = 0;
  const beats: FootageBeat[] = [];
  while (cursor < durationInFrames && config.footage.length > 0) {
    const src = config.footage[clipIndex % config.footage.length];
    const full = footageFrames[clipIndex % config.footage.length];
    const remaining = durationInFrames - cursor;
    const thisBeatFrames = Math.min(full, remaining);
    beats.push({ src, trimBefore: 0, trimAfter: thisBeatFrames, fromFrame: cursor, durationInFrames: thisBeatFrames });
    cursor += thisBeatFrames;
    clipIndex += 1;
  }

  return {
    durationInFrames,
    props: {
      audioSrc: config.audioSrc,
      musicBedSrc: config.musicBedSrc,
      musicBedVolume: config.musicBedVolume,
      wordTimingsKey: config.wordTimingsKey,
      beats,
      hook: config.hook,
    },
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ArchivalHookCard"
        component={ArchivalHookCard}
        durationInFrames={300}
        fps={FPS}
        width={1080}
        height={1920}
        defaultProps={{ audioSrc: config.audioSrc, wordTimingsKey: config.wordTimingsKey, beats: [], hook: config.hook }}
        calculateMetadata={calculateMetadata}
      />
    </>
  );
};
