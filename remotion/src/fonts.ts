// Fonts are bundled from npm (@fontsource) so rendering works fully offline.
import antonW400 from '@fontsource/anton/files/anton-latin-400-normal.woff2';
import bebasW400 from '@fontsource/bebas-neue/files/bebas-neue-latin-400-normal.woff2';
import interW600 from '@fontsource/inter/files/inter-latin-600-normal.woff2';
import interW800 from '@fontsource/inter/files/inter-latin-800-normal.woff2';
import interW900 from '@fontsource/inter/files/inter-latin-900-normal.woff2';
import montW600 from '@fontsource/montserrat/files/montserrat-latin-600-normal.woff2';
import montW800 from '@fontsource/montserrat/files/montserrat-latin-800-normal.woff2';
import montW900 from '@fontsource/montserrat/files/montserrat-latin-900-normal.woff2';
import popW600 from '@fontsource/poppins/files/poppins-latin-600-normal.woff2';
import popW800 from '@fontsource/poppins/files/poppins-latin-800-normal.woff2';
import popW900 from '@fontsource/poppins/files/poppins-latin-900-normal.woff2';
import oswW600 from '@fontsource/oswald/files/oswald-latin-600-normal.woff2';
import oswW700 from '@fontsource/oswald/files/oswald-latin-700-normal.woff2';
import pfW900 from '@fontsource/playfair-display/files/playfair-display-latin-900-normal.woff2';
import pfW900i from '@fontsource/playfair-display/files/playfair-display-latin-900-italic.woff2';
import {loadFont} from '@remotion/fonts';
import type {FontName} from './types';

const FILES: Record<FontName, {family: string; weights: Record<string, string>; italic?: Record<string, string>}> = {
  Oswald: {family: 'Oswald', weights: {'600': oswW600, '700': oswW700}},
  PlayfairDisplay: {family: 'Playfair Display', weights: {'900': pfW900}, italic: {'900': pfW900i}},
  Montserrat: {family: 'Montserrat', weights: {'600': montW600, '800': montW800, '900': montW900}},
  Inter: {family: 'Inter', weights: {'600': interW600, '800': interW800, '900': interW900}},
  Poppins: {family: 'Poppins', weights: {'600': popW600, '800': popW800, '900': popW900}},
  Anton: {family: 'Anton', weights: {'400': antonW400}},
  BebasNeue: {family: 'Bebas Neue', weights: {'400': bebasW400}},
};

const loaded = new Set<FontName>();

// Registers the font once (loadFont blocks rendering until the files are ready) and returns a CSS font stack.
export const getFont = (name: FontName): string => {
  const f = FILES[name] ?? FILES.Montserrat;
  if (!loaded.has(name)) {
    loaded.add(name);
    for (const [weight, url] of Object.entries(f.weights)) {
      loadFont({family: f.family, url, weight}).catch((e) => console.error(`font ${f.family} ${weight}:`, e));
    }
    for (const [weight, url] of Object.entries(f.italic ?? {})) {
      loadFont({family: f.family, url, weight, style: 'italic'}).catch((e) => console.error(`font ${f.family} italic:`, e));
    }
  }
  return `'${f.family}', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif`;
};

// Anton/Bebas are already ultra-bold at 400; the others need 900 for the punchy look.
export const heavyWeight = (name: FontName) =>
  name === 'Anton' || name === 'BebasNeue' ? 400 : name === 'Oswald' ? 700 : 900;
