import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';

export const ProgressBar: React.FC<{color: string}> = ({color}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end'}}>
      <div style={{height: 12, background: 'rgba(255,255,255,0.18)'}}>
        <div style={{height: '100%', width: `${(frame / durationInFrames) * 100}%`, background: color,
          boxShadow: `0 0 18px ${color}`}} />
      </div>
    </AbsoluteFill>
  );
};
