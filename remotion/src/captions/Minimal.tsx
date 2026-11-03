import {interpolate} from 'remotion';
import type {PresetProps} from './helpers';

// Clean, documentary-style subtitle on a soft dark pill.
export const Minimal: React.FC<PresetProps> = ({page, frame, fps, font}) => {
  const fade = interpolate(frame - page.start * fps, [0, 4], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <div
      style={{
        opacity: fade,
        transform: `translateY(${(1 - fade) * 12}px)`,
        background: 'rgba(0,0,0,0.55)',
        borderRadius: 18,
        padding: '14px 28px',
        fontFamily: font,
        fontWeight: 600,
        fontSize: 54,
        lineHeight: 1.25,
        color: 'white',
        textAlign: 'center',
        maxWidth: 900,
      }}
    >
      {page.words.map((w) => w.text).join(' ')}
    </div>
  );
};
