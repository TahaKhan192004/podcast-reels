"""Step 2: local Whisper transcription with word-level timestamps.

Backend auto-detection:
  • Apple Silicon Mac + mlx-whisper installed  → mlx-whisper  (large-v3-turbo)
  • NVIDIA GPU (CUDA visible to CTranslate2)   → faster-whisper float16 (large-v3-turbo)
  • otherwise                                   → faster-whisper int8 on CPU (small)

Outputs in the job folder:
  audio.wav                 16 kHz mono
  transcript.json           {language, backend, model, words:[{w,s,e}], lines:[{s,e,text}]}
  transcript/part_XX.txt    human/Claude-readable timestamped lines, split into chunks
"""
from __future__ import annotations

import ctypes
import glob
import os
import platform
import site
import time
from pathlib import Path

from .common import die, fmt_ts, load_config, log, read_json, require_bin, run, warn, write_json

MLX_MODELS = {
    "tiny": "mlx-community/whisper-tiny", "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx", "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx", "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}


def _preload_cuda_libs() -> None:
    """faster-whisper on NVIDIA needs cuBLAS + cuDNN. If they came from pip (nvidia-cublas-cu12,
    nvidia-cudnn-cu12), make them findable without the user editing PATH / LD_LIBRARY_PATH."""
    roots = [os.path.join(p, "nvidia") for p in site.getsitepackages() + [site.getusersitepackages()]]
    for root in filter(os.path.isdir, roots):
        if os.name == "nt":
            for d in glob.glob(os.path.join(root, "*", "bin")):
                os.add_dll_directory(d)
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        else:
            for lib in sorted(glob.glob(os.path.join(root, "*", "lib", "lib*.so*"))):
                try:
                    ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


def detect_backend(cfg: dict) -> tuple[str, str, str]:
    """Returns (backend, device, model)."""
    want = cfg.get("backend", "auto")
    model = cfg.get("model", "auto")
    is_apple = platform.system() == "Darwin" and platform.machine() == "arm64"

    if want in ("auto", "mlx") and is_apple:
        try:
            import mlx_whisper  # noqa: F401
            return "mlx", "metal", "large-v3-turbo" if model == "auto" else model
        except ImportError:
            if want == "mlx":
                die("mlx-whisper not installed: pip install mlx-whisper")
            warn("Apple Silicon detected but mlx-whisper missing; falling back to faster-whisper CPU.")

    try:
        import ctranslate2
    except ImportError:
        die("faster-whisper is not installed: pip install -r requirements.txt")
    if ctranslate2.get_cuda_device_count() > 0:
        _preload_cuda_libs()
        return "faster-whisper", "cuda", "large-v3-turbo" if model == "auto" else model
    return "faster-whisper", "cpu", "small" if model == "auto" else model


def extract_audio(job: Path) -> Path:
    wav = job / "audio.wav"
    if not wav.exists():
        log("Extracting audio …")
        run([require_bin("ffmpeg"), "-y", "-i", str(job / "source.mp4"), "-vn", "-ac", "1",
             "-ar", "16000", "-c:a", "pcm_s16le", str(wav)])
    return wav


def transcribe(job: Path, force: bool = False) -> Path:
    out = job / "transcript.json"
    if out.exists() and not force:
        log(f"Transcript exists → {out}")
        write_chunks(job)
        return out

    cfg = load_config(job)["transcribe"]
    wav = extract_audio(job)
    backend, device, model = detect_backend(cfg)
    lang = cfg.get("language") or None
    log(f"Transcribing with {backend} on {device} (model: {model}) — this is the slow step …")
    t0 = time.time()

    words: list[dict] = []
    if backend == "mlx":
        import mlx_whisper
        res = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MLX_MODELS.get(model, model),
                                     word_timestamps=True, language=lang,
                                     condition_on_previous_text=False)
        language = res.get("language", lang or "")
        for seg in res["segments"]:
            for w in seg.get("words", []):
                words.append({"w": w["word"].strip(), "s": round(w["start"], 3), "e": round(w["end"], 3)})
    else:
        from faster_whisper import WhisperModel
        compute = "float16" if device == "cuda" else "int8"
        wm = WhisperModel(model, device=device, compute_type=compute)
        segments, info = wm.transcribe(str(wav), language=lang, word_timestamps=True, vad_filter=True,
                                       vad_parameters={"min_silence_duration_ms": 500},
                                       condition_on_previous_text=False)
        language = info.language
        total = info.duration or 1
        last_pct = -10
        for seg in segments:
            for w in seg.words or []:
                words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
            pct = int(seg.end / total * 100)
            if pct >= last_pct + 5:
                print(f"   {pct:3d}%  ({fmt_ts(seg.end)} / {fmt_ts(total)})", flush=True)
                last_pct = pct

    words = [w for w in words if w["w"]]
    if not words:
        die("Whisper returned no words — is there speech in this video?")
    write_json(out, {"language": language, "backend": backend, "model": model,
                     "words": words, "lines": build_lines(words)})
    log(f"Transcribed {len(words):,} words in {time.time() - t0:.0f}s → {out}")
    write_chunks(job)
    return out


def build_lines(words: list[dict], max_words: int = 22, gap: float = 1.0) -> list[dict]:
    """Group words into short sentence-like lines so Claude gets fine-grained timestamps."""
    lines, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_sentence = w["w"][-1:] in ".?!" and len(cur) >= 4
        long_gap = nxt is not None and nxt["s"] - w["e"] > gap
        if end_sentence or long_gap or len(cur) >= max_words or nxt is None:
            lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
            cur = []
    return lines


def write_chunks(job: Path) -> None:
    data = read_json(job / "transcript.json")
    chunk_sec = load_config(job)["transcribe"]["chunk_minutes"] * 60
    tdir = job / "transcript"
    tdir.mkdir(exist_ok=True)
    for old in tdir.glob("part_*.txt"):
        old.unlink()
    buckets: dict[int, list[str]] = {}
    for ln in data["lines"]:
        buckets.setdefault(int(ln["s"] // chunk_sec), []).append(
            f"[{fmt_ts(ln['s'])} → {fmt_ts(ln['e'])}] {ln['text']}")
    for i, (k, rows) in enumerate(sorted(buckets.items()), 1):
        header = f"# Part {i}  ({fmt_ts(k * chunk_sec)} – {fmt_ts((k + 1) * chunk_sec)})\n\n"
        (tdir / f"part_{i:02d}.txt").write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    log(f"Wrote {len(buckets)} transcript chunk(s) → {tdir}")
