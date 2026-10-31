import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {heavyWeight} from '../fonts';
import type {CaptionStyle} from '../types';

const SHOW_SEC = 2.8;

// Scroll-stopping hook text for the first ~3 s: white card, words stagger in, then flies out.
export const HookTitle: React.FC<{text: string; style: CaptionStyle; font: string}> = ({text, style, font}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  if (t > SHOW_SEC + 0.4) return null;

  const enter = spring({frame, fps, config: {damping: 12, stiffness: 160}});
  const exit = interpolate(t, [SHOW_SEC, SHOW_SEC + 0.35], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const words = text.split(/\s+/);

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'flex-start', top: '13%'}}>
      <div
        style={{
          transform: `translateY(${-exit * 260}px) scale(${0.6 + 0.4 * enter}) rotate(-2deg)`,
          opacity: 1 - exit,
          background: 'white',
          borderRadius: 26,
          padding: '22px 36px',
          maxWidth: '88%',
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          textAlign: 'center',
        }}
      >
        {words.map((w, i) => {
          const s = spring({frame: frame - 4 - i * 2, fps, config: {damping: 14}});
          return (
            <span
              key={i}
              style={{
                display: 'inline-block',
                margin: '0 10px',
                fontFamily: font,
                fontWeight: heavyWeight(style.font),
                fontSize: 76,
                lineHeight: 1.1,
                color: i === words.length - 1 ? '#E0115F' : '#111',
                textTransform: 'uppercase',
                transform: `translateY(${(1 - s) * 40}px)`,
                opacity: s,
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
