import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import type {CaptionPage, CaptionStyle, Preset} from '../types';
import type {PresetProps} from './helpers';
import {Boxed} from './Boxed';
import {Hormozi} from './Hormozi';
import {Karaoke} from './Karaoke';
import {Minimal} from './Minimal';

const PRESETS: Record<Preset, React.FC<PresetProps>> = {hormozi: Hormozi, karaoke: Karaoke, boxed: Boxed, minimal: Minimal};

// Picks the page on screen at this frame and hands it to the chosen preset.
export const Captions: React.FC<{pages: CaptionPage[]; preset: Preset; style: CaptionStyle; font: string}> = ({
  pages,
  preset,
  style,
  font,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const page = pages.find((p) => t >= p.start && t < p.end);
  if (!page) return null;
  const Comp = PRESETS[preset] ?? Hormozi;
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div
        style={{
          position: 'absolute',
          top: `${style.position * 100}%`,
          transform: 'translateY(-50%)',
          width: '90%',
          display: 'flex',
          justifyContent: 'center',
        }}
      >
        <Comp page={page} t={t} frame={frame} fps={fps} style={style} font={font} />
      </div>
    </AbsoluteFill>
  );
};
