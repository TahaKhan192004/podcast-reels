import {Composition} from 'remotion';
import {Reel} from './Reel';
import {sampleProps} from './sample';
import type {ReelProps} from './types';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Reel"
    component={Reel as unknown as React.FC<Record<string, unknown>>}
    defaultProps={sampleProps as unknown as Record<string, unknown>}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={300}
    calculateMetadata={({props}) => {
      const p = props as unknown as ReelProps;
      return {
        durationInFrames: Math.max(1, Math.ceil(p.durationSec * p.fps)),
        fps: p.fps,
        width: p.width,
        height: p.height,
      };
    }}
  />
);
