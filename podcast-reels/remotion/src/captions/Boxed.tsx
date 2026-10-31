import {spring} from 'remotion';
import {heavyWeight} from '../fonts';
import {activeIndex, fitFontSize, outline, type PresetProps} from './helpers';

// TikTok style: words appear one by one as spoken; the current word sits on a coloured box.
export const Boxed: React.FC<PresetProps> = ({page, t, frame, fps, style, font}) => {
  const active = activeIndex(page, t);
  const size = fitFontSize(page, 96, 880);

  return (
    <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '10px 14px'}}>
      {page.words.map((w, i) => {
        if (i > active) return null;
        const pop = spring({frame: frame - Math.round(w.s * fps), fps, config: {damping: 11, stiffness: 240}});
        const isActive = i === active;
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              fontFamily: font,
              fontWeight: heavyWeight(style.font),
              fontSize: size,
              lineHeight: 1.1,
              padding: '4px 18px',
              borderRadius: 16,
              background: isActive ? style.highlightColor : 'transparent',
              color: isActive ? '#000' : w.emph ? style.secondaryColor : '#fff',
              textShadow: isActive ? 'none' : outline(6),
              textTransform: style.uppercase ? 'uppercase' : 'none',
              transform: `scale(${0.5 + 0.5 * pop}) rotate(${isActive ? -3 : 0}deg)`,
              boxShadow: isActive ? '0 10px 30px rgba(0,0,0,0.45)' : 'none',
            }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
