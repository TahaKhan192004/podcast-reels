import {AbsoluteFill, useCurrentFrame} from 'remotion';

// Animated film grain (SVG turbulence, reseeded every 2 frames).
export const Grain: React.FC<{opacity?: number}> = ({opacity = 0.07}) => {
  const seed = Math.floor(useCurrentFrame() / 2) % 12;
  return (
    <AbsoluteFill style={{opacity, mixBlendMode: 'overlay', pointerEvents: 'none'}}>
      <svg width="100%" height="100%">
        <filter id={`grain-${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#grain-${seed})`} />
      </svg>
    </AbsoluteFill>
  );
};
