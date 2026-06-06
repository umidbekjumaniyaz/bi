import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

DEFAULT_SOURCE = "https://www.youtube.com/live/6dp-bvQ7RWo?si=44fxPf_rSiDNAYIw"
MAX_RETRIES = 5
TARGET_CLASS_NAME = "car"
STATS_FILE = Path("stats.json")
HISTORY_FILE = Path("history.json")
STATS_EVERY = 30                  # write stats every N frames
MAX_HISTORY_POINTS = 100          # keep last 100 data points for BI charts

MOVE_STEP = 0.01   # fraction per keypress
TILT_STEP = 0.02   # tilt fraction per keypress


# ── Diagonal Counter Line ─────────────────────────────────────────────────────

@dataclass
class CounterLine:
    """
    Diagonal counter line defined by two endpoints (frame fractions).
    Crossing is detected via signed area (cross product) — works for any angle.

    Default coordinates match the red diagonal line in the Shinjuku camera:
      bottom point ≈ (48%, 90%) → top point ≈ (82%, 40%)
    """
    x1_frac: float = 0.48   # bottom/left endpoint X
    y1_frac: float = 0.90   # bottom/left endpoint Y
    x2_frac: float = 0.82   # top/right endpoint X
    y2_frac: float = 0.40   # top/right endpoint Y
    count:   int   = 0

    _sides: dict = field(default_factory=dict)

    # ── geometry ──────────────────────────────────────────────────────────────
    def endpoints(self, w: int, h: int) -> tuple[tuple[int, int], tuple[int, int]]:
        p1 = (int(self.x1_frac * w), int(self.y1_frac * h))
        p2 = (int(self.x2_frac * w), int(self.y2_frac * h))
        return p1, p2

    # ── controls ─────────────────────────────────────────────────────────────
    def move(self, dx: float = 0.0, dy: float = 0.0) -> None:
        """Translate entire line."""
        self.x1_frac = max(0.0, min(1.0, self.x1_frac + dx))
        self.x2_frac = max(0.0, min(1.0, self.x2_frac + dx))
        self.y1_frac = max(0.0, min(1.0, self.y1_frac + dy))
        self.y2_frac = max(0.0, min(1.0, self.y2_frac + dy))

    def tilt(self, delta: float) -> None:
        """Rotate around midpoint: bottom goes up/down, top goes opposite."""
        self.y1_frac = max(0.0, min(1.0, self.y1_frac + delta))
        self.y2_frac = max(0.0, min(1.0, self.y2_frac - delta))

    def reset(self) -> None:
        self.count = 0
        self._sides.clear()

    # ── crossing detection ────────────────────────────────────────────────────
    @staticmethod
    def _signed_area(px: int, py: int,
                     x1: int, y1: int, x2: int, y2: int) -> float:
        return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)

    def check_crossing(self, track_id: int,
                       cx: int, cy: int, w: int, h: int) -> bool:
        (x1, y1), (x2, y2) = self.endpoints(w, h)
        sign = self._signed_area(cx, cy, x1, y1, x2, y2)
        side = "pos" if sign >= 0 else "neg"
        prev = self._sides.get(track_id)
        self._sides[track_id] = side
        if prev is not None and prev != side:
            self.count += 1
            return True
        return False

    def cleanup(self, active_ids: set[int]) -> None:
        for tid in list(self._sides):
            if tid not in active_ids:
                del self._sides[tid]

    # ── drawing ───────────────────────────────────────────────────────────────
    def draw(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        (x1, y1), (x2, y2) = self.endpoints(w, h)

        cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 255), 3)
        cv2.circle(frame, (x1, y1), 8, (0, 180, 255), -1)
        cv2.circle(frame, (x2, y2), 8, (0, 180, 255), -1)

        # Counter badge at midpoint
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        label = f"  Cars: {self.count}  "
        font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2
        (tw, th), _ = cv2.getTextSize(label, font, scale, thick)
        tx, ty = mx - tw // 2, my - 18
        cv2.rectangle(frame, (tx - 4, ty - th - 4), (tx + tw + 4, ty + 6),
                      (0, 0, 0), -1)
        cv2.putText(frame, label, (tx, ty), font, scale, (0, 255, 255), thick)


# ── Help overlay ──────────────────────────────────────────────────────────────

HELP_LINES = [
    "W / S   - move line up / down",
    "A / D   - move line left / right",
    "[  / ]  - tilt (rotate line)",
    "R       - reset counter",
    "Q       - quit",
]

def draw_help(frame: np.ndarray, cars_in_scene: int) -> None:
    cv2.rectangle(frame, (6, 6), (235, 36), (0, 0, 0), -1)
    cv2.putText(frame, f"Cars in frame: {cars_in_scene}", (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
    for i, text in enumerate(HELP_LINES):
        cv2.putText(frame, text, (10, 58 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)


# ── Video opener ──────────────────────────────────────────────────────────────

def is_local(source: str) -> bool:
    return not source.startswith(("https://", "http://", "rtsp://", "rtmp://"))


def open_stream(source: str, cookies: str | None, attempt: int) -> cv2.VideoCapture:
    if is_local(source):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path.resolve()}")
        print(f"[INFO] Opening local file: {path.name}")
    else:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
        print(f"[INFO] Connecting to stream (attempt {attempt})…")
        opts = {"format": "best[height<=720]/best", "quiet": True, "no_warnings": True}
        if cookies:
            opts["cookiesfrombrowser"] = (cookies,)
        try:
            with YoutubeDL(opts) as dl:
                meta = dl.extract_info(source, download=False)
        except DownloadError as exc:
            raise RuntimeError("YouTube stream could not be resolved.") from exc
        if not meta or "url" not in meta:
            raise RuntimeError("Could not extract stream URL.")
        source = meta["url"]

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {source}")
    return cap


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Car counter with diagonal crossing line.")
    p.add_argument("--source",     default=DEFAULT_SOURCE)
    p.add_argument("--model",      default="best.pt")
    p.add_argument("--confidence", type=float, default=0.25)
    p.add_argument("--iou",        type=float, default=0.45)
    p.add_argument("--imgsz",      type=int,   default=1280)
    p.add_argument("--frame-skip", type=int,   default=1)
    p.add_argument("--loop",       action="store_true",
                   help="Loop local video when it ends")
    # Line endpoints as fractions (0–1) of frame size
    p.add_argument("--x1", type=float, default=0.48, help="Line start X (default 0.48)")
    p.add_argument("--y1", type=float, default=0.90, help="Line start Y (default 0.90)")
    p.add_argument("--x2", type=float, default=0.82, help="Line end X   (default 0.82)")
    p.add_argument("--y2", type=float, default=0.40, help="Line end Y   (default 0.40)")
    p.add_argument("--cookies-from-browser",
                   choices=["brave", "chrome", "chromium",
                            "edge", "firefox", "opera", "safari"])
    return p.parse_args()


def resolve_target_class_id(model: YOLO) -> int:
    for class_id, name in model.names.items():
        if str(name).lower() == TARGET_CLASS_NAME:
            return int(class_id)
    raise RuntimeError(f"Model does not contain a '{TARGET_CLASS_NAME}' class: {model.names}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # Try to load YOLO model
    try:
        model = YOLO(args.model)
    except:
        print(f"[WARN] Could not load {args.model}, falling back to yolov8n.pt")
        model = YOLO("yolov8n.pt")

    target_class_id = resolve_target_class_id(model)
    print(f"[INFO] Model classes : {model.names}")
    print(f"[INFO] Tracking class: {target_class_id} -> '{model.names[target_class_id]}'")
    print("[INFO] Vehicle Traffic Monitoring Active.")

    line = CounterLine(
        x1_frac=args.x1, y1_frac=args.y1,
        x2_frac=args.x2, y2_frac=args.y2,
    )

    local = is_local(args.source)
    retry = 0
    history_data = []

    while True:
        try:
            video = open_stream(args.source, args.cookies_from_browser, retry + 1)
        except Exception as exc:
            if local:
                print(f"[ERROR] {exc}")
                break
            retry += 1
            if retry > MAX_RETRIES:
                print("[ERROR] Max reconnect attempts reached.")
                break
            wait = min(5 * retry, 30)
            print(f"[ERROR] {exc}  Retrying in {wait}s…")
            time.sleep(wait)
            continue

        if not local:
            retry = 0

        frame_num = 0
        last_annotated: np.ndarray | None = None
        cars_in_scene: int = 0
        print("[INFO] Video opened.  Press 'q' to quit.")

        while True:
            ok, frame = video.read()
            if not ok:
                video.release()
                if local:
                    if args.loop:
                        print("[INFO] Video ended — looping…")
                        line._sides.clear()
                        break
                    else:
                        print(f"[INFO] Video ended. Total Cars: {line.count}")
                        cv2.destroyAllWindows()
                        return
                else:
                    print("[WARN] Stream dropped — reconnecting…")
                    time.sleep(3)
                    break

            h, w = frame.shape[:2]
            frame_num += 1

            if frame_num % args.frame_skip == 0:
                result = model.track(
                    source=frame,
                    classes=[target_class_id],
                    conf=args.confidence,
                    iou=args.iou,
                    imgsz=args.imgsz,
                    persist=True,
                    verbose=False,
                )[0]

                last_annotated = result.plot(conf=False, line_width=2)

                boxes = result.boxes
                cars_in_scene = len(boxes) if boxes else 0
                if boxes.id is not None:
                    active_ids: set[int] = set()
                    for box, tid in zip(boxes.xyxy, boxes.id.int().tolist()):
                        cx = int((box[0] + box[2]) / 2)
                        cy = int((box[1] + box[3]) / 2)
                        active_ids.add(tid)
                        if line.check_crossing(tid, cx, cy, w, h):
                            print(f"[COUNT] Car #{tid} crossed! Total: {line.count}")
                    line.cleanup(active_ids)

                # ── Write stats and history for BI ───────────────────────────
                if frame_num % STATS_EVERY == 0:
                    ts = datetime.now(timezone.utc).isoformat()
                    _write_stats(line.count, cars_in_scene, frame_num, args.source)
                    
                    history_data.append({"time": ts, "count": cars_in_scene, "crossed": line.count})
                    if len(history_data) > MAX_HISTORY_POINTS:
                        history_data.pop(0)
                    try:
                        HISTORY_FILE.write_text(json.dumps(history_data))
                    except: pass

            display = (last_annotated if last_annotated is not None else frame).copy()
            line.draw(display)
            draw_help(display, cars_in_scene)
            cv2.imshow("Vehicle Traffic Monitor", display)

            key = cv2.waitKey(1) & 0xFF
            if   key == ord("q"):
                video.release()
                cv2.destroyAllWindows()
                return
            elif key == ord("w"):  line.move(dy=-MOVE_STEP)
            elif key == ord("s"):  line.move(dy=+MOVE_STEP)
            elif key == ord("a"):  line.move(dx=-MOVE_STEP)
            elif key == ord("d"):  line.move(dx=+MOVE_STEP)
            elif key == ord("["):  line.tilt(+TILT_STEP)
            elif key == ord("]"):  line.tilt(-TILT_STEP)
            elif key == ord("r"):
                line.reset()
                print("[INFO] Counter reset.")
                _write_stats(0, cars_in_scene, frame_num, args.source)

    cv2.destroyAllWindows()
    _write_stats(line.count, 0, 0, "", stopped=True)


# ── Stats writer ──────────────────────────────────────────────────────────────

def _write_stats(crossed: int, in_scene: int, frame: int,
                 source: str, stopped: bool = False) -> None:
    """Write live stats to stats.json so the chatbot can read them."""
    data = {
        "crossed":   crossed,
        "in_scene":  in_scene,
        "frame":     frame,
        "source":    source,
        "object_label": "car",
        "stopped":   stopped,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        STATS_FILE.write_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass   # never crash the main loop for stats


if __name__ == "__main__":
    main()
