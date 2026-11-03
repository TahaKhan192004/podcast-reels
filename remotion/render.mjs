// Renders every reel in a manifest written by pipeline/render.py.
// Bundles the Remotion project ONCE, then renders clip after clip (much faster than `npx remotion render` per clip).
//
//   node render.mjs <manifest.json>
//   manifest: {publicDir, concurrency, crf, renders: [{id, props, out}]}
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const manifestPath = process.argv[2];
if (!manifestPath) {
  console.error('usage: node render.mjs <manifest.json>');
  process.exit(1);
}
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

console.log('▸ Bundling Remotion project …');
const serveUrl = await bundle({
  entryPoint: path.join(here, 'src', 'index.ts'),
  publicDir: manifest.publicDir,
});

let n = 0;
for (const r of manifest.renders) {
  n++;
  const composition = await selectComposition({
    serveUrl, id: 'Reel', inputProps: r.props, browserExecutable: process.env.REMOTION_BROWSER || null,
    timeoutInMilliseconds: manifest.timeoutMs ?? 180000,
  });
  let last = -1;
  await renderMedia({
    composition,
    serveUrl,
    codec: 'h264',
    crf: manifest.crf ?? 18,
    x264Preset: manifest.x264Preset ?? 'medium',
    pixelFormat: 'yuv420p',
    audioCodec: 'aac',
    audioBitrate: '192k',
    outputLocation: r.out,
    inputProps: r.props,
    concurrency: manifest.concurrency ?? null,
    timeoutInMilliseconds: manifest.timeoutMs ?? 180000, // default is 30 s, too short on slow Windows laptops
    browserExecutable: process.env.REMOTION_BROWSER || null, // optional: use an existing Chrome/Chromium
    onProgress: ({progress}) => {
      const pct = Math.floor(progress * 100);
      if (pct >= last + 10) {
        last = pct;
        console.log(`   [${r.id}] ${n}/${manifest.renders.length}  ${pct}%`);
      }
    },
  });
  console.log(`✔ ${r.out}`);
}
