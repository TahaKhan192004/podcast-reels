"""Podcast → Reels command line.

  python -m pipeline prepare <youtube-url | video-file>   download + transcribe
  python -m pipeline validate [job]                         check Claude's clips.json
  python -m pipeline produce  [job] [--only 01,03]          cut → reframe → captions/effects → render
  python -m pipeline status   [job]
  python -m pipeline doctor                                 check that everything is installed
  python -m pipeline assets                                 download fonts + face model (setup runs this)
  python -m pipeline dashboard [--port 8765]                web UI: paste a link, get reels

[job] = folder name inside jobs/ (or a path). Omit it to use the most recent job.
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
import time

from . import common
from .common import REMOTION_DIR, fmt_ts, latest_job, log, read_json, resolve_job, warn


def cmd_prepare(a):
    from .download import download
    from .transcribe import transcribe
    job = download(a.source, force=a.force)
    transcribe(job, force=a.force)
    info = read_json(job / "info.json")
    parts = sorted((job / "transcript").glob("part_*.txt"))
    print(f"\nJOB_DIR={job}")
    print(f"TITLE={info.get('title')}")
    print(f"DURATION={fmt_ts(info.get('duration') or 0)}")
    print(f"TRANSCRIPT_PARTS={len(parts)}")
    print("NEXT: Claude reads transcript/part_*.txt and writes clips.json, then: python -m pipeline produce")


def cmd_validate(a):
    from .clips import validate
    validate(_job(a))


def cmd_produce(a):
    from .clips import validate
    from .cut import cut
    from .reframe import reframe
    from .render import render_all
    job = _job(a)
    specs = validate(job)
    if a.only:
        wanted = {x.strip().zfill(2) for x in a.only.split(",")}
        specs = [s for s in specs if s["id"] in wanted]
    if not specs:
        warn("Nothing to produce.")
        return
    t0 = time.time()
    for s in specs:
        cut(job, s, force=a.force)
        reframe(job, s, force=a.force)
    outs = render_all(job, specs, force=a.force or a.rerender)
    print()
    log(f"Done in {time.time() - t0:.0f}s. {len(outs)} reel(s):")
    for o in outs:
        print(f"   {o}")


def cmd_status(a):
    job = _job(a)
    info = read_json(job / "info.json") if (job / "info.json").exists() else {}
    print(f"Job:        {job.name}\nTitle:      {info.get('title', '?')}")
    for label, p in [("Video", "source.mp4"), ("Transcript", "transcript.json"), ("Clips", "clips.json")]:
        print(f"{label + ':':<12}{'✓' if (job / p).exists() else '—'}")
    outs = sorted((job / "output").glob("*.mp4")) if (job / "output").exists() else []
    print(f"Rendered:   {len(outs)}")
    for o in outs:
        print(f"   {o.name}")


def cmd_doctor(_a):
    ok = True

    def check(name, cond, hint=""):
        nonlocal ok
        print(f"  {'✓' if cond else '✖'} {name}" + ("" if cond else f"   → {hint}"))
        ok &= bool(cond)

    print("System")
    check("ffmpeg", shutil.which("ffmpeg"), "install ffmpeg (see README)")
    check("node", shutil.which("node"), "install Node.js 18+ (only needed for the Remotion engine)")
    if shutil.which("deno"):
        print("  ✓ deno (yt-dlp needs it for YouTube)")
    else:  # warning only: downloads still work today, but YouTube is phasing this requirement in
        print("  ! deno not found   → winget install DenoLand.Deno / brew install deno (YouTube downloads may fail without it)")
    print("Python packages")
    for mod in ("yt_dlp", "cv2", "numpy", "yaml"):
        check(mod, importlib.util.find_spec(mod), "pip install -r requirements.txt")
    has_fw = importlib.util.find_spec("faster_whisper")
    has_mlx = importlib.util.find_spec("mlx_whisper")
    check("whisper backend (faster-whisper or mlx-whisper)", has_fw or has_mlx, "pip install -r requirements.txt")
    if has_fw or has_mlx:
        from .transcribe import detect_backend
        b, d, m = detect_backend(common.load_config()["transcribe"])
        print(f"    → will use {b} on {d} with model {m}")
    print("Remotion")
    check("remotion/node_modules", (REMOTION_DIR / "node_modules").exists(), "cd remotion && npm install")
    check("caption fonts for ffmpeg engine", any((common.ASSETS_DIR / "fonts").glob("*.ttf")),
          "python -m pipeline assets")
    print("\nAll good ✔" if ok else "\nFix the ✖ items above.")


FONT_URLS = {
    "Anton-Regular.ttf": "ofl/anton/Anton-Regular.ttf",
    "BebasNeue-Regular.ttf": "ofl/bebasneue/BebasNeue-Regular.ttf",
    "Poppins-Black.ttf": "ofl/poppins/Poppins-Black.ttf",
    "Poppins-SemiBold.ttf": "ofl/poppins/Poppins-SemiBold.ttf",
}


def cmd_assets(_a):
    """One-time downloads: TTF fonts for the ffmpeg caption engine + the YuNet face model.
    (Remotion bundles its own fonts from npm; Whisper models download on first transcription.)"""
    import urllib.request
    d = common.ASSETS_DIR / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    for name, path in FONT_URLS.items():
        if (d / name).exists():
            continue
        try:
            urllib.request.urlretrieve(f"https://raw.githubusercontent.com/google/fonts/main/{path}", d / name)
            log(f"font {name}")
        except Exception as e:  # noqa: BLE001
            warn(f"could not download {name}: {e}")
    from .reframe import FaceDetector
    FaceDetector()


def _job(a):
    return resolve_job(a.job) if getattr(a, "job", None) else latest_job()


def main():
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if len(sys.argv) > 1 and sys.argv[1] == "dashboard":  # web UI: ./reels dashboard [--port N] [--no-open]
        from dashboard.server import main as dashboard_main
        return dashboard_main(sys.argv[2:])
    p = argparse.ArgumentParser(prog="python -m pipeline", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("prepare", help="download + transcribe")
    sp.add_argument("source")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--model", help="whisper model override (tiny/base/small/medium/large-v3/large-v3-turbo)")
    sp.add_argument("--language", help="force language, e.g. en")
    sp.set_defaults(fn=cmd_prepare)

    sv = sub.add_parser("validate")
    sv.add_argument("job", nargs="?")
    sv.set_defaults(fn=cmd_validate)

    pr = sub.add_parser("produce", help="cut, reframe and render every clip in clips.json")
    pr.add_argument("job", nargs="?")
    pr.add_argument("--only", help="comma-separated clip ids, e.g. 01,04")
    pr.add_argument("--force", action="store_true", help="redo every step")
    pr.add_argument("--rerender", action="store_true", help="redo only the final render (keeps cuts/reframes)")
    pr.add_argument("--engine", choices=["remotion", "ffmpeg"])
    pr.add_argument("--preset", choices=["hormozi", "karaoke", "boxed", "minimal"])
    pr.add_argument("--mode", choices=["face", "blur", "center"], help="reframe mode")
    pr.set_defaults(fn=cmd_produce)

    st = sub.add_parser("status")
    st.add_argument("job", nargs="?")
    st.set_defaults(fn=cmd_status)

    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sub.add_parser("assets", help="download fonts + face model (setup does this)").set_defaults(fn=cmd_assets)

    a = p.parse_args()
    ov = common.CLI_OVERRIDES
    if getattr(a, "model", None):
        ov.setdefault("transcribe", {})["model"] = a.model
    if getattr(a, "language", None):
        ov.setdefault("transcribe", {})["language"] = a.language
    if getattr(a, "engine", None):
        ov.setdefault("render", {})["engine"] = a.engine
    if getattr(a, "preset", None):
        ov.setdefault("captions", {})["preset"] = a.preset
        ov["_force_preset"] = True
    if getattr(a, "mode", None):
        ov.setdefault("reframe", {})["mode"] = a.mode
    a.fn(a)


if __name__ == "__main__":
    main()
