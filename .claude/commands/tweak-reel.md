---
description: Change one reel (hook, timing, effects, caption style) and re-render only that clip
argument-hint: <clip-id> <what to change> [job-folder]
---

Tweak request: $ARGUMENTS

Use the most recent job in `jobs/` unless one is named. Open its `clips.json`, apply the change to that clip
(check the transcript for exact word times when moving start/end or moments), then run
`./reels validate <job>` and re-render only that clip:
- timing (start/end) changed → `./reels produce <job> --only <id> --force`
- anything else → `./reels produce <job> --only <id> --rerender`

For job-wide style changes (colors, font, music, brand handle), edit `jobs/<job>/config.yaml` instead.
View the new `output/<id>_*.jpg` cover frame and summarize what changed.
