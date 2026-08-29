#!/usr/bin/env python3
"""
Steady Mouse control panel (GTK4) for the tremor-filter daemon.
On/off switch + live sliders. Changes apply instantly (writes config + SIGHUP to daemon).
"""
import json, os, signal, subprocess, sys
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

HOME = os.path.expanduser("~")
DAEMON = f"{HOME}/.local/bin/tremor-filter.py"
CFG = f"{HOME}/.config/tremor-filter/config.json"
PIDFILE = f"{HOME}/.config/tremor-filter/pid"
DEFAULTS = {"smooth": 0.70, "beta": 0.40, "freeze": 90, "debounce": 60, "deadzone": 0.0}

def load_cfg():
    cfg = dict(DEFAULTS); cfg["device"] = ""
    try:
        with open(CFG) as f: cfg.update(json.load(f))
    except Exception: pass
    return cfg

def save_cfg(cfg):
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    with open(CFG, "w") as f: json.dump(cfg, f, indent=2)

def daemon_pid():
    try:
        pid = int(open(PIDFILE).read().strip())
        os.kill(pid, 0)                       # alive?
        with open(f"/proc/{pid}/cmdline") as f:
            if "tremor-filter.py" in f.read(): return pid
    except Exception: pass
    return None

def start_daemon():
    subprocess.Popen([sys.executable, DAEMON], start_new_session=True,
                     stdout=open("/tmp/tremor-filter.log", "w"), stderr=subprocess.STDOUT)

def stop_daemon():
    pid = daemon_pid()
    if pid:
        try: os.kill(pid, signal.SIGTERM)
        except Exception: pass

def signal_reload():
    pid = daemon_pid()
    if pid:
        try: os.kill(pid, signal.SIGHUP)
        except Exception: pass

SLIDERS = [
    # key,       label,               min, max,  step,  digits, suffix
    ("smooth",   "Smoothing",         0.0, 0.95, 0.05,  2,      "  (higher = steadier)"),
    ("beta",     "Responsiveness",    0.0, 1.5,  0.1,   1,      "  (lower = steadier / less wobble)"),
    ("freeze",   "Click freeze",      0,   250,  10,    0,      " ms  (hold still on click)"),
    ("debounce", "Double-click block",0,   150,  10,    0,      " ms  (ignore accidental re-clicks)"),
    ("deadzone", "Dead zone",         0.0, 3.0,  0.25,  2,      " px  (ignore tiny jitter)"),
]

class SteadyApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="ai.openclaw.steadymouse")
        self.syncing = False

    def do_activate(self):
        self.cfg = load_cfg()
        win = Gtk.ApplicationWindow(application=self, title="Steady Mouse")
        win.set_default_size(460, 520)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for m in ("top", "bottom", "start", "end"): getattr(box, f"set_margin_{m}")(20)
        win.set_child(box)

        # header: title + on/off switch
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title = Gtk.Label(); title.set_markup("<span size='xx-large' weight='bold'>Steady Mouse</span>")
        title.set_hexpand(True); title.set_xalign(0.0)
        self.switch = Gtk.Switch(); self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.set_active(daemon_pid() is not None)
        self.switch.connect("state-set", self.on_switch)
        head.append(title); head.append(self.switch)
        box.append(head)
        self.status = Gtk.Label(); self.status.set_xalign(0.0)
        box.append(self.status)
        box.append(Gtk.Separator())

        # sliders
        self.scales = {}
        for key, label, lo, hi, step, digits, suffix in SLIDERS:
            lbl = Gtk.Label(); lbl.set_xalign(0.0)
            lbl.set_markup(f"<b>{label}</b><span alpha='60%'>{suffix}</span>")
            box.append(lbl)
            sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
            sc.set_digits(digits); sc.set_draw_value(True); sc.set_value_pos(Gtk.PositionType.RIGHT)
            sc.set_hexpand(True); sc.set_size_request(-1, 44)
            sc.set_value(float(self.cfg.get(key, DEFAULTS[key])))
            sc.connect("value-changed", self.on_slide, key)
            self.scales[key] = sc
            box.append(sc)

        # reset
        btn = Gtk.Button(label="Reset to defaults"); btn.connect("clicked", self.on_reset)
        btn.set_margin_top(8); box.append(btn)

        hint = Gtk.Label(); hint.set_xalign(0.0); hint.set_wrap(True)
        hint.set_markup("<span alpha='65%'>Tip: leave it ON while you slide — changes apply live. "
                        "SUPER+SHIFT+M also toggles it.</span>")
        box.append(hint)

        GLib.timeout_add_seconds(1, self.poll)
        self.refresh_status()
        win.present()

    def on_switch(self, sw, state):
        if self.syncing: return False
        if state: start_daemon()
        else: stop_daemon()
        GLib.timeout_add(300, self.refresh_status)
        return False

    def on_slide(self, scale, key):
        val = scale.get_value()
        self.cfg[key] = round(val, 2) if key in ("smooth", "deadzone", "beta") else int(round(val))
        save_cfg(self.cfg)
        signal_reload()

    def on_reset(self, _btn):
        for key in DEFAULTS:
            self.cfg[key] = DEFAULTS[key]
            self.scales[key].set_value(float(DEFAULTS[key]))
        save_cfg(self.cfg); signal_reload()

    def refresh_status(self):
        on = daemon_pid() is not None
        self.syncing = True; self.switch.set_active(on); self.syncing = False
        self.status.set_markup(f"<span alpha='70%'>Status: <b>{'ON' if on else 'off'}</b></span>")
        return False

    def poll(self):
        self.refresh_status(); return True

if __name__ == "__main__":
    SteadyApp().run(None)
