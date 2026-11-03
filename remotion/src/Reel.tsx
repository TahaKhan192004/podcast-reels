import {AbsoluteFill, Audio, OffthreadVideo, staticFile} from 'remotion';
import {Captions} from './captions/Captions';
import {BrandHandle} from './effects/BrandHandle';
import {Camera} from './effects/Camera';
import {EndCard} from './effects/EndCard';
import {FlashLayer} from './effects/Flash';
import {Grain} from './effects/Grain';
import {HookTitle} from './effects/HookTitle';
import {MomentTexts} from './effects/MomentText';
import {MotionGraphics} from './effects/MotionGraphics';
import {ProgressBar} from './effects/ProgressBar';
import {Vignette} from './effects/Vignette';
import {getFont} from './fonts';
import type {ReelProps} from './types';

// Layer order (bottom → top): video under camera moves → grade → flashes → pop texts → captions → hook → UI
export const Reel: React.FC<ReelProps> = (p) => {
  const font = getFont(p.captionStyle.font);
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      <Camera moments={p.moments} beats={p.zoomBeats} autoZoom={p.effects.autoZoom}>
        {p.videoFile ? (
          <OffthreadVideo src={staticFile(p.videoFile)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        ) : (
          <AbsoluteFill style={{background: 'linear-gradient(160deg,#1d2b64,#5b247a 55%,#f8cdda)'}} />
        )}
      </Camera>

      {p.effects.vignette && <Vignette />}
      {p.effects.grain && <Grain />}
      <FlashLayer moments={p.moments} />
      <MomentTexts moments={p.moments} style={p.captionStyle} font={font} faceBand={p.faceBand} />
      <MotionGraphics moments={p.moments} style={p.captionStyle} font={font} faceBand={p.faceBand} />
      <Captions pages={p.pages} preset={p.preset} style={p.captionStyle} font={font} />
      {p.hook && <HookTitle text={p.hook} style={p.captionStyle} font={font} />}
      {p.brandHandle && <BrandHandle handle={p.brandHandle} font={font} />}
      {p.endCard && <EndCard text={p.endCard} style={p.captionStyle} font={font} />}
      {p.effects.progressBar && <ProgressBar color={p.captionStyle.highlightColor} />}
      {p.music && <Audio src={staticFile(p.music.file)} volume={p.music.volume} loop />}
    </AbsoluteFill>
  );
};
