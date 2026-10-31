import {AbsoluteFill, Easing, interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Moment, ZoomBeat} from '../types';

/**
 * Virtual camera over the footage:
 *  • slow push-in across the whole clip
 *  • jump-cut zoom "beats" at sentence boundaries (hard cuts between 1.0 and 1.12)
 *  • punch     → springy zoom-in, holds, eases back
 *  • zoom_out  → starts tight and pulls back
 *  • shake     → decaying camera shake
 *  • glitch    → violent jitter + colour shift
 */
export const Camera: React.FC<{
  moments: Moment[];
  beats: ZoomBeat[];
  autoZoom: boolean;
  children: React.ReactNode;
}> = ({moments, beats, autoZoom, children}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const t = frame / fps;

  let scale = 1;
  let x = 0;
  let y = 0;
  let filter = 'none';

  if (autoZoom) {
    scale *= interpolate(frame, [0, durationInFrames], [1, 1.06]);
    let beat = 1;
    for (const b of beats) if (b.t <= t) beat = b.scale;
    scale *= beat;
  }

  for (const m of moments) {
    const local = t - m.t;
    if (local < 0 || local > m.duration + 0.5) continue;
    const startFrame = Math.round(m.t * fps);

    if (m.effect === 'punch') {
      const inn = spring({frame: frame - startFrame, fps, config: {damping: 14, stiffness: 220}});
      const out = interpolate(local, [m.duration, m.duration + 0.4], [1, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      });
      scale *= 1 + 0.2 * inn * out;
    } else if (m.effect === 'zoom_out') {
      const p = interpolate(local, [0, m.duration], [0, 1], {
        extrapolateRight: 'clamp',
        easing: Easing.out(Easing.cubic),
      });
      scale *= 1 + 0.3 * (1 - p);
    } else if (m.effect === 'shake' || m.effect === 'glitch') {
      const amp = (m.effect === 'glitch' ? 34 : 20) * Math.max(0, 1 - local / m.duration);
      x += (random(`sx-${frame}`) - 0.5) * 2 * amp;
      y += (random(`sy-${frame}`) - 0.5) * 2 * amp;
      if (m.effect === 'shake') scale *= 1.04; // hide the edges while shaking
      if (m.effect === 'glitch' && local < 0.3) {
        scale *= 1.06;
        filter = `hue-rotate(${Math.round(random(`h-${frame}`) * 180)}deg) saturate(1.8) contrast(1.2)`;
      }
    }
  }

  return (
    <AbsoluteFill
      style={{
        transform: `translate(${x}px, ${y}px) scale(${scale})`,
        transformOrigin: '50% 38%', // faces sit in the upper-middle of a vertical frame
        filter,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
