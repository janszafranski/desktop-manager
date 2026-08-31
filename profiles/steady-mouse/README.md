# Steady Mouse — hand-tremor mouse filter

A SteadyMouse-style tremor filter for Linux — works on **any desktop** (X11 or
Wayland, KDE or Hyprland), because it filters at the input layer. Runs in
userspace (no root): it grabs the physical mouse via `evdev`, applies an
adaptive **One Euro** low-pass filter (smooths tremor at slow speeds, stays
low-lag on deliberate moves) plus click-steadying, and emits a filtered virtual
mouse via `uinput`. On Hyprland it adds a Super+Shift+M toggle + autostart; on
KDE/GNOME/other it uses XDG autostart (bind the toggle in your DE's settings).

## Install
Via the Desktop Manager GUI → **Steady Mouse** card → *Install the app*, or:
```bash
./install.sh
```
Requires membership of the **`input`** group (for `/dev/uinput` + `/dev/input`):
`sudo usermod -aG input "$USER"` then log out/in.

## Use
- **Launch panel:** app menu → "Steady Mouse" (or run `tremor-gui.py`)
- **Toggle on/off:** `Super+Shift+M`, the panel switch, or the tray icon
- **Tray icon:** a mouse in the system tray — **filled = on, outline = off**;
  click it to toggle, open Settings, or Help
- **Tune:** the panel's sliders — *Smoothing*, *Responsiveness* (lower = steadier),
  *Click freeze*, *Double-click block*, *Dead zone*. Changes apply live.
- **Startup & tray toggles** (panel, both **on** by default): *Launch at startup*
  and *Show tray icon*.
- **Help:** the **?** button (bottom-right of the panel, or the tray menu) opens
  the [full documentation](DOCUMENTATION.md).

## Files
| file | role |
|------|------|
| `tremor-filter.py`   | the evdev→uinput daemon (One Euro filter, click-steadying) |
| `tremor-gui.py`      | GTK4 control panel (on/off, sliders, startup + tray toggles, help) |
| `tremor-tray.py`     | GTK3 + Ayatana AppIndicator tray icon (filled/outline mouse) |
| `steady-autostart.py`| login launcher — starts daemon + tray per the GUI toggles |
| `steady-toggle.sh`   | start/stop toggle (bound to Super+Shift+M) |
| `steady-mouse.desktop` | app-launcher entry |
| `config.json`        | daemon defaults (device empty = auto-detect) |
| `gui.json`           | GUI prefs — `autostart` / `tray` (both default true) |
| `assets/icons/`      | tray icons (`steady-mouse-on/off.{svg,png}`) |
| `DOCUMENTATION.md`   | full user documentation (opened by the **?** help button) |

The tray icon needs **`libayatana-appindicator`** (Arch) /
`gir1.2-ayatanaappindicator3-0.1` (Debian). Without it the app still works —
just no tray icon.

Config lives at `~/.config/tremor-filter/config.json`; the daemon hot-reloads it
on `SIGHUP` (the GUI does this on every slider change).
