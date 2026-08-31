#!/usr/bin/env python3
"""
Steady Mouse control panel (GTK4) for the tremor-filter daemon.
On/off switch + live sliders. Changes apply instantly (writes config + SIGHUP to daemon).
"""
import json, os, signal, subprocess, sys
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Gdk

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

# --- startup / tray / help --------------------------------------------------
TRAY      = f"{HOME}/.local/bin/tremor-tray.py"
LAUNCHER  = f"{HOME}/.local/bin/steady-autostart.py"
PREFS     = f"{HOME}/.config/tremor-filter/gui.json"
AUTOSTART = f"{HOME}/.config/autostart/steady-mouse.desktop"
DOCS_URL  = "https://github.com/janszafranski/desktop-manager/blob/master/profiles/steady-mouse/DOCUMENTATION.md"
PREF_DEFAULTS = {"autostart": True, "tray": True}

def load_prefs():
    p = dict(PREF_DEFAULTS)
    try:
        with open(PREFS) as f: p.update(json.load(f))
    except Exception: pass
    return p

def save_prefs(p):
    os.makedirs(os.path.dirname(PREFS), exist_ok=True)
    with open(PREFS, "w") as f: json.dump(p, f, indent=2)

def is_hyprland():
    d = f"{os.environ.get('XDG_CURRENT_DESKTOP','')}:{os.environ.get('DESKTOP_SESSION','')}".lower()
    if "hyprland" in d: return True
    try: return subprocess.run(["pgrep","-x","Hyprland"], capture_output=True).returncode == 0
    except Exception: return False

def set_xdg_autostart(enabled):
    """Non-Hyprland desktops: (de)register the launcher as XDG autostart.
    On Hyprland the launcher runs from hyprland.lua, so this is a no-op."""
    if is_hyprland(): return
    if enabled:
        os.makedirs(os.path.dirname(AUTOSTART), exist_ok=True)
        with open(AUTOSTART, "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Steady Mouse\n"
                    f"Exec=python3 {LAUNCHER}\nX-GNOME-Autostart-enabled=true\nNoDisplay=true\n")
    else:
        try: os.remove(AUTOSTART)
        except FileNotFoundError: pass

def tray_pid():
    for pid in os.listdir("/proc"):
        if not pid.isdigit(): continue
        try:
            with open(f"/proc/{pid}/cmdline") as f:
                if "tremor-tray.py" in f.read(): return int(pid)
        except Exception: pass
    return None

def start_tray():
    if tray_pid() is None:
        subprocess.Popen([sys.executable, TRAY], start_new_session=True,
                         stdout=open("/tmp/tremor-tray.log", "w"), stderr=subprocess.STDOUT)

def stop_tray():
    pid = tray_pid()
    if pid:
        try: os.kill(pid, signal.SIGTERM)
        except Exception: pass

def open_help(*_):
    subprocess.Popen(["xdg-open", DOCS_URL], start_new_session=True)

def switch_row(label_text, sub, active, handler):
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    lbl = Gtk.Label(); lbl.set_xalign(0.0); lbl.set_hexpand(True); lbl.set_wrap(True)
    lbl.set_markup(f"<b>{label_text}</b>\n<span alpha='60%' size='small'>{sub}</span>")
    sw = Gtk.Switch(); sw.set_valign(Gtk.Align.CENTER)
    sw.set_active(active); sw.connect("state-set", handler)
    row.append(lbl); row.append(sw)
    return row, sw

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
        self.prefs = load_prefs()
        if not os.path.exists(PREFS):        # first run — defaults ON, so enable both
            save_prefs(self.prefs)
            set_xdg_autostart(self.prefs.get("autostart", True))
            if self.prefs.get("tray", True): start_tray()
        win = Gtk.ApplicationWindow(application=self, title="Steady Mouse")
        win.set_default_size(460, 600)
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
        close = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close.set_valign(Gtk.Align.CENTER)
        close.add_css_class("flat")
        close.set_tooltip_text("Close")
        close.connect("clicked", lambda *_: win.close())
        head.append(close)
        box.append(head)
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

        # startup & tray options
        sep = Gtk.Separator(); sep.set_margin_top(4); box.append(sep)
        row1, self.sw_autostart = switch_row(
            "Launch at startup", "Run Steady Mouse automatically when you log in.",
            self.prefs.get("autostart", True), self.on_autostart)
        box.append(row1)
        row2, self.sw_tray = switch_row(
            "Show tray icon", "A mouse in the system tray — filled when on, outline when off.",
            self.prefs.get("tray", True), self.on_tray)
        box.append(row2)

        # Help — compact bordered box, right-aligned inline with the tip text
        help_css = Gtk.CssProvider()
        _css = ".sm-help{padding:1px 12px;min-height:0}"
        try: help_css.load_from_string(_css)
        except Exception:
            try: help_css.load_from_data(_css.encode())
            except Exception: pass
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), help_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        tip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tip_row.set_margin_top(4)
        hint = Gtk.Label(); hint.set_xalign(0.0); hint.set_wrap(True)
        hint.set_hexpand(True); hint.set_valign(Gtk.Align.CENTER)
        hint.set_markup("<span alpha='65%'>Tip: leave it ON while you slide — changes apply live. "
                        "SUPER+SHIFT+M also toggles it.</span>")
        help_btn = Gtk.Button(label="Help")
        help_btn.add_css_class("sm-help")
        help_btn.set_valign(Gtk.Align.CENTER)
        help_btn.set_tooltip_text("Open the full documentation")
        help_btn.connect("clicked", open_help)
        tip_row.append(hint); tip_row.append(help_btn)
        box.append(tip_row)

        GLib.timeout_add_seconds(1, self.poll)
        self.refresh_status()
        key = Gtk.EventControllerKey()
        key.connect("key-pressed",
                    lambda _c, kv, *_: win.close() if kv == Gdk.KEY_Escape else False)
        win.add_controller(key)
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

    def on_autostart(self, _sw, state):
        self.prefs["autostart"] = bool(state); save_prefs(self.prefs)
        set_xdg_autostart(bool(state))
        return False

    def on_tray(self, _sw, state):
        self.prefs["tray"] = bool(state); save_prefs(self.prefs)
        if state: start_tray()
        else: stop_tray()
        return False

    def refresh_status(self):
        on = daemon_pid() is not None
        self.syncing = True; self.switch.set_active(on); self.syncing = False
        return False

    def poll(self):
        self.refresh_status(); return True

if __name__ == "__main__":
    SteadyApp().run(None)
