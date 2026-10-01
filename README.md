# Boat Watch

Watches a video feed and **beeps when a boat stops in frame**.

- A boat sitting in view: nothing.
- A boat crossing the frame and carrying on: nothing.
- A boat that comes to a halt and stays put: beep.

Two versions, same detection logic:

| | Chrome app | Terminal app |
|---|---|---|
| Start it | double-click **Boat Watch.app** | `.venv/bin/python boat_watch.py --show` |
| Camera permission | Chrome asks, once | needs Terminal added to System Settings → Camera |
| Detector | COCO-SSD (TensorFlow.js) | YOLOv8 (Ultralytics) |
| Accuracy | good | better, especially on small/distant boats |

---

## Chrome version (just double-click)

Double-click **Boat Watch.app**. It starts a tiny local server and opens the page in
Chrome. Pick a source, press **Start**, and allow the camera when Chrome asks.

First launch takes 20–30 seconds to download the detector (about 6 MB) and needs an
internet connection; after that it is cached and starts immediately. Video never
leaves the machine — detection runs inside the page.

If the app bundle will not open, double-click `start.command` instead, or serve the
folder yourself:

```bash
cd web && python3 -m http.server 8777 --bind 127.0.0.1
```

then visit http://localhost:8777/.

### Switching the input

The **Input** dropdown covers three kinds of source, and you can switch while it runs:

- **Any camera** — built-in, USB webcams, or an iPhone (see below). Names fill in once
  you have allowed access once; press **↻** to rescan.
- **Screen or window…** — point it at a harbour webcam stream, a video call, or
  anything else playing on screen.
- **Video file…** — pick a clip off disk and it analyses that instead.

**Mirror the image** flips the picture for a front-facing camera; leave it off for a
camera pointed at water.

### Using your iPhone as the camera

macOS hides the iPhone from *browsers* unless the phone is in Apple's "magic pose".
This is an Apple privacy restriction, not a bug in this app — it stops a web page
grabbing a phone camera you did not mean to share. All five must be true at once:

- landscape orientation
- screen off and locked
- resting still, not in your hand
- rear camera unobstructed
- near the Mac, with Wi-Fi and Bluetooth on

Prop it in a stand, lock it, leave it alone, then press **↻** next to the Input list.
Once it connects **you can pick the phone up and move it freely** — the pose is only
needed to make the initial connection.

If it still never appears, some Chrome builds miss Continuity Camera even in the pose
([Chromium issue 436126054](https://issues.chromium.org/issues/436126054)). Safari
detects it reliably: double-click **Boat Watch (Safari).app** instead. The page and
the beeping work identically there.

As a last resort the terminal version talks to the camera directly through macOS and
is not subject to the browser restriction — `--source 1` is usually the iPhone.

### Controls

| Control | Default | What it does |
|---|---|---|
| Look for | boat | Also person / car / truck / bird — `person` is the easy indoor test |
| Confidence threshold | 0.35 | Lower it for small or distant boats |
| Hold still for | 6 s | How long a boat must stay put before it counts as stopped |
| Movement allowed while stopped | 0.12 | As a fraction of the boat's own size |
| Re-beep every | 60 s | Reminder while a boat stays stopped (0 = beep once) |
| Also beep for boats already parked | off | Include boats that were static from the start |
| Sound on | on | Turn off to log and flash only |

### Testing it without a boat

Set **Look for** to `person`, **Hold still for** to 5, press Start, walk into frame,
and stand still — it should beep at you.

---

## How "stopped" is decided

Each detected boat gets a tracked id, and two questions decide the beep. Both are
measured against the boat's own on-screen size, so a distant boat and a close one are
judged the same way and detector jitter does not read as movement.

- **Has it moved?** The total spread of its centre across the whole track. A boat that
  appears after startup counts as having moved — it got there somehow.
- **Is it stopped now?** How far the centre wandered over the last "hold still for"
  window. Under the movement threshold means it is holding position → beep.

A boat already parked in frame when you start is ignored until it moves, unless you
switch that on.

---

## Terminal version (optional, not set up by default)

Better detector (YOLOv8), same behaviour, useful if you want it running headless.
It needs about 730 MB of Python libraries, so it is not installed unless you ask for it:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Then:

```bash
.venv/bin/python boat_watch.py --show
```

macOS will refuse the camera until the app you launch it from — Terminal, iTerm — is
ticked under System Settings → Privacy & Security → Camera. Quit and reopen that app
after ticking it.

Useful flags: `--source` (camera index or a video file), `--class-name person` for an
indoor test, `--stop-seconds`, `--move-threshold`, `--repeat-seconds`, `--alert-static`,
`--conf`, `--model yolov8s.pt` for better accuracy, `--quiet`, `--every N` to cut CPU.
`--help` lists them all.

---

## Tests

Both versions run the stop/go logic against the same synthetic tracks — a boat passing
through, one arriving and parking, one bobbing at anchor, one that stops then leaves —
with no camera needed:

```bash
.venv/bin/python test_boat_watch.py
```

(needs the terminal version set up first). For the browser version, open http://localhost:8777/?selftest=1 while the server runs.

---

## Files

- `web/index.html` — the whole Chrome app, one file
- `Boat Watch.app` — launcher, opens in Chrome
- `Boat Watch (Safari).app` — same, but opens in Safari (use this for the iPhone camera)
- `start.command` — plain-shell fallback launcher
- `launcher.applescript`, `launcher-safari.applescript` — sources for the app bundles

Keep the launchers next to the `web` folder; the whole folder can be moved anywhere.
- `boat_watch.py` — the terminal version
- `test_boat_watch.py` — logic tests for the terminal version
