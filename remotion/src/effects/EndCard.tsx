import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {heavyWeight} from '../fonts';
import type {CaptionStyle} from '../types';

const SECONDS = 2;

// Darkens the last 2 s and pops a call-to-action.
export const EndCard: React.FC<{text: string; style: CaptionStyle; font: string}> = ({text, style, font}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const start = durationInFrames - SECONDS * fps;
  if (frame < start) return null;
  const f = frame - start;
  const dim = interpolate(f, [0, 10], [0, 0.6], {extrapolateRight: 'clamp'});
  const pop = spring({frame: f - 4, fps, config: {damping: 10}});
  return (
    <AbsoluteFill style={{backgroundColor: `rgba(0,0,0,${dim})`, alignItems: 'center', justifyContent: 'center'}}>
      <div style={{transform: `scale(${pop})`, fontFamily: font, fontWeight: heavyWeight(style.font), fontSize: 92,
        color: style.highlightColor, textAlign: 'center', maxWidth: '85%', textTransform: 'uppercase',
        textShadow: '0 6px 30px rgba(0,0,0,0.8)'}}>
        {text}
      </div>
    </AbsoluteFill>
  );
};
