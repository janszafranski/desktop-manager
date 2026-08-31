#!/usr/bin/env python3
"""
Steady Mouse tray applet — persistent system-tray (StatusNotifierItem) indicator
for the tremor-filter daemon.

Icon: a small mouse — FILLED WHITE when the filter is ON, OUTLINE (empty) when OFF.
Runs as its own process (GTK3 + Ayatana AppIndicator) because the control panel
is GTK4 and the two toolkits can't share a process.

Menu: toggle the filter, open Settings (the GTK4 panel), Help, Quit (tray only).
"""
import os, signal, subprocess, sys
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, GLib, AyatanaAppIndicator3 as AppIndicator3

HOME    = os.path.expanduser("~")
DAEMON  = f"{HOME}/.local/bin/tremor-filter.py"
GUI     = f"{HOME}/.local/bin/tremor-gui.py"
PIDFILE = f"{HOME}/.config/tremor-filter/pid"
ICONDIR = f"{HOME}/.local/share/steady-mouse/icons"
HELP_LOCAL = f"{HOME}/.local/share/steady-mouse/help.html"
DOCS_URL = "https://github.com/janszafranski/desktop-manager/blob/master/profiles/steady-mouse/DOCUMENTATION.md"
ICON_ON, ICON_OFF = "steady-mouse-on", "steady-mouse-off"


def daemon_pid():
    """Return the live daemon PID, or None."""
    try:
        pid = int(open(PIDFILE).read().strip())
        os.kill(pid, 0)
        with open(f"/proc/{pid}/cmdline") as f:
            if "tremor-filter.py" in f.read():
                return pid
    except Exception:
        pass
    return None


def start_daemon():
    subprocess.Popen([sys.executable, DAEMON], start_new_session=True,
                     stdout=open("/tmp/tremor-filter.log", "w"), stderr=subprocess.STDOUT)


def stop_daemon():
    pid = daemon_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass


class Tray:
    def __init__(self):
        self.ind = AppIndicator3.Indicator.new_with_path(
            "steady-mouse", ICON_ON,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS, ICONDIR)
        self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.ind.set_title("Steady Mouse")

        self.menu = Gtk.Menu()
        self.item_toggle = Gtk.CheckMenuItem(label="Steady Mouse active")
        self.item_toggle.connect("toggled", self.on_toggle)
        self.menu.append(self.item_toggle)
        self.menu.append(Gtk.SeparatorMenuItem())

        item_settings = Gtk.MenuItem(label="Settings…")
        item_settings.connect("activate", lambda *_: self.launch(GUI))
        self.menu.append(item_settings)

        item_help = Gtk.MenuItem(label="Help")
        item_help.connect("activate", lambda *_: self.open_help())
        self.menu.append(item_help)

        self.menu.append(Gtk.SeparatorMenuItem())
        item_quit = Gtk.MenuItem(label="Quit tray")
        item_quit.connect("activate", lambda *_: Gtk.main_quit())
        self.menu.append(item_quit)

        self.menu.show_all()
        self.ind.set_menu(self.menu)
        # secondary action (middle-click on hosts that support it) toggles
        self.ind.set_secondary_activate_target(self.item_toggle)

        self._syncing = False
        self._last = None
        self.refresh()
        GLib.timeout_add_seconds(2, self.refresh)

    def on_toggle(self, item):
        if self._syncing:
            return
        if item.get_active():
            if daemon_pid() is None:
                start_daemon()
        else:
            stop_daemon()
        GLib.timeout_add(300, self.refresh)

    def refresh(self):
        on = daemon_pid() is not None
        if on != self._last:
            self.ind.set_icon_full(ICON_ON if on else ICON_OFF,
                                   "Steady Mouse " + ("on" if on else "off"))
            self._last = on
        self._syncing = True
        self.item_toggle.set_active(on)
        self.item_toggle.set_label("Steady Mouse active" if on else "Steady Mouse off")
        self._syncing = False
        return True

    def launch(self, path):
        try:
            subprocess.Popen([sys.executable, path], start_new_session=True)
        except Exception:
            pass

    def open_help(self):
        target = HELP_LOCAL if os.path.exists(HELP_LOCAL) else DOCS_URL
        try:
            subprocess.Popen(["xdg-open", target], start_new_session=True)
        except Exception:
            pass


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    Tray()
    Gtk.main()
