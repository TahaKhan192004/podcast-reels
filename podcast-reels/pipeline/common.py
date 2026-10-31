"""Shared helpers: config loading, paths, ffmpeg wrappers, time formatting."""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = ROOT / "jobs"
MODELS_DIR = ROOT / "models"
ASSETS_DIR = ROOT / "assets"
REMOTION_DIR = ROOT / "remotion"


# ── logging ──────────────────────────────────────────────────
def log(msg: str) -> None:
    print(f"\033[36m▸\033[0m {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"\033[33m⚠ {msg}\033[0m", flush=True)


def die(msg: str) -> None:
    print(f"\033[31m✖ {msg}\033[0m", file=sys.stderr, flush=True)
    sys.exit(1)


# ── config ───────────────────────────────────────────────────
def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


CLI_OVERRIDES: dict = {}  # filled by __main__ from flags like --preset / --engine


def load_config(job_dir: Path | None = None) -> dict:
    """config.yaml  ←  jobs/<job>/config.yaml  ←  command-line flags"""
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    if job_dir and (job_dir / "config.yaml").exists():
        cfg = _deep_merge(cfg, yaml.safe_load((job_dir / "config.yaml").read_text(encoding="utf-8")) or {})
    return _deep_merge(cfg, CLI_OVERRIDES)


# ── json ─────────────────────────────────────────────────────
def read_json(p: Path) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p: Path, data: Any) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── strings / time ───────────────────────────────────────────
def slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)[:max_len].strip("-") or "video"


def fmt_ts(sec: float) -> str:
    """123.456 -> 00:02:03.4"""
    sec = max(0.0, float(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:04.1f}"


def parse_ts(value: float | int | str) -> float:
    """Accepts 123.4, "123.4", "02:03.4", "00:02:03.4"."""
    if isinstance(value, (int, float)):
        return float(value)
    parts = [float(p) for p in str(value).strip().split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


# ── ffmpeg ───────────────────────────────────────────────────
def require_bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        die(f"'{name}' not found on PATH. Run the setup script first (see README).")
    return path


def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, capture_output=quiet, text=True)
    if res.returncode != 0:
        err = (res.stderr or "")[-3000:] if quiet else ""
        die(f"Command failed ({res.returncode}): {' '.join(map(str, cmd[:6]))} …\n{err}")
    return res


def ffprobe(path: Path) -> dict:
    res = run([require_bin("ffprobe"), "-v", "error", "-print_format", "json",
               "-show_format", "-show_streams", str(path)])
    return json.loads(res.stdout)


def video_info(path: Path) -> dict:
    data = ffprobe(path)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    return {
        "width": int(v["width"]),
        "height": int(v["height"]),
        "fps": fps,
        "duration": float(data["format"].get("duration", 0)),
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
    }


# ── job helpers ──────────────────────────────────────────────
def resolve_job(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir():
        return p.resolve()
    if (JOBS_DIR / arg).is_dir():
        return (JOBS_DIR / arg).resolve()
    die(f"Job folder not found: {arg}")


def latest_job() -> Path:
    jobs = [d for d in JOBS_DIR.iterdir() if d.is_dir()] if JOBS_DIR.exists() else []
    if not jobs:
        die("No jobs yet. Run: python -m pipeline prepare <youtube-url>")
    return max(jobs, key=lambda d: d.stat().st_mtime)


def clip_dir(job: Path, clip_id: str) -> Path:
    d = job / "clips" / clip_id
    d.mkdir(parents=True, exist_ok=True)
    return d
