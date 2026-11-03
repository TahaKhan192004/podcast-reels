import {interpolate} from 'remotion';
import {outline, type PresetProps} from './helpers';

// Full line on screen; each word fills left→right with the highlight colour as it is spoken.
export const Karaoke: React.FC<PresetProps> = ({page, t, frame, fps, style, font}) => {
  const fade = interpolate(frame - page.start * fps, [0, 5], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '4px 16px', opacity: fade}}>
      {page.words.map((w, i) => {
        const p = interpolate(t, [w.s, Math.max(w.e, w.s + 0.05)], [0, 100], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        const common: React.CSSProperties = {
          fontFamily: font,
          fontWeight: 800,
          fontSize: 74,
          lineHeight: 1.15,
          whiteSpace: 'nowrap',
        };
        return (
          <span key={i} style={{position: 'relative', display: 'inline-block'}}>
            <span style={{...common, color: 'rgba(255,255,255,0.95)', textShadow: outline(5)}}>{w.text}</span>
            <span
              style={{
                ...common,
                position: 'absolute',
                left: 0,
                top: 0,
                color: w.emph ? style.secondaryColor : style.highlightColor,
                clipPath: `inset(-20% ${100 - p}% -20% -5%)`,
                textShadow: outline(5),
              }}
            >
              {w.text}
            </span>
          </span>
        );
      })}
    </div>
  );
};
