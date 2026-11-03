// Shape of props.json written by pipeline/render.py (build_props). Keep the two in sync.

export type CaptionWord = {text: string; s: number; e: number; emph: boolean};
export type CaptionPage = {start: number; end: number; words: CaptionWord[]};
export type Preset = 'hormozi' | 'karaoke' | 'boxed' | 'minimal';
export type FontName = 'Montserrat' | 'Anton' | 'BebasNeue' | 'Inter' | 'Poppins' | 'Oswald' | 'PlayfairDisplay';
export type Effect =
  | 'punch' | 'shake' | 'flash' | 'text' | 'zoom_out' | 'glitch'
  | 'stat' | 'kinetic' | 'lower' | 'burst';

export type Moment = {t: number; effect: Effect; text: string; duration: number};
export type ZoomBeat = {t: number; scale: number};

export type CaptionStyle = {
  position: number; // 0 top … 1 bottom
  highlightColor: string;
  secondaryColor: string;
  font: FontName;
  uppercase: boolean;
};

export type FaceBand = [number, number]; // [top, bottom] of the main face, fractions of frame height

export type ReelProps = {
  faceBand?: FaceBand | null; // used to keep pop-up graphics off the speaker's face
  videoFile: string; // file inside the render public dir; '' = preview background
  durationSec: number;
  fps: number;
  width: number;
  height: number;
  preset: Preset;
  pages: CaptionPage[];
  captionStyle: CaptionStyle;
  hook: string;
  moments: Moment[];
  zoomBeats: ZoomBeat[];
  effects: {autoZoom: boolean; grain: boolean; vignette: boolean; progressBar: boolean};
  brandHandle: string;
  endCard: string;
  music: {file: string; volume: number} | null;
};
