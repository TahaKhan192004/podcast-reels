# 🎙️ Podcast → Reels

Drop in a YouTube link to a long podcast and get back a folder of finished **9:16 reels**: face-tracked,
captioned and with motion graphics. Everything runs **locally** with Claude Code.

```
 YouTube URL
     │  yt-dlp                         pipeline/download.py
     ▼
 source.mp4 ──► Whisper (local)        pipeline/transcribe.py   auto: mlx (Mac) · CUDA · CPU
     │            word-level timestamps
     ▼
 transcript/part_XX.txt ──► Claude Code picks the viral moments    (CLAUDE.md playbook)
     │                      writes clips.json: times, hook, keywords, effects, caption, hashtags
     ▼
 ffmpeg frame-accurate cut + loudness -14 LUFS                     pipeline/cut.py
     ▼
 Face tracking + active-speaker detection → 9:16 crop              pipeline/reframe.py
     ▼
 Remotion: animated captions · hook title · punch zooms · shakes ·  remotion/
           flashes · pop-up callouts · grain · vignette · progress bar · end card · music
     ▼
 jobs/<video>/output/01_title.mp4  + .txt (post caption) + .jpg (cover)
```

---

## 1. Setup (once)

**You need:** Python 3.10+, Node.js 18+, ffmpeg, Deno and [Claude Code](https://claude.com/claude-code).
The setup scripts install whatever is missing and verify everything.

**macOS / Linux**
```bash
./setup.sh
```

**Windows 10/11** (PowerShell, from the project folder, the one that contains `setup.ps1`)
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```
It installs Git, ffmpeg, Node.js, Python and Deno (YouTube downloads need it) with `winget` if they're missing. If it says a tool "is not on PATH yet",
close PowerShell, open a new one, and run the same command again.

When `./reels doctor` prints **All good ✔** you're ready. The script picks the Whisper backend automatically:

| Machine | Backend | Default model | Speed (1 h podcast, rough) |
|---|---|---|---|
| Mac Apple Silicon (M1–M4) | mlx-whisper (Metal) | large-v3-turbo | ~4–8 min |
| Windows/Linux + NVIDIA GPU | faster-whisper CUDA fp16 | large-v3-turbo | ~2–5 min |
| Any CPU | faster-whisper int8 | small | ~15–40 min |

Override with `transcribe.model` in `config.yaml` (e.g. `medium` on a fast CPU for better accuracy).
Whisper models download automatically the first time (`small` ≈ 0.5 GB, `large-v3-turbo` ≈ 1.6 GB).

*Optional:* to stop Claude Code asking permission for every pipeline command, copy
`templates/claude-settings.example.json` to `.claude/settings.json`.

---

## 2. Use it with Claude Code

Open the folder in Claude Code and run:

```
/make-reels https://www.youtube.com/watch?v=XXXXXXXX
/make-reels https://youtu.be/XXXXXXXX 5 focus on the money advice, use karaoke captions
/make-reels ~/Videos/episode42.mp4 10
```

Claude downloads and transcribes the video, reads the whole transcript, picks the best moments, writes the hooks and
effects, renders everything, checks the cover frames and reports a table of results.

Other commands:

| Command | Use |
|---|---|
| `/pick-clips [job] [instructions]` | redo only the clip selection (e.g. "6 clips, only about relationships") |
| `/tweak-reel 03 make the hook punchier and add a shake at "I was broke"` | change and re-render one reel |

Or just talk to it: *"re-render clip 2 with boxed captions"*, *"make all reels for this job use green highlights"*.

---

## 3. Use the dashboard (no terminal needed)

```bash
./reels dashboard          # Windows: dashboard.cmd
```
Opens **http://127.0.0.1:8765** in your browser. Paste a YouTube link, pick how many reels you want, press **Make reels**.

1. Download and transcription run locally: **no Claude tokens**.
2. Claude Code is called **once** (headless `claude -p`, thinking off) to choose the clips and plan the motion graphics. The token count and cost are shown live in the page.
3. Cutting, face tracking and rendering run locally again, and finished reels appear as playable cards with their post caption, a download button and a copy-caption button.

It needs Claude Code installed and logged in. The server only listens on your own computer (`127.0.0.1`) and rejects requests from other origins.
Options: `./reels dashboard --port 9000`, `--no-open`. Dashboard runs are stored in `.dashboard/`; reels made from the CLI show up in the project list too.

---

## 4. Run it by hand (no Claude needed for the mechanical steps)

```bash
./reels prepare "https://youtu.be/XXXXXXXX"      # download + transcribe → jobs/<job>/
# write jobs/<job>/clips.json yourself (see templates/clips.example.json)
./reels validate                                  # checks + snaps cuts to word boundaries
./reels produce                                   # renders every clip
./reels produce --only 02,05 --rerender           # re-render a few
./reels produce --preset karaoke --engine ffmpeg  # per-run overrides
./reels status | ./reels doctor | ./reels --help
```
(On Windows cmd/PowerShell use `reels` instead of `./reels`; inside Claude Code `./reels` works everywhere.)

Every step is cached: re-running `produce` skips finished cuts and reframes, so experimenting with styles is fast.

---

## 5. Customize

All defaults live in **`config.yaml`** (fully commented). To change a single video, put a `config.yaml`
inside `jobs/<job>/` that contains only the keys you want to change:

```yaml
captions: {preset: boxed, highlight_color: "#00FF88", font: Anton}
render:
  brand_handle: "@mypodcast"
  end_card: "Follow for part 2 👀"
  music: {enabled: true, volume: 0.06}   # random track from assets/music/
reframe: {mode: blur}                     # face | blur | center
```

**Caption presets:** `hormozi` (big pop words) · `boxed` (TikTok word boxes) · `karaoke` (line fill) · `minimal` (clean subtitles)
**Fonts:** Montserrat · Anton · BebasNeue · Inter · Poppins · Oswald · Playfair Display (bundled, so no internet is needed at render time)
**Effects Claude can place:** `punch` · `text` (pop-up callout) · `shake` · `flash` · `zoom_out` · `glitch`, plus motion-graphic cards:
`stat` (counting number card) · `kinetic` (slam-in headline) · `lower` (name tag / lower third) · `burst` (emoji pop).
Text graphics are placed automatically away from the speaker's face.
**Always-on polish (toggle in config):** hook title, jump-cut zoom beats, slow push-in, film grain, vignette, progress bar

Preview and design the motion graphics live: `cd remotion && npm run studio`.

Background music: drop royalty-free `.mp3` files in `assets/music/` and set `render.music.enabled: true`.

---

## 6. Folder structure

```
podcast-reels/
├── CLAUDE.md               ← Claude's playbook (clip selection rules, schema, workflow)
├── .claude/commands/       ← /make-reels  /pick-clips  /tweak-reel
├── config.yaml             ← all settings
├── reels, reels.cmd        ← CLI wrappers (use the project .venv)
├── dashboard/, dashboard.cmd  ← local web UI (`./reels dashboard`)
├── setup.sh, setup.ps1
├── requirements.txt
├── pipeline/               ← Python: download · transcribe · clips · cut · reframe · captions · render
├── remotion/               ← React/Remotion: Reel.tsx, captions/ (4 presets), effects/ (camera, flash, hook, MotionGraphics …)
├── templates/              ← clips.example.json, claude-settings.example.json
├── assets/music/  assets/fonts/  models/
└── jobs/<video>/           ← one folder per video (source, transcript, clips.json, output/)
```

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| YouTube says *"Sign in to confirm you're not a bot"* | set `download.cookies_from_browser: chrome` (or firefox/edge/safari) in config.yaml |
| YouTube download fails / warns about a JavaScript runtime | install Deno (`winget install DenoLand.Deno` · `brew install deno`) and reopen the terminal; `./reels doctor` checks for it |
| yt-dlp fails to download | update it: `.venv/bin/pip install -U yt-dlp` (Windows: `.venv\Scripts\pip install -U yt-dlp`) |
| Transcription is slow | normal on CPU; set `transcribe.model: base` for drafts, or use a GPU/Mac |
| CUDA errors (`cublas64_12.dll`, `libcudnn`) | rerun setup (installs `nvidia-cublas-cu12` + `nvidia-cudnn-cu12`) or set `transcribe.backend: faster-whisper` with `model: small` to use the CPU |
| Wrong person framed | the camera follows whoever's mouth moves most; for tricky shots use `--mode blur` on that clip |
| Remotion render fails / no Node | `./reels produce --engine ffmpeg` (captions only, no motion graphics) |
| Render stalls or times out (esp. Windows laptops) | `render.concurrency` defaults to 2; raise `render.timeout_seconds` if frames are slow. Too many parallel tabs (8+) is what stalls it |
| Renders are slow | on a strong machine raise `render.concurrency` (try 4) and set `encode.preset: veryfast` |
| Need to start over on a clip | `./reels produce --only 03 --force` |

Only use this on content you have the rights to repurpose (your own podcast, or with the creator's permission).
