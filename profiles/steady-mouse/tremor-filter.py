#!/usr/bin/env python3
"""
tremor-filter: a SteadyMouse-style hand-tremor filter for Linux / Wayland (Hyprland).

Reads a physical mouse via evdev, grabs it, emits a *filtered* virtual mouse via uinput.
Userspace (needs 'input' group). No root.

Motion filter = the One Euro Filter (Casiez et al.): an adaptive low-pass whose cutoff
rises with pointer speed. Slow/near-still motion is smoothed hard (cancels tremor and the
"stair-stepping" of naive smoothing); deliberate fast motion passes through with low lag.
Plus click-steadying (freeze on press) and click debounce.

Config: ~/.config/tremor-filter/config.json (smooth, freeze, debounce, deadzone, device)
Live tuning: edit config + SIGHUP (the GUI does this). Signals: TERM/INT=exit, HUP=reload, USR1=bypass.
"""
import argparse, json, math, os, signal, sys, time
import evdev
from evdev import ecodes as e, InputDevice, UInput

CONFIG = os.path.expanduser("~/.config/tremor-filter/config.json")
PIDFILE = os.path.expanduser("~/.config/tremor-filter/pid")
DEFAULTS = {"smooth": 0.70, "beta": 0.40, "freeze": 90, "debounce": 60, "deadzone": 0.0, "device": ""}

def log(*a): print("[tremor-filter]", *a, file=sys.stderr, flush=True)

def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG) as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except Exception: pass
    return cfg

def derive(cfg):
    s = max(0.0, min(0.95, float(cfg["smooth"])))
    # map the single "smooth" slider to One Euro params:
    #   smooth 0    -> mincutoff ~12 Hz  (barely smoothed, very responsive)
    #   smooth 0.55 -> mincutoff ~2.7 Hz (good tremor smoothing, low lag)
    #   smooth 0.95 -> mincutoff ~0.33 Hz (very heavy)
    return {
        "mincutoff": 0.3 + 12.0 * (1.0 - s) ** 2,
        # beta = speed coefficient. LOWER = steadier (tremor's own velocity won't unlock
        # the filter) but a touch more lag on fast moves; HIGHER = snappier but wobblier.
        "beta": max(0.0, float(cfg.get("beta", 0.4))),
        "dcutoff": 1.0,
        "freeze_s": max(0, int(cfg["freeze"])) / 1000.0,
        "debounce_s": max(0, int(cfg["debounce"])) / 1000.0,
        "dz": max(0.0, float(cfg["deadzone"])),
    }

class OneEuro:
    def __init__(self, mincutoff, beta, dcutoff):
        self.mincutoff, self.beta, self.dcutoff = mincutoff, beta, dcutoff
        self.x = None; self.dx = 0.0; self.t = None
    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)
    def reset_to(self, x, t):
        self.x = x; self.dx = 0.0; self.t = t
    def filt(self, x, t):
        if self.x is None:
            self.x = x; self.t = t; return x
        dt = t - self.t
        if dt <= 0: dt = 1e-3
        self.t = t
        dxdt = (x - self.x) / dt
        ad = self._alpha(self.dcutoff, dt)
        self.dx = ad * dxdt + (1 - ad) * self.dx
        cutoff = self.mincutoff + self.beta * abs(self.dx)
        a = self._alpha(cutoff, dt)
        self.x = a * x + (1 - a) * self.x
        return self.x

def find_mouse(preferred):
    if preferred and os.path.exists(preferred): return preferred
    best = None
    for path in evdev.list_devices():
        try: d = InputDevice(path)
        except Exception: continue
        caps = d.capabilities(); rel = caps.get(e.EV_REL, []); keys = caps.get(e.EV_KEY, [])
        if e.REL_X in rel and e.REL_Y in rel and e.BTN_LEFT in keys:
            if e.REL_WHEEL in rel: return path
            best = best or path
    return best

def build_uinput_caps(src):
    caps = src.capabilities(); out = {}
    if e.EV_REL in caps: out[e.EV_REL] = list(caps[e.EV_REL])
    if e.EV_KEY in caps: out[e.EV_KEY] = list(caps[e.EV_KEY])
    out.setdefault(e.EV_REL, [])
    for axis in (e.REL_X, e.REL_Y, e.REL_WHEEL):
        if axis not in out[e.EV_REL]: out[e.EV_REL].append(axis)
    out.setdefault(e.EV_KEY, [])
    for btn in (e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE):
        if btn not in out[e.EV_KEY]: out[e.EV_KEY].append(btn)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=None)
    ap.add_argument("--no-grab", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        for p in evdev.list_devices():
            try: d = InputDevice(p); print(f"{p}\t{d.name}")
            except Exception: pass
        return

    cfg = load_config()
    p = derive(cfg)
    # single instance: bow out if a live daemon already holds the pidfile
    try:
        old = int(open(PIDFILE).read().strip())
        os.kill(old, 0)
        with open(f"/proc/{old}/cmdline") as _f:
            if "tremor-filter" in _f.read():
                log(f"already running (pid {old}); exiting"); return
    except Exception:
        pass
    path = find_mouse(args.device or cfg.get("device"))
    if not path: log("no mouse found (try --list)"); sys.exit(1)
    dev = InputDevice(path); log(f"source: {path} ({dev.name})")
    ui = UInput(build_uinput_caps(dev), name="tremor-filter virtual mouse")
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        open(PIDFILE, "w").write(str(os.getpid()))
    except Exception: pass

    fx = OneEuro(p["mincutoff"], p["beta"], p["dcutoff"])
    fy = OneEuro(p["mincutoff"], p["beta"], p["dcutoff"])
    rx = ry = 0.0          # raw accumulated absolute position
    ex = ey = 0            # last emitted integer position
    dx = dy = 0.0          # per-report accumulators
    freeze_until = 0.0
    last_press = {}; drop_release = set()
    state = {"bypass": False}

    def stop(*_):
        try:
            if not args.no_grab: dev.ungrab()
        except Exception: pass
        try: ui.close()
        except Exception: pass
        os._exit(0)
    def reload(*_):
        p.update(derive(load_config()))
        fx.mincutoff = fy.mincutoff = p["mincutoff"]
        fx.beta = fy.beta = p["beta"]
        log("reloaded", {k: round(p[k], 3) for k in ("mincutoff", "beta", "freeze_s", "debounce_s", "dz")})
    def toggle(*_):
        state["bypass"] = not state["bypass"]; log("BYPASS" if state["bypass"] else "FILTERING")
    signal.signal(signal.SIGINT, stop); signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, reload); signal.signal(signal.SIGUSR1, toggle)

    if not args.no_grab: dev.grab(); log("mouse grabbed")
    else: log("NO-GRAB test mode")

    try:
        for ev in dev.read_loop():
            if ev.type == e.EV_REL:
                if ev.code == e.REL_X: dx += ev.value
                elif ev.code == e.REL_Y: dy += ev.value
                else: ui.write(e.EV_REL, ev.code, ev.value)
            elif ev.type == e.EV_KEY:
                btn, val, now = ev.code, ev.value, time.monotonic()
                if val == 1:
                    if now - last_press.get(btn, 0) < p["debounce_s"]:
                        drop_release.add(btn); continue
                    last_press[btn] = now; freeze_until = now + p["freeze_s"]
                    ui.write(e.EV_KEY, btn, 1)
                elif val == 0:
                    if btn in drop_release: drop_release.discard(btn); continue
                    ui.write(e.EV_KEY, btn, 0)
                else:
                    ui.write(e.EV_KEY, btn, val)
            elif ev.type == e.EV_SYN and ev.code == e.SYN_REPORT:
                t = ev.timestamp()
                if state["bypass"]:
                    ox, oy = int(dx), int(dy)
                    rx += dx; ry += dy; ex += ox; ey += oy
                    fx.reset_to(rx, t); fy.reset_to(ry, t)
                else:
                    if p["dz"] > 0 and math.hypot(dx, dy) < p["dz"]:
                        dx = dy = 0.0
                    if t < freeze_until:
                        # hold the pointer still through the click; keep filter at rest
                        fx.reset_to(rx, t); fy.reset_to(ry, t); ox = oy = 0
                    else:
                        rx += dx; ry += dy
                        sx = fx.filt(rx, t); sy = fy.filt(ry, t)
                        nx = int(round(sx)); ny = int(round(sy))
                        ox = nx - ex; oy = ny - ey
                        ex = nx; ey = ny
                if ox: ui.write(e.EV_REL, e.REL_X, ox)
                if oy: ui.write(e.EV_REL, e.REL_Y, oy)
                ui.syn()
                dx = dy = 0.0
    except OSError as ex_:
        log("device error:", ex_)
    finally:
        try:
            if not args.no_grab: dev.ungrab()
        except Exception: pass
        ui.close(); log("stopped, mouse restored")

if __name__ == "__main__":
    main()
