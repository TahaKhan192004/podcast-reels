# Podcast → Reels — instructions for Claude Code

This project turns a long YouTube video (usually a podcast) into finished vertical reels.
**Scripts do the mechanical work; you (Claude) do the editorial work**: choosing the clips, writing hooks,
picking keywords and placing motion-graphic moments.

```
./reels prepare <url>  →  YOU write jobs/<job>/clips.json  →  ./reels produce <job>
(yt-dlp + Whisper)        (editorial decisions)               (ffmpeg cut → face-track 9:16 → Remotion)
```

Always run the pipeline through `./reels …` (it uses the project's `.venv`). Never `pip install` into the
system Python. If something is missing, run `./reels doctor` and follow its hints.

## Commands

| Command | What it does |
|---|---|
| `./reels prepare "<url or video file>"` | download + transcribe → prints `JOB_DIR=…` |
| `./reels validate [job]` | checks `clips.json`, snaps cuts to word boundaries, prints a table + warnings |
| `./reels produce [job]` | cut → reframe → render every clip |
| `./reels produce [job] --only 02,05 --rerender` | re-render only some clips (keeps cuts/reframes) |
| `./reels produce [job] --preset boxed --engine ffmpeg --mode blur` | per-run overrides |
| `./reels status [job]` · `./reels doctor` | progress · installation check |

`[job]` is the folder name inside `jobs/`; omit it to use the most recent job.
Transcription of a 1–2 h podcast can take a long time on CPU; run `prepare` with a generous Bash timeout
(10 min max) and, if it is still running, run it in the background and poll `./reels status`.

## Job folder layout

```
jobs/<job>/
  source.mp4  info.json  audio.wav  transcript.json
  transcript/part_01.txt …     ← READ THESE to choose clips ([HH:MM:SS.s → HH:MM:SS.s] text)
  clips.json                   ← YOU WRITE THIS
  config.yaml                  ← optional per-job overrides of ../../config.yaml
  clips/<id>/                  ← intermediate files (raw.mp4, vertical.mp4, props.json, track.json)
  output/NN_title.mp4 .txt .jpg  ← final reel, post caption, cover frame
```

## How to choose clips (the important part)

1. Read `info.json` (title, channel, description, chapters) to understand who is talking and about what.
2. Read **every** `transcript/part_XX.txt` in order. For long episodes, keep running candidate notes in
   `jobs/<job>/notes.md` as you go so nothing is forgotten.
3. Shortlist ~2× the target count, then keep the best (default `clips.target_count` in config.yaml, or
   what the user asked for). Prefer quality over quantity: never pad with weak clips.

**A great reel clip:**
- **Hooks in the first 3 seconds.** Its first sentence is a bold claim, a contrarian take, a surprising number,
  a direct question, or the start of a story with tension. Start *exactly* on that sentence.
- **Stands alone.** No "like I said", "that thing", "he" without context at the start. A stranger scrolling must get it.
- **One idea, with a payoff.** Ends right after the punchline, conclusion, or emotional peak, not mid-thought.
- **Has energy:** emotion, laughter, conflict, vulnerability, a specific story, concrete numbers, a quotable line.
- **Length:** `clips.min_seconds`–`clips.max_seconds` (default 20–75 s); 30–60 s is the sweet spot.

**Avoid:** sponsor reads and ads, intros and outros, "subscribe" segments, inside jokes, moments that depend on something
shown on screen, crosstalk-heavy parts, and clips that overlap each other.

Clips must be one continuous range (no internal jump cuts). If the best moment has a slow middle,
choose a tighter range rather than including filler.

## clips.json schema

Times are **absolute times in the source video**, copied from the transcript (`"00:12:03.4"` or seconds).
Template: `templates/clips.example.json`.

```json
{
  "clips": [
    {
      "title": "Why most startups die in year two",
      "start": "00:41:12.3",
      "end": "00:42:05.8",
      "score": 9,
      "reason": "Contrarian claim + concrete story + clear lesson at the end",
      "hook": "Most startups die here",
      "caption_preset": "hormozi",
      "keywords": ["cash", "year two", "runway"],
      "moments": [
        {"t": "00:41:15.0", "effect": "text", "text": "💸 CASH IS KING", "duration": 1.5},
        {"t": "00:41:31.2", "effect": "punch"},
        {"t": "00:41:48.9", "effect": "shake", "duration": 0.5}
      ],
      "post_caption": "Revenue is vanity, cash is sanity. Here's the mistake that kills most startups 👇",
      "hashtags": ["#startups", "#entrepreneur", "#podcast", "#business"]
    }
  ]
}
```

Field guide:
- **hook**: on-screen title for the first ~3 s. Max 7 words. Create curiosity; don't just repeat the
  first spoken line. The last word is highlighted, so end on the strongest word.
- **score**: 1–10 virality estimate; only keep ≥ 7. Order clips best-first.
- **caption_preset**: `hormozi` (big 3-word pop captions; high-energy business/motivation),
  `boxed` (TikTok-style word boxes; fun, punchy), `karaoke` (full line fills as spoken; storytelling),
  `minimal` (clean subtitles; serious or emotional). Omit to use the config default.
- **keywords**: 2–6 words *actually spoken in the clip*. They are colored differently in captions, and if
  there are no punch/shake moments the camera auto-punches on them.
- **moments**: 2–5 per clip, at least ~4 s apart, timed to the exact word from the transcript:
  - `punch`: quick zoom-in on a punchline or key word
  - `text`: big pop-up callout. Put a ≤4-word `text`, usually with one emoji ("🚫 NOT TALENT", "$10M"); the best uses are numbers, names and key concepts
  - `shake`: camera shake for a shocking or emphatic statement
  - `flash`: white flash for a turn in the story or a "but then…"
  - `zoom_out`: starts tight and pulls back for a reveal
  - `glitch`: use rarely; for something absurd or "wait, what?"
  - optional `duration` in seconds (defaults to 1.2)
- **post_caption / hashtags**: written to `output/NN_title.txt` for posting.

## After writing clips.json

1. `./reels validate <job>`. Fix every warning (bad times, durations outside range, overlaps) and re-run.
2. `./reels produce <job>`.
3. **QA:** look at the cover frames `output/*.jpg` with the Read tool (they're images). Check the speaker is
   framed and the captions are readable. If framing is wrong on a clip, re-run just that clip with
   `--mode blur` or tune `reframe:` in the job's `config.yaml`.
4. Report a table to the user: file, duration, score, hook, why it should perform.

## Tweaking a single reel

Edit that clip's entry in `clips.json` (hook, moments, preset, keywords), then
`./reels produce <job> --only <id> --rerender`. If you changed `start`/`end`, use `--force` instead, because the cut must be redone.
Style tweaks that apply to every clip of a job go in `jobs/<job>/config.yaml`; only the keys you change are needed, e.g.:

```yaml
captions: {preset: karaoke, highlight_color: "#00FF88", font: Anton}
render: {brand_handle: "@mypodcast", end_card: "Follow for part 2 👀", music: {enabled: true}}
```

## Code map (for extending the system)

| Want to… | Edit |
|---|---|
| change defaults | `config.yaml` |
| add a caption preset | `remotion/src/captions/<Name>.tsx` + register in `captions/Captions.tsx`; add to `PRESETS` in `pipeline/clips.py`, `PRESET_LAYOUT` + an ASS style in `pipeline/captions.py`, the `Preset` type in `remotion/src/types.ts` and `--preset` choices in `pipeline/__main__.py` |
| add a camera effect | `remotion/src/effects/Camera.tsx` (zoom/shake) or `Flash.tsx` (overlays); add the name to `EFFECTS` in `pipeline/clips.py` and `Effect` in `types.ts` |
| add an overlay (logo, subscribe button…) | new component in `remotion/src/effects/`, mount it in `remotion/src/Reel.tsx`, add a prop in `types.ts` + `build_props()` in `pipeline/render.py` |
| change face tracking | `pipeline/reframe.py` (`_choose_targets` = who to frame, camera smoothing in `analyse_faces`) |
| change Whisper behaviour | `pipeline/transcribe.py` |

Preview the Remotion design live with `cd remotion && npm run studio` (it uses demo props from `src/sample.ts`).
After changing TypeScript, run `cd remotion && npx tsc --noEmit`.
