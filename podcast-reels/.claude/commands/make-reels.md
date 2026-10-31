---
description: Turn a YouTube podcast link into finished vertical reels (download → transcribe → pick clips → render)
argument-hint: <youtube-url | video-file> [number of reels] [extra instructions]
---

Make reels from: $ARGUMENTS

Follow CLAUDE.md. Steps:

1. Run `./reels doctor`. If anything is ✖, stop and tell me how to fix it.
2. Run `./reels prepare "<url or file>"` (use a 10-minute Bash timeout; if transcription runs longer,
   run it in the background and poll `./reels status`). Note the printed `JOB_DIR`.
3. Read `JOB_DIR/info.json`, then read **every** `JOB_DIR/transcript/part_*.txt` in order, keeping candidate
   notes in `JOB_DIR/notes.md` for long episodes.
4. Choose the clips using the "How to choose clips" rules in CLAUDE.md. Use the number of reels I asked for,
   or `clips.target_count` from config.yaml. Respect any extra instructions I gave (topic focus, style, length).
5. Write `JOB_DIR/clips.json` with hooks, keywords, moments, caption presets, post captions and hashtags.
6. Run `./reels validate <job>` and fix every warning.
7. Run `./reels produce <job>` (rendering takes a while; use a long timeout or the background).
8. QA: view each `output/*.jpg` cover frame. Re-run any badly framed clip with `--only <id> --force --mode blur`.
9. Finish with a table: file · duration · score · hook · why it should perform, plus the output folder path.
