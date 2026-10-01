"""End-to-end test of the alert path: synthetic boat tracks -> beep events."""
import os, sys, math, random, types
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from boat_watch import Track

OPTS = types.SimpleNamespace(stop_seconds=6.0, move_threshold=0.12,
                             min_track_seconds=2.0, repeat_seconds=20.0,
                             alert_static=False)

def run(name, path, seconds=45, fps=15.0, opts=OPTS, started_before=True):
    random.seed(1)
    tr = Track(1, 0.0)
    if not started_before:      # entered frame after startup grace
        tr.has_moved = True
    events = []
    for i in range(int(seconds*fps)):
        t = i/fps
        tr.update(path(t), t, opts.stop_seconds)
        ev, drift = tr.evaluate(opts)
        if ev:
            events.append((ev, round(t, 1)))
    print(f"{name:34s} {events}")
    return events

J = lambda: random.uniform(-3, 3)
box = lambda x, y=200: (x+J(), y+J(), x+120+J(), y+60+J())

e = run("passing straight through", lambda t: box(20 + t*30))
assert e == [], e

e = run("arrives at 8s, then parks", lambda t: box(20 + min(t,8.0)*30))
assert [x[0] for x in e] == ["stopped", "still"], e   # stop, then a repeat at +20s
assert 12 < e[0][1] < 16, e
assert abs((e[1][1] - e[0][1]) - OPTS.repeat_seconds) < 0.5, e

e = run("parked since startup (ignored)", lambda t: box(300))
assert e == [], e

o = types.SimpleNamespace(**{**OPTS.__dict__, "alert_static": True})
e = run("parked since startup (--alert-static)", lambda t: box(300), opts=o)
assert e and e[0][0] == "stopped", e

e = run("stops at 5s, leaves at 25s",
        lambda t: box(20 + min(t,5.0)*30 + max(0.0, t-25.0)*30))
# leaves before the 20s repeat is due, so: stop then move-off
assert [x[0] for x in e] == ["stopped", "moving"], e
assert e[1][1] > 25.0, e

e = run("anchored, bobbing on swell",
        lambda t: box(20 + min(t,6.0)*30 + math.sin(t*2)*4, 200 + math.sin(t*3)*3))
assert e and e[0][0] == "stopped", e

o = types.SimpleNamespace(**{**OPTS.__dict__, "repeat_seconds": 0.0})
e = run("stopped, --repeat-seconds 0", lambda t: box(20 + min(t,8.0)*30), opts=o)
assert [x[0] for x in e] == ["stopped"], e

print("\nall assertions passed")
