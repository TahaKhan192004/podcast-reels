import {Config} from '@remotion/cli/config';

// Used by `npm run studio`. Final renders go through render.mjs.
Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
