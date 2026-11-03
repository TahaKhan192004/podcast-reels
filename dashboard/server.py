"""Local dashboard: paste a YouTube link → reels.

  download + transcribe   local (yt-dlp + Whisper)            0 Claude tokens
  choose clips            ONE headless `claude -p` call        a few thousand tokens (shown in the UI)
  validate + render       local (ffmpeg + OpenCV + Remotion)   0 Claude tokens

Run:  ./reels dashboard      (or dashboard.cmd / ./dashboard.sh)
Binds to 127.0.0.1 only.
"""
from __future__ import annotations

import json
import mimetypes
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from pipeline.common import JOBS_DIR, ROOT, read_json

HERE = Path(__file__).resolve().parent
STATE_DIR = ROOT / ".dashboard"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STEPS = ["download", "transcribe", "pick", "validate", "render"]
MODELS = {"sonnet", "opus", "haiku"}

RUNS: dict[str, dict] = {}
LOCK = threading.Lock()
QUEUE: "queue.Queue[str]" = queue.Queue()
PROCS: dict[str, subprocess.Popen] = {}

# ─────────────────────────── Claude prompt (kept deliberately small) ───────────────────────────

SYSTEM = "You are a short-form video editor. Reply with one JSON object only: no prose, no code fences."

RULES = """Pick the {n} best vertical-reel clips (fewer if the video lacks strong ones; never pad) from the transcript below.
Transcript lines are "<start_seconds> <text>"; a line ends where the next starts.

Clip rules: 20-75 s (30-60 ideal), one continuous range, starts exactly on a hook sentence (bold claim, surprising number,
question, story with tension), stands alone with no missing context, ends right after the payoff. Skip sponsor reads,
intros/outros, "subscribe" asks, inside jokes. Clips must not overlap. Order best-first, keep only score>=7.

Per clip output:
{{"title":str,"start":sec,"end":sec,"score":1-10,"reason":"<=15 words","hook":"<=7 words, curiosity, ends on strongest word",
"caption_preset":"hormozi|boxed|karaoke|minimal","keywords":[2-4 words actually spoken],
"moments":[{{"t":sec,"effect":E,"text":str,"duration":sec}}],"post_caption":str,"hashtags":[4-5]}}
Wrap as {{"clips":[...]}}. Times are absolute seconds in the video.

Moments (2-4 per clip, >=4 s apart, first one >=3 s after the clip start (the hook title owns the start), t inside the clip, timed to the exact spoken word):
 stat    text "32%|OF ALL HEALINGS" (number|label)  - for a concrete number/statistic, duration 2.2
 kinetic text up to 6 words, big slam-in headline    - for the single key line, at most 1 per clip, duration 2
 lower   text "TOPIC|short subtitle"                 - names a concept/person/study, at most 1 per clip, duration 2.5
 text    text <=4 words with 1 emoji                 - pop-up callout, duration 1.5
 burst   text = 1 emoji                              - emotional/funny beat, at most 1 per clip
 punch (zoom on punchline) | shake (shocking) | flash (story turn) | zoom_out (reveal) - no text
Use a different mix on each clip; every clip gets at least one of stat/kinetic/lower/text.
caption_preset: hormozi=high-energy, boxed=punchy/fun, karaoke=storytelling, minimal=serious/emotional; vary across clips.
"""


def claude_exe() -> str | None:
    found = shutil.which("claude")
    if not found:
        return None
    p = Path(found)
    # npm's Windows shim is claude.cmd; the real binary takes arguments verbatim
    native = p.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    return str(native) if native.exists() else found


def compact_transcript(job: Path) -> str:
    rx = re.compile(r"^\[(\d+):(\d+):(\d+(?:\.\d+)?)\s*→\s*[^\]]*\]\s*(.*)$")
    out = []
    for part in sorted((job / "transcript").glob("part_*.txt")):
        for line in part.read_text(encoding="utf-8").splitlines():
            m = rx.match(line)
            if m:
                sec = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
                out.append(f"{sec:.1f} {m[4].strip()}")
    return "\n".join(out)


def extract_json(text: str) -> dict:
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON object in Claude's reply")
    data = json.loads(text[a:b + 1])
    if not isinstance(data.get("clips"), list) or not data["clips"]:
        raise ValueError("reply has no clips")
    return data


# ─────────────────────────── run state ───────────────────────────

def save(run: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    (STATE_DIR / f"{run['id']}.json").write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")


def add_log(run: dict, line: str) -> None:
    line = ANSI.sub("", line).rstrip()
    if line:
        run["log"].append(line)
        del run["log"][:-300]


def set_step(run: dict, step: str, progress: float = 0.0) -> None:
    run["step"], run["progress"] = step, progress


def run_cmd(run: dict, args: list[str], on_line=None) -> int:
    env = {**os.environ, "PYTHONUTF8": "1"}
    p = subprocess.Popen([sys.executable, "-m", "pipeline", *args], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    PROCS[run["id"]] = p
    for line in p.stdout:  # type: ignore[union-attr]
        line = ANSI.sub("", line).rstrip()
        if not line:
            continue
        if not re.match(r"^\s*\d+%\s+\(", line):  # keep the log readable: skip per-percent spam
            add_log(run, line)
        if on_line:
            on_line(line)
    p.wait()
    PROCS.pop(run["id"], None)
    if run.get("cancelled"):
        raise RuntimeError("cancelled")
    return p.returncode


def step_prepare(run: dict) -> Path:
    set_step(run, "download")
    found: dict[str, str] = {}

    def on_line(line: str) -> None:
        if line.startswith("JOB_DIR="):
            found["dir"] = line.split("=", 1)[1].strip()
        elif line.startswith("TITLE="):
            run["title"] = line.split("=", 1)[1].strip()
        elif "Extracting audio" in line or "Transcribing with" in line:
            set_step(run, "transcribe")
        m = re.match(r"^\s*(\d+)%\s+\(", line)
        if m and run["step"] == "transcribe":
            run["progress"] = int(m[1]) / 100
        m = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", line)
        if m and run["step"] == "download":
            run["progress"] = float(m[1]) / 100

    code = run_cmd(run, ["prepare", run["url"]], on_line)
    if code != 0 or "dir" not in found:
        raise RuntimeError("download/transcription failed (see log)")
    job = Path(found["dir"])
    run["job"] = job.name
    return job


def step_pick(run: dict, job: Path, retry_note: str = "") -> None:
    set_step(run, "pick")
    exe = claude_exe()
    if not exe:
        raise RuntimeError("`claude` CLI not found on PATH (install Claude Code and log in)")
    info = read_json(job / "info.json")
    dur = int(info.get("duration") or 0)
    head = f'Video: "{info.get("title","")}" by {info.get("channel","")} ({dur // 60} min)'
    extra = f"\nExtra instructions from the user: {run['instructions']}" if run.get("instructions") else ""
    prompt = (RULES.format(n=run["count"]) + extra + f"\n\n{head}\n\nTRANSCRIPT:\n" + compact_transcript(job)
              + (f"\n\nYour previous reply was rejected: {retry_note}. Return corrected JSON only." if retry_note else ""))
    (job / "pick_prompt.txt").write_text(prompt, encoding="utf-8")
    add_log(run, f"Asking Claude ({run['model']}) to choose clips — one call, ~{len(prompt) // 4:,} input tokens …")
    cmd = [exe, "-p", "--model", run["model"], "--system-prompt", SYSTEM, "--output-format", "json",
           "--no-session-persistence", "--disable-slash-commands", "--tools", ""]
    with tempfile.TemporaryDirectory() as neutral:  # neutral cwd so no project CLAUDE.md gets loaded
        env = {**os.environ, "MAX_THINKING_TOKENS": "0"}  # the rules are explicit; thinking would only burn tokens
        p = subprocess.Popen(cmd, cwd=neutral, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        PROCS[run["id"]] = p
        out, err = p.communicate(prompt)
        PROCS.pop(run["id"], None)
    if run.get("cancelled"):
        raise RuntimeError("cancelled")
    if p.returncode != 0:
        raise RuntimeError(f"claude failed: {(err or out).strip()[:300]}")
    reply = json.loads(out)
    if reply.get("is_error"):
        raise RuntimeError(f"claude error: {str(reply.get('result'))[:300]}")
    u = reply.get("usage") or {}
    t = run.setdefault("tokens", {"input": 0, "output": 0, "cost": 0.0, "calls": 0})
    t["input"] += sum(u.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    t["output"] += u.get("output_tokens", 0) or 0
    t["cost"] = round(t["cost"] + float(reply.get("total_cost_usd") or 0), 4)
    t["calls"] += 1
    data = extract_json(str(reply.get("result", "")))
    (job / "clips.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    add_log(run, f"Claude chose {len(data['clips'])} clip(s) — {t['input']:,} in / {t['output']:,} out tokens.")


def step_validate(run: dict, job: Path) -> bool:
    set_step(run, "validate")
    return run_cmd(run, ["validate", job.name]) == 0


def step_render(run: dict, job: Path) -> None:
    set_step(run, "render")
    total = len(read_json(job / "clips.validated.json"))
    cuts = {"n": 0}

    def on_line(line: str) -> None:
        if re.search(r"\]\s+reframing", line):
            cuts["n"] += 1
        m = re.search(r"\[(\d+)\]\s+(\d+)/(\d+)\s+(\d+)%", line)
        frac = 0.0
        if m:
            idx, tot, pct = int(m[2]), int(m[3]), int(m[4])
            frac = ((idx - 1) + pct / 100) / max(tot, 1)
        run["progress"] = round(0.3 * min(cuts["n"] / max(total, 1), 1) + 0.7 * frac, 4)

    args = ["produce", job.name]
    if run.get("motion") is False:
        args += ["--engine", "ffmpeg"]
    if run_cmd(run, args, on_line) != 0:
        raise RuntimeError("render failed (see log)")


def process(run_id: str) -> None:
    run = RUNS[run_id]
    if run.get("cancelled"):
        return
    run["status"] = "running"
    try:
        job = step_prepare(run)
        save(run)
        step_pick(run, job)
        save(run)
        if not step_validate(run, job):
            add_log(run, "clips.json failed validation — asking Claude to fix it once …")
            step_pick(run, job, retry_note="clips.json failed validation (bad times, out-of-range or empty)")
            if not step_validate(run, job):
                raise RuntimeError("clips.json is still invalid after one retry")
        save(run)
        step_render(run, job)
        run["status"], run["progress"] = "done", 1.0
        add_log(run, "All done ✔")
    except Exception as e:  # noqa: BLE001
        cancelled = run.get("cancelled")
        run["status"] = "cancelled" if cancelled else "error"
        run["error"] = "" if cancelled else str(e)
        add_log(run, "Cancelled." if cancelled else f"✖ {e}")
    finally:
        run["finished"] = time.time()
        save(run)


def worker() -> None:
    while True:
        rid = QUEUE.get()
        try:
            process(rid)
        except Exception as e:  # noqa: BLE001
            RUNS[rid].update(status="error", error=str(e))
        QUEUE.task_done()


# ─────────────────────────── views ───────────────────────────

def job_clips(job_name: str) -> list[dict]:
    job = JOBS_DIR / job_name
    try:
        specs = read_json(job / "clips.validated.json")
    except Exception:  # noqa: BLE001
        return []
    out = []
    for s in specs:
        slug = s.get("slug", "")
        mp4 = job / "output" / f"{slug}.mp4"
        cover = job / "output" / f"{slug}.jpg"
        out.append({
            "id": s["id"], "title": s.get("title"), "hook": s.get("hook"), "score": s.get("score"),
            "reason": s.get("reason"), "duration": s.get("duration"), "preset": s.get("caption_preset"),
            "effects": sorted({m["effect"] for m in s.get("moments", [])}),
            "post_caption": s.get("post_caption"), "hashtags": s.get("hashtags", []),
            "video": f"/media/{job_name}/{slug}.mp4" if mp4.exists() else None,
            "cover": f"/media/{job_name}/{slug}.jpg" if cover.exists() else None,
        })
    return out


def public(run: dict, full: bool = False) -> dict:
    keys = ("id", "url", "count", "model", "status", "step", "progress", "title", "job", "error", "tokens",
            "created", "finished", "motion", "instructions")
    d = {k: run.get(k) for k in keys}
    if run.get("job"):
        d["clips"] = job_clips(run["job"])
        d["rendered"] = sum(1 for c in d["clips"] if c["video"])
    if full:
        d["log"] = run.get("log", [])[-120:]
    return d


def orphan_runs() -> list[dict]:
    """Job folders made from the CLI (no dashboard run file) so earlier reels show up too."""
    known = {r.get("job") for r in RUNS.values()}
    out = []
    if JOBS_DIR.exists():
        for d in JOBS_DIR.iterdir():
            if d.is_dir() and d.name not in known and (d / "output").exists() and any((d / "output").glob("*.mp4")):
                try:
                    title = read_json(d / "info.json").get("title", d.name)
                except Exception:  # noqa: BLE001
                    title = d.name
                out.append({"id": f"job:{d.name}", "title": title, "job": d.name, "status": "done", "step": "render",
                            "progress": 1.0, "created": d.stat().st_mtime, "log": [], "url": "", "count": None,
                            "model": None, "tokens": None})
    return out


def find_run(rid: str) -> dict | None:
    if rid in RUNS:
        return RUNS[rid]
    if rid.startswith("job:"):
        return next((r for r in orphan_runs() if r["id"] == rid), None)
    return None


def load_state() -> None:
    if not STATE_DIR.exists():
        return
    for f in STATE_DIR.glob("*.json"):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if r.get("status") in ("running", "queued"):
            r["status"], r["error"] = "error", "interrupted (dashboard was restarted)"
        RUNS[r["id"]] = r


# ─────────────────────────── http ───────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "ReelDashboard"
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):  # quiet
        pass

    def _ok_host(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        origin = self.headers.get("Origin")
        if host not in ("127.0.0.1", "localhost"):
            return False
        return not origin or urlparse(origin).hostname in ("127.0.0.1", "localhost")

    def _json(self, obj, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if not self._ok_host():
            return self._json({"error": "forbidden"}, 403)
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = (HERE / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if path == "/api/jobs":
            with LOCK:
                items = [public(r) for r in RUNS.values()] + [public(r) for r in orphan_runs()]
            items.sort(key=lambda r: r.get("created") or 0, reverse=True)
            return self._json({"jobs": items, "claude": bool(claude_exe())})
        m = re.fullmatch(r"/api/jobs/(.+)", path)
        if m:
            run = find_run(unquote(m[1]))
            return self._json(public(run, full=True)) if run else self._json({"error": "not found"}, 404)
        m = re.fullmatch(r"/media/([\w.\-]+)/([\w.\-]+\.(?:mp4|jpg))", path)
        if m:
            return self._serve_file(JOBS_DIR / m[1] / "output" / m[2])
        self._json({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        if not self._ok_host():
            return self._json({"error": "forbidden"}, 403)
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._json({"error": "bad json"}, 400)
        if path == "/api/jobs":
            url = str(body.get("url", "")).strip()
            if not re.match(r"^https?://\S+$", url):
                return self._json({"error": "Paste a full http(s) video link."}, 400)
            try:
                count = max(1, min(20, int(body.get("count", 5))))
            except (TypeError, ValueError):
                count = 5
            model = body.get("model") if body.get("model") in MODELS else "sonnet"
            run = {"id": uuid.uuid4().hex[:10], "url": url, "count": count, "model": model,
                   "instructions": str(body.get("instructions", ""))[:500].strip(),
                   "motion": bool(body.get("motion", True)), "status": "queued", "step": "download",
                   "progress": 0.0, "title": url, "job": None, "error": None, "log": [], "created": time.time(),
                   "tokens": {"input": 0, "output": 0, "cost": 0.0, "calls": 0}}
            with LOCK:
                RUNS[run["id"]] = run
            save(run)
            QUEUE.put(run["id"])
            return self._json({"id": run["id"]}, 201)
        m = re.fullmatch(r"/api/jobs/([\w]+)/cancel", path)
        if m and m[1] in RUNS:
            run = RUNS[m[1]]
            run["cancelled"] = True
            proc = PROCS.get(run["id"])
            if proc and proc.poll() is None:
                if os.name == "nt":  # kill the whole tree (node/ffmpeg children too)
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
                else:
                    proc.kill()
            if run["status"] == "queued":
                run["status"] = "cancelled"
            return self._json({"ok": True})
        self._json({"error": "not found"}, 404)

    def _serve_file(self, f: Path) -> None:
        if not f.is_file():
            return self._json({"error": "not found"}, 404)
        size = f.stat().st_size
        start, end, code = 0, size - 1, 200
        rng = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if rng and (rng[1] or rng[2]):
            if rng[1]:
                start = int(rng[1])
                end = int(rng[2]) if rng[2] else size - 1
            else:
                start = max(0, size - int(rng[2]))
            end = min(end, size - 1)
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with f.open("rb") as fh:
                fh.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main(argv: list[str] | None = None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="reels dashboard")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="don't open the browser")
    a = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    load_state()
    threading.Thread(target=worker, daemon=True).start()
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError:
        sys.exit(f"Port {a.port} is busy. Is the dashboard already running? Try --port {a.port + 1}")
    url = f"http://127.0.0.1:{a.port}/"
    print(f"Reel dashboard running at {url}   (Ctrl+C to stop)")
    if not claude_exe():
        print("! `claude` CLI not found — clip picking will fail until Claude Code is installed and logged in.")
    if not a.no_open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
        for p in list(PROCS.values()):
            p.kill()


if __name__ == "__main__":
    main()
