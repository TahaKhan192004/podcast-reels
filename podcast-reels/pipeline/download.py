"""Step 1: download a YouTube video (or import a local file) into a new job folder."""
from __future__ import annotations

import shutil
from pathlib import Path

from .common import JOBS_DIR, die, load_config, log, run, require_bin, slugify, video_info, write_json


def download(source: str, force: bool = False) -> Path:
    cfg = load_config()["download"]
    if Path(source).expanduser().is_file():
        return _import_local(Path(source).expanduser().resolve(), force)

    try:
        import yt_dlp
    except ImportError:
        die("yt-dlp is not installed. Activate the venv and run: pip install -r requirements.txt")

    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, **_cookie_opts(cfg)}) as ydl:
        info = ydl.extract_info(source, download=False)

    job = JOBS_DIR / f"{slugify(info.get('title', 'video'), 50)}-{info['id']}"
    job.mkdir(parents=True, exist_ok=True)
    out = job / "source.mp4"

    _write_meta(job, info, source)
    if out.exists() and not force:
        log(f"Already downloaded → {out}")
        return job

    log(f"Downloading “{info.get('title')}” ({_dur(info.get('duration'))}) …")
    opts = {
        "format": cfg["format"].format(h=cfg["max_height"]),
        "merge_output_format": "mp4",
        "outtmpl": str(job / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": False,
        "noprogress": False,
        **_cookie_opts(cfg),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([source])

    if not out.exists():  # some formats merge to mkv/webm → remux to mp4
        cand = next((p for p in job.glob("source.*") if p.suffix in {".mkv", ".webm", ".mov"}), None)
        if not cand:
            die("Download finished but no video file was found.")
        run([require_bin("ffmpeg"), "-y", "-i", str(cand), "-c", "copy", str(out)])
        cand.unlink()
    log(f"Saved → {out}")
    return job


def _import_local(path: Path, force: bool) -> Path:
    job = JOBS_DIR / slugify(path.stem, 60)
    job.mkdir(parents=True, exist_ok=True)
    out = job / "source.mp4"
    if not out.exists() or force:
        log(f"Importing local file {path.name} …")
        if path.suffix.lower() == ".mp4":
            shutil.copy2(path, out)
        else:
            run([require_bin("ffmpeg"), "-y", "-i", str(path), "-c:v", "libx264", "-crf", "16",
                 "-c:a", "aac", "-b:a", "192k", str(out)])
    vi = video_info(out)
    write_json(job / "info.json", {"title": path.stem, "source": str(path), "duration": vi["duration"],
                                   "channel": "", "description": "", "chapters": []})
    return job


def _write_meta(job: Path, info: dict, url: str) -> None:
    write_json(job / "info.json", {
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "url": info.get("webpage_url", url),
        "id": info.get("id"),
        "duration": info.get("duration"),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "description": (info.get("description") or "")[:4000],
        "tags": info.get("tags") or [],
        "chapters": [{"start": c.get("start_time"), "end": c.get("end_time"), "title": c.get("title")}
                     for c in (info.get("chapters") or [])],
    })


def _cookie_opts(cfg: dict) -> dict:
    b = (cfg.get("cookies_from_browser") or "").strip()
    return {"cookiesfrombrowser": (b,)} if b else {}


def _dur(sec) -> str:
    if not sec:
        return "?"
    h, r = divmod(int(sec), 3600)
    return f"{h}h{r // 60:02d}m" if h else f"{r // 60}m{r % 60:02d}s"
