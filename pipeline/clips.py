"""Step 3: validate Claude's clips.json, snap boundaries to word edges and build per-clip specs.

clips.json (written by Claude) — see CLAUDE.md for the full schema:
{
  "clips": [{
    "title": "...", "start": "00:12:03.4", "end": "00:13:01.0",
    "hook": "Most startups die here", "score": 9, "reason": "...",
    "caption_preset": "hormozi",                # optional
    "keywords": ["cash", "year two"],           # optional, highlighted in captions
    "moments": [{"t": "00:12:20.0", "effect": "punch", "text": "💸 CASH IS KING"}],  # optional
    "post_caption": "...", "hashtags": ["#startups"]
  }]
}
"""
from __future__ import annotations

from pathlib import Path

from .common import clip_dir, die, fmt_ts, load_config, parse_ts, read_json, slugify, warn, write_json

EFFECTS = {"punch", "shake", "flash", "text", "zoom_out", "glitch", "stat", "kinetic", "lower", "burst"}
PRESETS = {"hormozi", "karaoke", "boxed", "minimal"}


def validate(job: Path) -> list[dict]:
    path = job / "clips.json"
    if not path.exists():
        die(f"{path} not found. Ask Claude to pick clips first (/pick-clips).")
    try:
        data = read_json(path)
    except Exception as e:  # noqa: BLE001
        die(f"clips.json is not valid JSON: {e}")
    raw = data["clips"] if isinstance(data, dict) else data
    if not raw:
        die("clips.json has no clips.")

    cfg = load_config(job)
    ccfg = cfg["clips"]
    words = read_json(job / "transcript.json")["words"]
    specs: list[dict] = []
    errors = 0

    for i, c in enumerate(raw, 1):
        cid = str(c.get("id") or f"{i:02d}").zfill(2)
        try:
            start, end = parse_ts(c["start"]), parse_ts(c["end"])
        except (KeyError, ValueError) as e:
            warn(f"[{cid}] bad start/end: {e}")
            errors += 1
            continue
        if end <= start:
            warn(f"[{cid}] end ≤ start")
            errors += 1
            continue

        snapped = snap(words, start, end, ccfg["pad_start"], ccfg["pad_end"])
        if snapped is None:
            warn(f"[{cid}] no transcribed speech between {fmt_ts(start)} and {fmt_ts(end)}")
            errors += 1
            continue
        start, end = snapped
        dur = end - start
        if dur < ccfg["min_seconds"] * 0.8 or dur > ccfg["max_seconds"] * 1.25:
            warn(f"[{cid}] duration {dur:.1f}s is outside {ccfg['min_seconds']}–{ccfg['max_seconds']}s")

        cwords = [{"w": w["w"], "s": round(w["s"] - start, 3), "e": round(w["e"] - start, 3)}
                  for w in words if w["s"] >= start - 0.01 and w["e"] <= end + 0.01]
        moments = []
        for m in c.get("moments", []) or []:
            try:
                t = parse_ts(m["t"]) - start
            except (KeyError, ValueError):
                continue
            eff = m.get("effect", "punch")
            if eff not in EFFECTS:
                warn(f"[{cid}] unknown effect '{eff}' → using 'punch'")
                eff = "punch"
            if -1.0 <= t < 0:  # start snapped to the first word a moment later than the planned time
                t = 0.0
            if not 0 <= t <= dur:
                warn(f"[{cid}] moment at {m['t']} is outside the clip → ignored")
                continue
            moments.append({"t": round(t, 3), "effect": eff, "text": m.get("text", ""),
                            "duration": float(m.get("duration", 1.2))})

        preset = cfg["captions"]["preset"] if cfg.get("_force_preset") else \
            (c.get("caption_preset") or cfg["captions"]["preset"])
        if preset not in PRESETS:
            warn(f"[{cid}] unknown caption preset '{preset}' → {cfg['captions']['preset']}")
            preset = cfg["captions"]["preset"]

        spec = {
            "id": cid,
            "title": c.get("title", f"Clip {cid}"),
            "slug": f"{cid}_{slugify(c.get('title', 'clip'), 40)}",
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(dur, 3),
            "hook": c.get("hook", ""),
            "score": c.get("score"),
            "reason": c.get("reason", ""),
            "caption_preset": preset,
            "keywords": [k.lower() for k in c.get("keywords", []) or []],
            "moments": sorted(moments, key=lambda m: m["t"]),
            "post_caption": c.get("post_caption", ""),
            "hashtags": c.get("hashtags", []) or [],
            "words": cwords,
        }
        write_json(clip_dir(job, cid) / "clip.json", spec)
        specs.append(spec)

    _check_overlaps(specs)
    if errors:
        warn(f"{errors} clip(s) skipped because of errors.")
    _print_table(specs)
    write_json(job / "clips.validated.json", [{k: v for k, v in s.items() if k != "words"} for s in specs])
    return specs


def snap(words: list[dict], start: float, end: float, pad_s: float,
         pad_e: float) -> tuple[float, float] | None:
    """Move start/end to the nearest word boundaries so we never cut mid-word (None = no speech in range)."""
    first = next((i for i, w in enumerate(words) if w["e"] > start + 0.05), None)
    last = max((i for i, w in enumerate(words) if w["s"] < end - 0.05), default=None)
    if first is None or last is None or last < first:
        return None
    # if the chosen start lands mid-word, include that whole word
    s = words[first]["s"]
    e = words[last]["e"]
    prev_end = words[first - 1]["e"] if first > 0 else 0.0
    next_start = words[last + 1]["s"] if last + 1 < len(words) else e + pad_e
    s = max(s - pad_s, (prev_end + s) / 2 if first > 0 else 0.0)
    e = min(e + pad_e, (e + next_start) / 2 if last + 1 < len(words) else e + pad_e)
    return round(max(0.0, s), 3), round(e, 3)


def _check_overlaps(specs: list[dict]) -> None:
    ordered = sorted(specs, key=lambda s: s["start"])
    for a, b in zip(ordered, ordered[1:]):
        if b["start"] < a["end"] - 1:
            warn(f"Clips {a['id']} and {b['id']} overlap ({fmt_ts(b['start'])} < {fmt_ts(a['end'])})")


def _print_table(specs: list[dict]) -> None:
    print("\n  ID  START        END          DUR    SCORE  TITLE")
    for s in specs:
        print(f"  {s['id']}  {fmt_ts(s['start'])}  {fmt_ts(s['end'])}  {s['duration']:5.1f}s  "
              f"{str(s.get('score') or '-'):>5}  {s['title'][:50]}")
    print()
