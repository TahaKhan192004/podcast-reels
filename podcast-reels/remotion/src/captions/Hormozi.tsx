import {interpolate, spring} from 'remotion';
import {heavyWeight} from '../fonts';
import {activeIndex, fitFontSize, outline, type PresetProps} from './helpers';

// 2–3 huge words; the spoken word turns the highlight colour and pops; keywords use the secondary colour.
export const Hormozi: React.FC<PresetProps> = ({page, t, frame, fps, style, font}) => {
  const enter = spring({frame: frame - Math.round(page.start * fps), fps, config: {damping: 12, stiffness: 200}});
  const active = activeIndex(page, t);
  const size = fitFontSize(page, 108);

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        columnGap: size * 0.28,
        rowGap: 4,
        transform: `scale(${interpolate(enter, [0, 1], [0.8, 1])})`,
        opacity: enter,
      }}
    >
      {page.words.map((w, i) => {
        const isActive = i === active;
        const pop = isActive ? spring({frame: frame - Math.round(w.s * fps), fps, config: {damping: 10, stiffness: 260}}) : 0;
        const color = isActive ? style.highlightColor : w.emph ? style.secondaryColor : '#FFFFFF';
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              fontFamily: font,
              fontWeight: heavyWeight(style.font),
              fontSize: size,
              lineHeight: 1.08,
              color,
              textTransform: style.uppercase ? 'uppercase' : 'none',
              textShadow: outline(7),
              // the pop-scale grows the word by 7% of its own width per side; reserve that space in layout
              margin: `0 ${pop * 0.07 * w.text.length * size * 0.75 + pop * 6}px`,
              transform: `scale(${1 + 0.14 * pop}) rotate(${isActive ? -2 * pop : 0}deg)`,
            }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
