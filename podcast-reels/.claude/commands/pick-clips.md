---
description: (Re)choose clips for an already transcribed job and write clips.json, without rendering
argument-hint: [job-folder] [instructions, e.g. "5 clips about money, karaoke captions"]
---

Pick clips for: $ARGUMENTS

If no job folder is given, use the most recent folder in `jobs/`. Follow "How to choose clips" in CLAUDE.md:
read info.json and every transcript part, then write `clips.json` (back up an existing one to
`clips.prev.json` first). Run `./reels validate <job>`, fix the warnings, then show me the clip table and
ask whether to render it with `./reels produce <job>`.
