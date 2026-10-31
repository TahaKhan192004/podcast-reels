"""Step 4: frame-accurate cut of each clip from the source video (+ loudness normalisation)."""
from __future__ import annotations

from pathlib import Path

from .common import clip_dir, load_config, log, require_bin, run


def cut(job: Path, spec: dict, force: bool = False) -> Path:
    out = clip_dir(job, spec["id"]) / "raw.mp4"
    if out.exists() and not force:
        return out
    enc = load_config(job)["encode"]
    afilter = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"] if enc.get("loudnorm", True) else []
    log(f"[{spec['id']}] cutting {spec['duration']:.1f}s …")
    run([require_bin("ffmpeg"), "-y",
         "-ss", f"{spec['start']:.3f}", "-i", str(job / "source.mp4"), "-t", f"{spec['duration']:.3f}",
         "-map", "0:v:0", "-map", "0:a:0?",
         "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p",
         *afilter, "-c:a", "aac", "-b:a", enc["audio_bitrate"], "-ar", "48000",
         "-movflags", "+faststart", str(out)])
    return out
