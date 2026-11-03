"""Step 7: final render.

engine=remotion → captions + motion graphics + effects (remotion/render.mjs, one bundle for all clips)
engine=ffmpeg   → burned-in .ass captions only (fast fallback, no Node needed)

Final files land in  jobs/<job>/output/  as  NN_title.mp4 + NN_title.txt (post caption) + NN_title.jpg (cover)
"""
from __future__ import annotations

import os
import random
import shutil
import subprocess
from pathlib import Path

from .captions import build_pages, write_ass, zoom_beats
from .common import (ASSETS_DIR, REMOTION_DIR, clip_dir, die, load_config, log, read_json, require_bin, run,
                     warn, write_json)


def build_props(job: Path, spec: dict, cfg: dict, video_file: str, music_file: str | None) -> dict:
    ccfg, rcfg = cfg["captions"], cfg["render"]
    pages = build_pages(spec["words"], spec["caption_preset"], spec["keywords"], ccfg)
    moments = list(spec["moments"])
    if rcfg["auto_zoom"] and not any(m["effect"] in ("punch", "shake") for m in moments):
        # no moments from Claude → punch on emphasised keywords, at most one every 4 s
        last = -10.0
        for pg in pages:
            for w in pg["words"]:
                if w["emph"] and w["s"] - last > 4:
                    moments.append({"t": w["s"], "effect": "punch", "text": "", "duration": 0.9})
                    last = w["s"]
    face_band = None
    try:  # written by reframe.py in face mode; absent for blur/center
        face_band = read_json(clip_dir(job, spec["id"]) / "track.json").get("face_band")
    except (OSError, ValueError):
        pass
    return {
        "faceBand": face_band,
        "videoFile": video_file,
        "durationSec": spec["duration"],
        "fps": rcfg["fps"],
        "width": cfg["reframe"]["width"],
        "height": cfg["reframe"]["height"],
        "preset": spec["caption_preset"],
        "pages": pages,
        "captionStyle": {
            "position": ccfg["position"],
            "highlightColor": ccfg["highlight_color"],
            "secondaryColor": ccfg["secondary_color"],
            "font": ccfg["font"],
            "uppercase": bool(ccfg["uppercase"]),
        },
        "hook": spec["hook"] if rcfg["hook_title"] else "",
        "moments": sorted(moments, key=lambda m: m["t"]),
        "zoomBeats": zoom_beats(spec["words"], spec["duration"]) if rcfg["auto_zoom"] else [],
        "effects": {
            "autoZoom": bool(rcfg["auto_zoom"]),
            "grain": bool(rcfg["grain"]),
            "vignette": bool(rcfg["vignette"]),
            "progressBar": bool(rcfg["progress_bar"]),
        },
        "brandHandle": rcfg.get("brand_handle") or "",
        "endCard": rcfg.get("end_card") or "",
        "music": {"file": music_file, "volume": rcfg["music"]["volume"]} if music_file else None,
    }


def render_all(job: Path, specs: list[dict], force: bool = False) -> list[Path]:
    cfg = load_config(job)
    out_dir = job / "output"
    out_dir.mkdir(exist_ok=True)
    todo = [s for s in specs if force or not (out_dir / f"{s['slug']}.mp4").exists()]
    for s in specs:
        _write_post_text(out_dir, s)
    if not todo:
        log("All clips already rendered (use --force to re-render).")
        return [out_dir / f"{s['slug']}.mp4" for s in specs]

    engine = cfg["render"]["engine"]
    if engine == "remotion" and not (REMOTION_DIR / "node_modules").exists():
        warn("remotion/node_modules missing (run setup) → falling back to ffmpeg engine.")
        engine = "ffmpeg"

    if engine == "remotion":
        _render_remotion(job, todo, cfg, out_dir)
    else:
        for s in todo:
            _render_ffmpeg(job, s, cfg, out_dir)

    for s in specs:
        mp4 = out_dir / f"{s['slug']}.mp4"
        if mp4.exists():
            run([require_bin("ffmpeg"), "-y", "-ss", "1.2", "-i", str(mp4), "-frames:v", "1", "-q:v", "3",
                 str(out_dir / f"{s['slug']}.jpg")])
    return [out_dir / f"{s['slug']}.mp4" for s in specs]


def _render_remotion(job: Path, specs: list[dict], cfg: dict, out_dir: Path) -> None:
    public = job / ".render_public"
    public.mkdir(exist_ok=True)
    music_tracks = sorted(p for p in (ASSETS_DIR / "music").glob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a"})
    use_music = cfg["render"]["music"]["enabled"] and music_tracks
    if cfg["render"]["music"]["enabled"] and not music_tracks:
        warn("music.enabled is true but assets/music/ is empty.")

    renders = []
    for s in specs:
        src = clip_dir(job, s["id"]) / "vertical.mp4"
        _link(src, public / f"{s['id']}.mp4")
        music = None
        if use_music:
            track = random.choice(music_tracks)
            music = f"music_{track.name}"
            _link(track, public / music)
        props = build_props(job, s, cfg, f"{s['id']}.mp4", music)
        write_json(clip_dir(job, s["id"]) / "props.json", props)
        renders.append({"id": s["id"], "props": props, "out": str(out_dir / f"{s['slug']}.mp4")})

    manifest = job / ".render_manifest.json"
    write_json(manifest, {"publicDir": str(public), "concurrency": cfg["render"]["concurrency"] or None,
                          "timeoutMs": int(cfg["render"].get("timeout_seconds", 180)) * 1000,
                          "crf": cfg["encode"]["crf"], "x264Preset": cfg["encode"]["preset"],
                          "renders": renders})
    log(f"Rendering {len(renders)} reel(s) with Remotion …")
    node = require_bin("node")
    res = subprocess.run([node, "render.mjs", str(manifest)], cwd=REMOTION_DIR)
    if res.returncode != 0:
        die("Remotion render failed (see output above).")


def _render_ffmpeg(job: Path, spec: dict, cfg: dict, out_dir: Path) -> None:
    d = clip_dir(job, spec["id"])
    pages = build_pages(spec["words"], spec["caption_preset"], spec["keywords"], cfg["captions"])
    ass = write_ass(pages, spec["caption_preset"], cfg["captions"], d / "captions.ass",
                    cfg["reframe"]["width"], cfg["reframe"]["height"])
    log(f"[{spec['id']}] burning captions (ffmpeg engine) …")
    # run from the clip folder so the filter path has no drive letters/colons to escape (Windows-safe)
    fonts = os.path.relpath(ASSETS_DIR / "fonts", d).replace("\\", "/")
    enc = cfg["encode"]
    cmd = [require_bin("ffmpeg"), "-y", "-i", "vertical.mp4",
           "-vf", f"subtitles={ass.name}:fontsdir={fonts}",
           "-c:v", "libx264", "-crf", str(enc["crf"]), "-preset", enc["preset"], "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart", str((out_dir / f"{spec['slug']}.mp4").resolve())]
    res = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
    if res.returncode != 0:
        die(f"ffmpeg caption burn failed:\n{res.stderr[-2000:]}")


def _write_post_text(out_dir: Path, s: dict) -> None:
    tags = " ".join(s.get("hashtags") or [])
    body = f"{s['title']}\n\n{s.get('post_caption', '')}\n\n{tags}\n".strip() + "\n"
    (out_dir / f"{s['slug']}.txt").write_text(body, encoding="utf-8")


def _link(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
