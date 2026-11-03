// Demo props so `npm run studio` shows something without a real clip.
import type {CaptionPage, ReelProps} from './types';

const script =
  'Most people think success is about talent. It is not. It is about showing up every single day when nobody is watching.';

const words = script.split(' ').map((text, i) => ({
  text,
  s: 0.4 + i * 0.32,
  e: 0.4 + i * 0.32 + 0.28,
  emph: ['success', 'talent.', 'every', 'nobody'].includes(text.toLowerCase()),
}));

const pages: CaptionPage[] = [];
for (let i = 0; i < words.length; i += 3) {
  const w = words.slice(i, i + 3);
  pages.push({start: w[0].s, end: w[w.length - 1].e + 0.04, words: w});
}

export const sampleProps: ReelProps = {
  videoFile: '',
  durationSec: 9,
  fps: 30,
  width: 1080,
  height: 1920,
  preset: 'hormozi',
  pages,
  captionStyle: {position: 0.7, highlightColor: '#FFE600', secondaryColor: '#00E5FF', font: 'Montserrat', uppercase: true},
  hook: 'The real secret to success',
  moments: [
    {t: 2.0, effect: 'punch', text: '', duration: 1},
    {t: 3.3, effect: 'text', text: '🚫 NOT TALENT', duration: 1.4},
    {t: 5.6, effect: 'flash', text: '', duration: 0.4},
    {t: 7.0, effect: 'shake', text: '', duration: 0.5},
  ],
  zoomBeats: [{t: 0, scale: 1}, {t: 4.2, scale: 1.12}],
  effects: {autoZoom: true, grain: true, vignette: true, progressBar: true},
  brandHandle: '@yourpodcast',
  endCard: 'Follow for more 🎙️',
  music: null,
};
