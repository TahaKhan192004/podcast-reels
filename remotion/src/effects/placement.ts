// Keeps pop-up graphics off the speaker's face.
// `band` = [top, bottom] of the main face as fractions of the frame height (from pipeline/reframe.py), or null.
// Returns the top edge (fraction of frame height) for a graphic `h` tall: the preferred spot if it is clear
// of the face, otherwise the first free alternative, otherwise whichever overlaps the face least.
const MARGIN = 0.04; // face boxes from the detector cover eyes→chin, not forehead/hair
const CAPTION_TOP = 0.62; // captions start around here (default caption position 0.70), so graphics must end above it

export const placeTop = (band: [number, number] | null | undefined, preferred: number, h: number): number => {
  if (!band) return preferred;
  const lo = band[0] - MARGIN * 1.5;
  const hi = band[1] + MARGIN;
  const overlap = (top: number) => Math.max(0, Math.min(top + h, hi) - Math.max(top, lo));
  // alternatives: just above the captions, then the top strip, then the upper-middle
  const options = [preferred, CAPTION_TOP - h, 0.05, 0.3].filter((t, i, a) => t >= 0 && a.indexOf(t) === i);
  let best = preferred;
  let bestOverlap = Infinity;
  for (const top of options) {
    if (top + h > CAPTION_TOP + 0.02 && top !== preferred) continue; // would sit on the captions
    const o = overlap(top);
    if (o === 0) return top;
    if (o < bestOverlap) {
      best = top;
      bestOverlap = o;
    }
  }
  return best;
};
