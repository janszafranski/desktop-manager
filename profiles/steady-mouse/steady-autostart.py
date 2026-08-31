#!/usr/bin/env python3
"""
Shakefree Mouse startup launcher — invoked once at login (from Hyprland's
hyprland.lua, or XDG autostart on other desktops). It reads the GUI prefs
and starts the pieces the user has enabled:

  • the tremor-filter daemon   — if "autostart" (Launch at startup) is on
  • the tray applet            — if "tray" (Show tray icon) is on

Both flags default ON. The daemon and tray are each single-instance guarded,
so running this more than once is harmless.
"""
import json, os, subprocess, sys

HOME  = os.path.expanduser("~")
PREFS = f"{HOME}/.config/tremor-filter/gui.json"
DAEMON = f"{HOME}/.local/bin/tremor-filter.py"
TRAY   = f"{HOME}/.local/bin/tremor-tray.py"

prefs = {"autostart": True, "tray": True}
try:
    with open(PREFS) as f:
        prefs.update(json.load(f))
except Exception:
    pass


def proc_running(needle):
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        try:
            with open(f"/proc/{pid}/cmdline") as f:
                if needle in f.read():
                    return True
        except Exception:
            pass
    return False


def launch(path, log):
    subprocess.Popen([sys.executable, path], start_new_session=True,
                     stdout=open(log, "w"), stderr=subprocess.STDOUT)


if prefs.get("autostart", True) and not proc_running("tremor-filter.py"):
    launch(DAEMON, "/tmp/tremor-filter.log")

if prefs.get("tray", True) and not proc_running("tremor-tray.py"):
    launch(TRAY, "/tmp/tremor-tray.log")
