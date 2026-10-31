import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {heavyWeight} from '../fonts';
import type {CaptionStyle, Moment} from '../types';

// Big pop-up text/emoji callouts (any moment with `text`, typically effect 'text').
export const MomentTexts: React.FC<{moments: Moment[]; style: CaptionStyle; font: string}> = ({moments, style, font}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  const active = moments.filter(
    (m) => m.text && !['stat', 'kinetic', 'lower', 'burst'].includes(m.effect) && t >= m.t && t < m.t + m.duration,
  );
  return (
    <>
      {active.map((m, i) => {
        const f = frame - Math.round(m.t * fps);
        const pop = spring({frame: f, fps, config: {damping: 9, stiffness: 180}});
        const out = interpolate(t, [m.t + m.duration - 0.2, m.t + m.duration], [1, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <AbsoluteFill key={i} style={{alignItems: 'center', top: '24%', justifyContent: 'flex-start'}}>
            <div
              style={{
                transform: `scale(${pop * (0.9 + 0.1 * out)}) rotate(${interpolate(pop, [0, 1], [-12, -3])}deg)`,
                opacity: out,
                background: style.secondaryColor,
                color: '#000',
                fontFamily: font,
                fontWeight: heavyWeight(style.font),
                fontSize: 84,
                lineHeight: 1.05,
                padding: '18px 34px',
                borderRadius: 22,
                maxWidth: '86%',
                textAlign: 'center',
                textTransform: 'uppercase',
                boxShadow: '0 18px 50px rgba(0,0,0,0.45)',
              }}
            >
              {m.text}
            </div>
          </AbsoluteFill>
        );
      })}
    </>
  );
};
