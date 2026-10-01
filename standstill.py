#!/usr/bin/env python3
"""Watch a video feed and beep when something stops in frame.

Looks for boats by default (--class-name picks person, car, truck, bird...).
A boat that is simply present does nothing. A boat that crosses the frame and
keeps going does nothing. A boat that comes to a halt and stays put triggers a
beep.

Usage:
    python standstill.py --show
    python standstill.py --stop-seconds 8 --move-threshold 0.10
"""

import argparse
import collections
import math
import shutil
import subprocess
import sys
import threading
import time

DEFAULT_SOUND = "/System/Library/Sounds/Submarine.aiff"


# --------------------------------------------------------------------------
# Beeping
# --------------------------------------------------------------------------
class Beeper:
    """Plays an alert sound without blocking the capture loop."""

    def __init__(self, sound_path=DEFAULT_SOUND, quiet=False):
        self.sound_path = sound_path
        self.quiet = quiet
        self.afplay = shutil.which("afplay")
        self._lock = threading.Lock()
        self._playing = False

    def beep(self, times=2):
        if self.quiet:
            return
        with self._lock:
            if self._playing:
                return
            self._playing = True
        threading.Thread(target=self._play, args=(times,), daemon=True).start()

    def _play(self, times):
        try:
            for i in range(times):
                if self.afplay:
                    subprocess.run(
                        [self.afplay, self.sound_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                    time.sleep(0.4)
                if i + 1 < times:
                    time.sleep(0.15)
        finally:
            with self._lock:
                self._playing = False


# --------------------------------------------------------------------------
# Per-boat motion bookkeeping
# --------------------------------------------------------------------------
class Track:
    """Position history for one tracked boat, plus its moved/stopped state."""

    def __init__(self, track_id, now):
        self.id = track_id
        self.first_seen = now
        self.last_seen = now
        self.history = collections.deque()  # (t, cx, cy, diag)
        # Running bounds of every centre this track has ever had, used to tell
        # whether the boat has genuinely travelled or only jittered in place.
        self.min_x = self.max_x = None
        self.min_y = self.max_y = None
        self.max_diag = 1.0
        self.has_moved = False
        self.is_stopped = False
        self.stopped_since = None
        self.last_alert = None

    def update(self, box, now, window):
        x1, y1, x2, y2 = box
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        diag = max(math.hypot(x2 - x1, y2 - y1), 1.0)

        self.last_seen = now
        self.max_diag = max(self.max_diag, diag)
        self.history.append((now, cx, cy, diag))
        while len(self.history) > 2 and now - self.history[0][0] > window * 1.5:
            self.history.popleft()

        if self.min_x is None:
            self.min_x = self.max_x = cx
            self.min_y = self.max_y = cy
        else:
            self.min_x, self.max_x = min(self.min_x, cx), max(self.max_x, cx)
            self.min_y, self.max_y = min(self.min_y, cy), max(self.max_y, cy)

        travel = math.hypot(self.max_x - self.min_x, self.max_y - self.min_y)
        if travel / self.max_diag > 0.8:
            self.has_moved = True

    @property
    def age(self):
        return self.last_seen - self.first_seen

    def evaluate(self, opts):
        """Classify this track's current state, updating its stop bookkeeping.

        Returns (event, drift) where event is one of:
          'stopped' - it just came to a halt (beep)
          'still'   - it is still stopped and due for a repeat beep
          'moving'  - it was stopped and has started moving again
          None      - nothing worth reporting
        """
        now = self.last_seen
        drift = self.wander(opts.stop_seconds)
        if drift is None:
            return None, None

        if drift <= opts.move_threshold:
            if self.age < opts.min_track_seconds:
                return None, drift
            if not (self.has_moved or opts.alert_static):
                return None, drift
            if not self.is_stopped:
                self.is_stopped = True
                self.stopped_since = now
                self.last_alert = now
                return "stopped", drift
            if opts.repeat_seconds > 0 and now - self.last_alert >= opts.repeat_seconds:
                self.last_alert = now
                return "still", drift
            return None, drift

        was_stopped = self.is_stopped
        self.is_stopped = False
        self.stopped_since = None
        return ("moving" if was_stopped else None), drift

    def wander(self, window):
        """Radius the centre has wandered in the last `window` seconds,
        as a fraction of the boat's own size. None if history is too short."""
        now = self.last_seen
        pts = [p for p in self.history if now - p[0] <= window]
        if len(pts) < 3 or now - pts[0][0] < window * 0.8:
            return None
        cxs = [p[1] for p in pts]
        cys = [p[2] for p in pts]
        mid_x = (min(cxs) + max(cxs)) / 2.0
        mid_y = (min(cys) + max(cys)) / 2.0
        radius = max(math.hypot(x - mid_x, y - mid_y) for x, y in zip(cxs, cys))
        diag = sum(p[3] for p in pts) / len(pts)
        return radius / max(diag, 1.0)


# --------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Beep when something (a boat, by default) stops in the camera frame.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--source",
        default="0",
        help="camera index (0, 1, ...) or a path/URL to a video to analyse instead",
    )
    p.add_argument("--model", default="yolov8n.pt", help="YOLO weights (auto-downloaded)")
    p.add_argument("--device", default="auto", help="auto | cpu | mps | 0")
    p.add_argument("--imgsz", type=int, default=640, help="inference image size")
    p.add_argument("--conf", type=float, default=0.35, help="detection confidence threshold")
    p.add_argument(
        "--class-name",
        default="boat",
        help="COCO class to watch for (use e.g. 'person' to test indoors)",
    )
    p.add_argument(
        "--stop-seconds",
        type=float,
        default=6.0,
        help="how long a boat must hold still before it counts as stopped",
    )
    p.add_argument(
        "--move-threshold",
        type=float,
        default=0.12,
        help="motion allowance while 'stopped', as a fraction of the boat's size",
    )
    p.add_argument(
        "--min-track-seconds",
        type=float,
        default=2.0,
        help="ignore tracks younger than this (filters detection flicker)",
    )
    p.add_argument(
        "--repeat-seconds",
        type=float,
        default=60.0,
        help="re-beep for a boat still stopped after this long (0 = beep once)",
    )
    p.add_argument(
        "--startup-grace",
        type=float,
        default=4.0,
        help="boats already parked in frame at startup are ignored until they move",
    )
    p.add_argument(
        "--alert-static",
        action="store_true",
        help="also beep for boats that were already sitting still at startup",
    )
    p.add_argument("--sound", default=DEFAULT_SOUND, help="alert sound file")
    p.add_argument("--quiet", action="store_true", help="log only, never play a sound")
    p.add_argument("--show", action="store_true", help="open a preview window")
    p.add_argument("--every", type=int, default=1, help="run detection on every Nth frame")
    return p.parse_args()


def pick_device(requested):
    if requested != "auto":
        return requested
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "0"
    except Exception:
        pass
    return "cpu"


def stamp():
    return time.strftime("%H:%M:%S")


def main():
    args = parse_args()

    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        sys.exit(
            f"Missing dependency ({exc.name}). Install with:\n"
            "    python3 -m venv .venv && source .venv/bin/activate\n"
            "    pip install -r requirements.txt"
        )

    device = pick_device(args.device)
    print(f"[{stamp()}] loading {args.model} on {device} ...")
    model = YOLO(args.model)

    names = model.names
    wanted = {i for i, n in names.items() if n == args.class_name}
    if not wanted:
        sys.exit(f"Model has no class named {args.class_name!r}. Known: {sorted(set(names.values()))}")

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        if isinstance(source, int):
            sys.exit(
                f"Could not open camera {source}. On macOS, grant Camera access to "
                "your terminal app in System Settings > Privacy & Security > Camera, "
                "then run this again."
            )
        sys.exit(f"Could not open video source {source!r}.")

    print(
        f"[{stamp()}] watching for '{args.class_name}' — beeping when one holds still "
        f"for {args.stop_seconds:g}s. Ctrl-C to quit."
    )

    beeper = Beeper(args.sound, quiet=args.quiet)
    tracks = {}
    started = time.time()
    frame_no = 0
    last_boxes = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print(f"[{stamp()}] no more frames; stopping.")
                break
            frame_no += 1
            now = time.time()

            if frame_no % max(args.every, 1) == 0:
                results = model.track(
                    frame,
                    persist=True,
                    classes=sorted(wanted),
                    conf=args.conf,
                    imgsz=args.imgsz,
                    device=device,
                    tracker="bytetrack.yaml",
                    verbose=False,
                )[0]

                seen = set()
                last_boxes = []
                boxes = results.boxes
                if boxes is not None and boxes.id is not None:
                    xyxy = boxes.xyxy.cpu().numpy()
                    ids = boxes.id.int().cpu().tolist()
                    confs = boxes.conf.cpu().tolist()
                    for box, tid, cf in zip(xyxy, ids, confs):
                        seen.add(tid)
                        track = tracks.get(tid)
                        if track is None:
                            track = Track(tid, now)
                            tracks[tid] = track
                            # A boat that shows up after startup got there by
                            # moving, so it is a candidate for "stopped" alerts.
                            if now - started > args.startup_grace:
                                track.has_moved = True
                        track.update(box, now, args.stop_seconds)

                        event, drift = track.evaluate(args)
                        if event == "stopped":
                            label = args.class_name.upper()
                            print(
                                f"[{stamp()}] {label} STOPPED  id={tid} "
                                f"conf={cf:.2f} drift={drift:.3f}"
                            )
                            beeper.beep()
                        elif event == "still":
                            held = now - track.stopped_since
                            print(f"[{stamp()}] still stopped  id={tid} for {held:.0f}s")
                            beeper.beep(times=1)
                        elif event == "moving":
                            print(f"[{stamp()}] moving again   id={tid}")

                        last_boxes.append((box, tid, track.is_stopped, cf))

                stale = [t for t, tr in tracks.items()
                         if t not in seen and is_stale(tr, now, args.stop_seconds)]
                for t in stale:
                    tracks.pop(t, None)

            if args.show:
                for box, tid, stopped, cf in last_boxes:
                    x1, y1, x2, y2 = (int(v) for v in box)
                    color = (0, 0, 255) if stopped else (0, 200, 0)
                    label = f"#{tid} {'STOPPED' if stopped else args.class_name} {cf:.2f}"
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        frame, label, (x1, max(y1 - 8, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
                    )
                cv2.imshow("standstill", frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
    except KeyboardInterrupt:
        print(f"\n[{stamp()}] stopped.")
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()


def is_stale(track, now, window):
    """Forget a track we have not seen for a while, so ids do not pile up."""
    return now - track.last_seen > max(window * 2, 10.0)


if __name__ == "__main__":
    main()
