import {AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {getFont, heavyWeight} from '../fonts';
import type {CaptionStyle, Moment} from '../types';

// Motion-graphic moments chosen by Claude (effect + short text); all animation is deterministic code, so
// rendering them costs no tokens.
//   stat     "32%|OF ALL HEALINGS"   count-up number card            (number|label)
//   kinetic  "SAME DAD OPPOSITE LIVES"  words slam in, last word in accent serif
//   lower    "KEY IDEA|The nocebo effect"  lower-third tag sliding in from the left (title|subtitle)
//   burst    "🔥🔥"                emoji pops and radiates particles

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const fade = (t: number, m: Moment) =>
  interpolate(t, [m.t + m.duration - 0.25, m.t + m.duration], [1, 0], clamp);

const Stat: React.FC<{m: Moment; style: CaptionStyle}> = ({m, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const f = frame - Math.round(m.t * fps);
  const [numText, label = ''] = m.text.split('|');
  const match = numText.match(/^([^\d]*)(\d[\d,.]*)(.*)$/);
  const enter = spring({frame: f, fps, config: {damping: 14, stiffness: 140}});
  const out = fade(t, m);
  let shown = numText;
  if (match) {
    const target = parseFloat(match[2].replace(/,/g, ''));
    const decimals = (match[2].split('.')[1] || '').length;
    const v = target * interpolate(f, [0, fps * 0.8], [0, 1], {...clamp, easing: (x) => 1 - Math.pow(1 - x, 3)});
    shown = `${match[1]}${v.toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals})}${match[3]}`;
  }
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'flex-start', top: '19%'}}>
      <div
        style={{
          opacity: out,
          transform: `translateY(${(1 - enter) * 70}px) scale(${0.85 + 0.15 * enter})`,
          background: 'rgba(8,8,14,0.72)',
          border: `3px solid ${style.highlightColor}`,
          borderRadius: 34,
          padding: '14px 52px 22px',
          textAlign: 'center',
          boxShadow: `0 0 60px ${style.highlightColor}55, 0 24px 60px rgba(0,0,0,0.5)`,
          backdropFilter: 'blur(6px)',
        }}
      >
        <div
          style={{
            fontFamily: getFont('Oswald'),
            fontWeight: 700,
            fontSize: 190,
            lineHeight: 1.05,
            color: style.highlightColor,
            letterSpacing: -2,
          }}
        >
          {shown}
        </div>
        {label && (
          <div
            style={{
              fontFamily: getFont('Poppins'),
              fontWeight: 800,
              fontSize: 46,
              color: '#fff',
              textTransform: 'uppercase',
              letterSpacing: 3,
              marginTop: -6,
            }}
          >
            {label}
          </div>
        )}
        <div
          style={{
            height: 6,
            borderRadius: 3,
            marginTop: 14,
            background: style.highlightColor,
            width: `${interpolate(f, [4, 20], [0, 100], clamp)}%`,
            marginInline: 'auto',
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

const Kinetic: React.FC<{m: Moment; style: CaptionStyle; font: string}> = ({m, style, font}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const f = frame - Math.round(m.t * fps);
  const words = m.text.trim().split(/\s+/);
  const out = fade(t, m);
  const size = words.length <= 3 ? 150 : words.length <= 5 ? 118 : 96;
  return (
    <AbsoluteFill style={{opacity: out, justifyContent: 'flex-start', alignItems: 'center', top: '22%'}}>
      <div
        style={{
          position: 'absolute',
          inset: '-6% 0',
          background: 'linear-gradient(180deg, transparent, rgba(0,0,0,0.62) 30%, rgba(0,0,0,0.62) 70%, transparent)',
        }}
      />
      <div style={{position: 'relative', maxWidth: '90%', textAlign: 'center'}}>
        {words.map((w, i) => {
          const last = i === words.length - 1;
          const s = spring({frame: f - i * 4, fps, config: {damping: 10, stiffness: 220}});
          return (
            <span
              key={i}
              style={{
                display: 'inline-block',
                margin: '0 14px',
                fontFamily: last ? getFont('PlayfairDisplay') : font,
                fontStyle: last ? 'italic' : 'normal',
                fontWeight: last ? 900 : heavyWeight(style.font),
                fontSize: last ? size * 1.08 : size,
                lineHeight: 1.08,
                color: last ? style.highlightColor : '#fff',
                textTransform: last ? 'none' : 'uppercase',
                opacity: Math.min(1, s * 1.5),
                transform: `scale(${1.9 - 0.9 * s}) rotate(${(1 - s) * (i % 2 ? 6 : -6)}deg)`,
                textShadow: '0 8px 30px rgba(0,0,0,0.6)',
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Lower: React.FC<{m: Moment; style: CaptionStyle}> = ({m, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const f = frame - Math.round(m.t * fps);
  const [title, sub = ''] = m.text.split('|');
  const slide = spring({frame: f, fps, config: {damping: 15, stiffness: 120}});
  const exit = interpolate(t, [m.t + m.duration - 0.3, m.t + m.duration], [0, 1], clamp);
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', top: '6.5%'}}>
      <div style={{transform: `translateX(${(1 - slide) * -700 - exit * 700}px)`, display: 'inline-flex', flexDirection: 'column'}}>
        <div
          style={{
            alignSelf: 'flex-start',
            background: style.highlightColor,
            color: '#000',
            fontFamily: getFont('Oswald'),
            fontWeight: 700,
            fontSize: 54,
            letterSpacing: 2,
            padding: '8px 40px 8px 48px',
            textTransform: 'uppercase',
            borderTopRightRadius: 14,
          }}
        >
          {title}
        </div>
        {sub && (
          <div
            style={{
              alignSelf: 'flex-start',
              background: 'rgba(8,8,14,0.82)',
              color: '#fff',
              fontFamily: getFont('Poppins'),
              fontWeight: 600,
              fontSize: 40,
              padding: '10px 40px 12px 48px',
              borderBottomRightRadius: 14,
            }}
          >
            {sub}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

const Burst: React.FC<{m: Moment}> = ({m}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const f = frame - Math.round(m.t * fps);
  const pop = spring({frame: f, fps, config: {damping: 8, stiffness: 200}});
  const out = fade(t, m);
  const p = interpolate(f, [0, fps * 0.9], [0, 1], clamp);
  return (
    <AbsoluteFill style={{opacity: out}}>
      {Array.from({length: 10}, (_, i) => {
        const a = (i / 10) * Math.PI * 2 + random(`ba${i}`) * 0.5;
        const r = (240 + random(`br${i}`) * 260) * (1 - Math.pow(1 - p, 3));
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: `calc(50% + ${Math.cos(a) * r}px)`,
              top: `calc(38% + ${Math.sin(a) * r}px)`,
              fontSize: 70 + random(`bs${i}`) * 50,
              transform: `translate(-50%,-50%) rotate(${p * 90 * (i % 2 ? 1 : -1)}deg) scale(${1 - p * 0.4})`,
              opacity: 1 - p * 0.6,
            }}
          >
            {m.text}
          </div>
        );
      })}
      <div style={{position: 'absolute', left: '50%', top: '38%', fontSize: 260, transform: `translate(-50%,-50%) scale(${pop})`}}>
        {m.text}
      </div>
    </AbsoluteFill>
  );
};

export const MotionGraphics: React.FC<{moments: Moment[]; style: CaptionStyle; font: string}> = ({moments, style, font}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const active = moments.filter((m) => m.text && t >= m.t && t < m.t + m.duration);
  return (
    <>
      {active.map((m, i) => {
        if (m.effect === 'stat') return <Stat key={i} m={m} style={style} />;
        if (m.effect === 'kinetic') return <Kinetic key={i} m={m} style={style} font={font} />;
        if (m.effect === 'lower') return <Lower key={i} m={m} style={style} />;
        if (m.effect === 'burst') return <Burst key={i} m={m} />;
        return null;
      })}
    </>
  );
};
