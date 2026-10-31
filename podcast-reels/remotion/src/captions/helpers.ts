import type {CaptionPage, CaptionStyle} from '../types';

export type PresetProps = {page: CaptionPage; t: number; frame: number; fps: number; style: CaptionStyle; font: string};

// Thick text outline that works on any font (layered shadows instead of -webkit-text-stroke).
export const outline = (px: number, color = '#000') => {
  const steps = 16;
  const parts = Array.from({length: steps}, (_, i) => {
    const a = (i / steps) * Math.PI * 2;
    return `${(Math.cos(a) * px).toFixed(1)}px ${(Math.sin(a) * px).toFixed(1)}px 0 ${color}`;
  });
  return [...parts, `0 ${px + 4}px ${px * 2}px rgba(0,0,0,0.6)`].join(', ');
};

// Index of the word currently being spoken (last word that has started).
export const activeIndex = (page: CaptionPage, t: number) => {
  let idx = -1;
  page.words.forEach((w, i) => {
    if (t >= w.s) idx = i;
  });
  return idx;
};

export const fitFontSize = (page: CaptionPage, base: number, maxWidth = 940) => {
  const longest = Math.max(...page.words.map((w) => w.text.length), 1);
  return Math.min(base, maxWidth / (longest * 0.68));
};
