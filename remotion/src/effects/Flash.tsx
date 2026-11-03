import {AbsoluteFill, interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Moment} from '../types';

// White flash for 'flash', RGB slice bars for 'glitch'.
export const FlashLayer: React.FC<{moments: Moment[]}> = ({moments}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  const layers: React.ReactNode[] = [];
  moments.forEach((m, i) => {
    const local = t - m.t;
    if (m.effect === 'flash' && local >= 0 && local < 0.45) {
      const o = interpolate(local, [0, 0.04, 0.45], [0, 0.9, 0], {extrapolateRight: 'clamp'});
      layers.push(<AbsoluteFill key={i} style={{backgroundColor: 'white', opacity: o}} />);
    }
    if (m.effect === 'glitch' && local >= 0 && local < 0.35) {
      const bars = Array.from({length: 7}, (_, b) => {
        const top = random(`gt-${frame}-${b}`) * 100;
        const h = 1 + random(`gh-${frame}-${b}`) * 6;
        const shift = (random(`gs-${frame}-${b}`) - 0.5) * 120;
        const color = b % 2 ? 'rgba(0,255,255,0.35)' : 'rgba(255,0,180,0.35)';
        return (
          <div
            key={b}
            style={{position: 'absolute', left: shift, right: -shift, top: `${top}%`, height: `${h}%`,
              background: color, mixBlendMode: 'screen'}}
          />
        );
      });
      layers.push(<AbsoluteFill key={i}>{bars}</AbsoluteFill>);
    }
  });
  return <>{layers}</>;
};
