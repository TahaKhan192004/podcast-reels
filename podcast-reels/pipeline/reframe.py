"""Step 5: turn a 16:9 clip into a 9:16 reel.

mode=face   → detect faces (OpenCV YuNet, Haar fallback), pick the main speaker, follow them
              with a smooth "virtual camera" that snaps on camera cuts and stays still otherwise.
mode=blur   → full frame centred over a blurred, zoomed copy of itself.
mode=center → plain centre crop.
"""
from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path

import numpy as np

from .common import MODELS_DIR, clip_dir, die, load_config, log, require_bin, run, video_info, warn, write_json

YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
DETECT_W = 640  # detection runs on a downscaled frame


def reframe(job: Path, spec: dict, force: bool = False) -> Path:
    d = clip_dir(job, spec["id"])
    src, out = d / "raw.mp4", d / "vertical.mp4"
    if out.exists() and not force:
        return out
    cfg = load_config(job)
    rc, enc = cfg["reframe"], cfg["encode"]
    vi = video_info(src)
    mode = rc["mode"]

    if vi["width"] / vi["height"] <= 9 / 16 + 0.01:  # already vertical
        mode = "center"
    if mode == "face":
        track = analyse_faces(src, vi, rc)
        if track is None:
            warn(f"[{spec['id']}] no faces found → {rc['no_face_fallback']}")
            mode = rc["no_face_fallback"]
        else:
            write_json(d / "track.json", track["debug"])
            log(f"[{spec['id']}] reframing (face tracking, {track['shots']} shot(s)) …")
            _render_track(src, out, vi, track["centers"], rc, enc)
            return out

    log(f"[{spec['id']}] reframing ({mode}) …")
    W, H = rc["width"], rc["height"]
    if mode == "blur":
        vf = (f"[0:v]split=2[bg][fg];"
              f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:2,"
              f"eq=brightness=-0.08[bgb];"
              f"[fg]scale={W}:-2:flags=lanczos[fgs];[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[v]")
    else:
        vf = (f"[0:v]crop='min(iw,ih*9/16)':ih:(iw-min(iw,ih*9/16))/2:0,"
              f"scale={W}:{H}:flags=lanczos,setsar=1[v]")
    run([require_bin("ffmpeg"), "-y", "-i", str(src), "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-crf", str(enc["crf"]), "-preset", enc["preset"], "-pix_fmt", "yuv420p",
         "-c:a", "copy", str(out)])
    return out


# ── face detection ───────────────────────────────────────────
class FaceDetector:
    def __init__(self):
        import cv2
        self.cv2 = cv2
        self.yunet = None
        model = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
        if hasattr(cv2, "FaceDetectorYN"):
            try:
                if not model.exists():
                    log("Downloading YuNet face model (≈230 KB, one time) …")
                    MODELS_DIR.mkdir(exist_ok=True)
                    urllib.request.urlretrieve(YUNET_URL, model)
                self.yunet = cv2.FaceDetectorYN.create(str(model), "", (320, 320), 0.6, 0.3, 5000)
            except Exception as e:  # noqa: BLE001
                model.unlink(missing_ok=True)
                warn(f"YuNet unavailable ({e}); using Haar cascade (less accurate).")
        if self.yunet is None:
            self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def __call__(self, small: np.ndarray) -> list[dict]:
        """Faces in a downscaled BGR frame: {cx, w (normalised), conf, box (pixels x,y,w,h)}."""
        h, w = small.shape[:2]
        boxes = []
        if self.yunet is not None:
            self.yunet.setInputSize((w, h))
            _, det = self.yunet.detect(small)
            for f in det if det is not None else []:
                boxes.append((int(f[0]), int(f[1]), int(f[2]), int(f[3]), float(f[-1])))
        else:
            gray = self.cv2.cvtColor(small, self.cv2.COLOR_BGR2GRAY)
            for (x, y, fw, fh) in self.haar.detectMultiScale(gray, 1.1, 5, minSize=(int(w * 0.04),) * 2):
                boxes.append((int(x), int(y), int(fw), int(fh), 0.8))
        faces = [{"cx": (x + fw / 2) / w, "w": fw / w, "conf": c, "box": (x, y, fw, fh)}
                 for x, y, fw, fh, c in boxes]
        return [f for f in faces if f["w"] > 0.03]  # ignore tiny background faces


def _mouth_roi(gray: np.ndarray, box) -> np.ndarray | None:
    """Lower-middle part of the face, normalised to a small patch (used to measure talking motion)."""
    import cv2
    x, y, w, h = box
    x0, x1 = max(0, x + int(w * 0.2)), min(gray.shape[1], x + int(w * 0.8))
    y0, y1 = max(0, y + int(h * 0.6)), min(gray.shape[0], y + int(h * 1.05))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return cv2.resize(gray[y0:y1, x0:x1], (24, 16)).astype(np.float32)


def analyse_faces(src: Path, vi: dict, rc: dict) -> dict | None:
    import cv2
    det = FaceDetector()
    cap = cv2.VideoCapture(str(src))
    fps = vi["fps"] or 30
    step = max(1, round(fps / rc["sample_fps"]))
    sfps = fps / step  # actual samples per second
    crop_w = (vi["height"] * 9 / 16) / vi["width"]  # crop width as fraction of frame width

    samples, prev_hist, prev_faces, idx = [], None, [], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            small = cv2.resize(frame, (DETECT_W, int(DETECT_W * frame.shape[0] / frame.shape[1])))
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            cut = prev_hist is not None and \
                cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA) > rc["scene_cut_threshold"]
            prev_hist = hist
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = det(small)
            for f in faces:  # talking motion = change of the mouth patch since the previous sample
                f["roi"] = _mouth_roi(gray, f["box"])
                match = None if cut else min(prev_faces, key=lambda p: abs(p["cx"] - f["cx"]), default=None)
                f["act"] = 0.0
                if match is not None and abs(match["cx"] - f["cx"]) < 0.06 \
                        and f["roi"] is not None and match["roi"] is not None:
                    f["act"] = float(np.mean(np.abs(f["roi"] - match["roi"])))
            samples.append({"f": idx, "faces": faces, "cut": bool(cut)})
            prev_faces = faces
        idx += 1
    cap.release()
    total_frames = idx
    if not samples or sum(1 for s in samples if s["faces"]) < max(2, len(samples) * 0.15):
        return None

    targets, snaps = _choose_targets(samples, crop_w, sfps)

    # virtual camera per segment (segments split by camera cuts and speaker switches):
    # locked if the target barely moves, otherwise deadzone + exponential smoothing
    bounds = sorted({0, len(samples), *[i for i, s in enumerate(samples) if s["cut"]], *snaps})
    cams = [0.5] * len(samples)
    for a, b in zip(bounds, bounds[1:]):
        seg = targets[a:b]
        if not seg:
            continue
        if np.std(seg) < rc["deadzone"] / 2:
            cams[a:b] = [float(np.median(seg))] * len(seg)
            continue
        cam = seg[0]
        for j, t in enumerate(seg):
            if abs(t - cam) > rc["deadzone"]:
                cam += (t - cam) * rc["smoothing"]
            cams[a + j] = cam

    # clamp so the crop stays inside the frame, then expand samples to every frame
    half = crop_w / 2
    cams = [min(max(c, half), 1 - half) for c in cams]
    sample_frames = [s["f"] for s in samples]
    hard = {samples[i]["f"] for i in bounds[1:-1]}
    centers = np.empty(total_frames)
    for k in range(len(samples)):
        f0 = sample_frames[k]
        f1 = sample_frames[k + 1] if k + 1 < len(samples) else total_frames
        c0 = cams[k]
        c1 = cams[k + 1] if k + 1 < len(samples) and f1 not in hard else c0
        n = f1 - f0
        centers[f0:f1] = np.linspace(c0, c1, n, endpoint=False) if n > 0 else c0
    centers[: sample_frames[0]] = cams[0]
    return {
        "centers": centers,
        "shots": len(bounds) - 1,
        "debug": {"samples": [{"f": s["f"], "cut": s["cut"], "switch": i in snaps, "faces": len(s["faces"]),
                               "act": [round(f["act"], 2) for f in s["faces"]],
                               "target": round(t, 3), "cam": round(c, 3)}
                              for i, (s, t, c) in enumerate(zip(samples, targets, cams))]},
    }


def _choose_targets(samples: list[dict], crop_w: float, sfps: float) -> tuple[list[float], set[int]]:
    """Pick the x position to frame for every sample.

    One face → that face.  Two faces that fit in the crop → frame both.
    Otherwise → the active speaker (most mouth motion over a ~1.5 s window), with hysteresis so the
    camera only switches when the other person clearly talks more; switches are hard cuts (multicam look).
    """
    win = max(2, int(sfps * 0.75))          # ± window for talking-activity smoothing
    min_hold = int(sfps * 1.5)              # minimum time on a speaker before switching again
    targets: list[float | None] = []
    snaps: set[int] = set()
    cur, held = None, 0

    def activity_near(i: int, cx: float) -> float:
        tot = 0.0
        for s in samples[max(0, i - win): i + win + 1]:
            if s["cut"] and s is not samples[i]:
                continue
            tot += sum(f["act"] for f in s["faces"] if abs(f["cx"] - cx) < 0.06)
        return tot

    for i, s in enumerate(samples):
        if s["cut"]:
            cur, held = None, min_hold
        held += 1
        faces = [f for f in s["faces"] if f["w"] >= 0.5 * max(x["w"] for x in s["faces"])] if s["faces"] else []
        if not faces:
            targets.append(cur)
            continue
        faces.sort(key=lambda f: f["w"] * f["conf"], reverse=True)
        if len(faces) >= 2:
            a, b = faces[0], faces[1]
            left = min(a["cx"] - a["w"] / 2, b["cx"] - b["w"] / 2)
            right = max(a["cx"] + a["w"] / 2, b["cx"] + b["w"] / 2)
            if right - left < crop_w * 0.9:
                cur = (left + right) / 2
                targets.append(cur)
                continue
        if len(faces) == 1:
            new = faces[0]["cx"]
        else:
            ranked = sorted(faces, key=lambda f: activity_near(i, f["cx"]), reverse=True)
            best = ranked[0]["cx"]
            if cur is None:
                new = best
            else:
                cur_face = min(faces, key=lambda f: abs(f["cx"] - cur))
                cur_act = activity_near(i, cur_face["cx"])
                best_act = activity_near(i, best)
                switch = abs(best - cur_face["cx"]) > 0.06 and best_act > cur_act * 1.35 + 0.5 and held >= min_hold
                new = best if switch else cur_face["cx"]
        if cur is not None and abs(new - cur) > crop_w * 0.5 and not s["cut"]:
            snaps.add(i)
            held = 0
        cur = new
        targets.append(cur)

    first = next((t for t in targets if t is not None), 0.5)
    return [first if t is None else t for t in targets], snaps


def _render_track(src: Path, out: Path, vi: dict, centers: np.ndarray, rc: dict, enc: dict) -> None:
    import cv2
    W, H = vi["width"], vi["height"]
    cw = int(round(H * 9 / 16)) // 2 * 2
    ff = subprocess.Popen(
        [require_bin("ffmpeg"), "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{cw}x{H}", "-r", f"{vi['fps']:.5f}", "-i", "-",
         "-i", str(src), "-map", "0:v", "-map", "1:a?",
         "-vf", f"scale={rc['width']}:{rc['height']}:flags=lanczos,setsar=1",
         "-c:v", "libx264", "-crf", str(enc["crf"]), "-preset", enc["preset"], "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-shortest", str(out)],
        stdin=subprocess.PIPE)
    cap = cv2.VideoCapture(str(src))
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            c = centers[min(i, len(centers) - 1)]
            x0 = int(round(c * W - cw / 2))
            x0 = max(0, min(W - cw, x0))
            ff.stdin.write(np.ascontiguousarray(frame[:, x0:x0 + cw]).tobytes())
            i += 1
    except BrokenPipeError:
        pass
    finally:
        cap.release()
        ff.stdin.close()
        if ff.wait() != 0:
            die("ffmpeg failed while writing the reframed video.")
