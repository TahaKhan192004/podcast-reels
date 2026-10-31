"""Step 6: caption data.

build_pages()  → word groups ("pages") with per-word timing + emphasis, used by Remotion.
write_ass()    → .ass subtitle file per preset, used by the ffmpeg-only render engine.
"""
from __future__ import annotations

import re
from pathlib import Path

PRESET_LAYOUT = {  # words per page / chars per page
    "hormozi": (3, 18),
    "boxed": (3, 18),
    "karaoke": (7, 34),
    "minimal": (8, 40),
}


def _norm(w: str) -> str:
    return re.sub(r"[^\w']", "", w.lower())


def build_pages(words: list[dict], preset: str, keywords: list[str], ccfg: dict) -> list[dict]:
    max_w, max_c = PRESET_LAYOUT.get(preset, (3, 18))
    if preset in ("hormozi", "boxed"):
        max_w, max_c = ccfg.get("max_words", max_w), ccfg.get("max_chars", max_c)
    kw_tokens = {_norm(t) for k in keywords for t in k.split() if len(_norm(t)) > 2}

    pages, cur = [], []
    for i, w in enumerate(words):
        text = w["w"].strip()
        if not text:
            continue
        cur.append({"text": text, "s": w["s"], "e": w["e"], "emph": _norm(text) in kw_tokens})
        nxt = words[i + 1] if i + 1 < len(words) else None
        chars = sum(len(x["text"]) + 1 for x in cur)
        punct = text[-1:] in ".?!,;:"
        gap = nxt is not None and nxt["s"] - w["e"] > 0.45
        nxt_chars = chars + (len(nxt["w"]) if nxt else 0)
        if nxt is None or len(cur) >= max_w or nxt_chars > max_c or punct or gap:
            pages.append(cur)
            cur = []

    out = []
    for j, pg in enumerate(pages):
        start = pg[0]["s"]
        end = pg[-1]["e"]
        nxt_start = pages[j + 1][0]["s"] if j + 1 < len(pages) else end + 0.6
        end = min(max(end + 0.25, start + 0.4), nxt_start)  # hold briefly, never overlap the next page
        out.append({"start": round(start, 3), "end": round(end, 3), "words": pg})
    return out


def zoom_beats(words: list[dict], duration: float, min_gap: float = 3.5) -> list[dict]:
    """Jump-cut style zoom changes at sentence boundaries (alternating 1.0 / 1.12)."""
    beats, last, level = [{"t": 0.0, "scale": 1.0}], 0.0, 1.0
    for i, w in enumerate(words[:-1]):
        boundary = w["w"][-1:] in ".?!" or words[i + 1]["s"] - w["e"] > 0.5
        t = words[i + 1]["s"]
        if boundary and t - last >= min_gap and duration - t > 1.5:
            level = 1.12 if level == 1.0 else 1.0
            beats.append({"t": round(t, 3), "scale": level})
            last = t
    return beats


# ── ASS (ffmpeg engine) ──────────────────────────────────────
def _ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(pages: list[dict], preset: str, ccfg: dict, out: Path, W: int = 1080, H: int = 1920) -> Path:
    hl = _ass_color(ccfg["highlight_color"])
    sec = _ass_color(ccfg["secondary_color"])
    white, black = "&H00FFFFFF", "&H00000000"
    # libass needs static TTFs (assets/fonts, see `python -m pipeline fonts`): Montserrat/Inter → Poppins
    font = {"Anton": "Anton", "BebasNeue": "Bebas Neue"}.get(ccfg["font"], "Poppins Black")
    if preset == "minimal":
        font = "Poppins SemiBold"
    margin_v = int(H * (1 - ccfg["position"]))
    upper = ccfg.get("uppercase", True) and preset != "minimal"

    styles = {
        "hormozi": f"Style: Main,{font},96,{white},{white},{black},&H80000000,0,0,0,0,100,100,0,0,1,7,4,2,60,60,{margin_v},1",
        "boxed":   f"Style: Main,{font},84,{white},{white},&H00000000,&H00000000,0,0,0,0,100,100,0,0,3,14,0,2,60,60,{margin_v},1",
        "karaoke": f"Style: Main,{font},72,{hl},&H40FFFFFF,{black},&H80000000,0,0,0,0,100,100,0,0,1,5,3,2,70,70,{margin_v},1",
        "minimal": f"Style: Main,{font},58,{white},{white},&H00000000,&HA0000000,0,0,0,0,100,100,0,0,3,18,0,2,90,90,{margin_v},1",
    }
    lines = []
    for pg in pages:
        words = [(w["text"].upper() if upper else w["text"]) for w in pg["words"]]
        if preset == "karaoke":
            parts, cursor = [], pg["start"]
            for w, txt in zip(pg["words"], words):
                k = max(1, int(round((w["e"] - cursor) * 100)))
                parts.append(f"{{\\kf{k}}}{txt}")
                cursor = w["e"]
            lines.append((pg["start"], pg["end"], " ".join(parts)))
        elif preset == "minimal":
            lines.append((pg["start"], pg["end"], "{\\fad(80,80)}" + " ".join(words)))
        else:  # hormozi / boxed: one event per active word
            for i, w in enumerate(pg["words"]):
                s = w["s"] if i else pg["start"]
                e = pg["words"][i + 1]["s"] if i + 1 < len(pg["words"]) else pg["end"]
                pop = "{\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
                toks = []
                for j, (ww, txt) in enumerate(zip(pg["words"], words)):
                    if preset == "boxed":
                        if j > i:
                            continue  # boxed reveals words one by one
                        toks.append(f"{{\\3c{hl}\\c{black}}}{txt}{{\\3c{black}\\c{white}}}" if j == i else txt)
                    elif j == i:
                        toks.append(f"{{\\c{hl}\\fscx112\\fscy112}}{txt}{{\\c{white}\\fscx100\\fscy100}}")
                    elif ww["emph"]:
                        toks.append(f"{{\\c{sec}}}{txt}{{\\c{white}}}")
                    else:
                        toks.append(txt)
                lines.append((s, e, pop + " ".join(toks)))

    header = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{styles.get(preset, styles['hormozi'])}\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    body = "\n".join(f"Dialogue: 0,{_ass_time(s)},{_ass_time(e)},Main,,0,0,0,,{t}" for s, e, t in lines)
    out.write_text(header + body + "\n", encoding="utf-8")
    return out
