import {AbsoluteFill} from 'remotion';

export const BrandHandle: React.FC<{handle: string; font: string}> = ({handle, font}) => (
  <AbsoluteFill style={{alignItems: 'center', justifyContent: 'flex-start', top: '5.5%'}}>
    <div style={{fontFamily: font, fontWeight: 600, fontSize: 38, color: 'white', opacity: 0.8,
      textShadow: '0 2px 10px rgba(0,0,0,0.8)', letterSpacing: 1}}>
      {handle}
    </div>
  </AbsoluteFill>
);
