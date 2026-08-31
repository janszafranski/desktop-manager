# Steady Mouse — Full Documentation

<p align="center"><img src="https://raw.githubusercontent.com/janszafranski/desktop-manager/master/profiles/steady-mouse/assets/screenshot.png" alt="Steady Mouse control panel" width="380"></p>

A hand‑tremor mouse filter for **Linux**. Steady Mouse smooths shaky pointer
motion and steadies clicks, so people with hand tremor (essential tremor,
Parkinson's, MS, cerebral palsy, RSI, or just a caffeine‑jittery day) can point
and click accurately. It is the spiritual counterpart of the well‑known Windows
app **SteadyMouse** — the same idea, rebuilt natively for Linux. This is an
independent open‑source project; it is **not** the Windows program and shares no
code with it.

- **Works on any desktop** — X11 or Wayland, Hyprland, KDE, GNOME, anything —
  because it filters at the **input layer**, below the windowing system.
- **No root** — runs entirely in userspace (it only needs your user to be in the
  `input` group).
- **Live tuning** — every setting applies instantly while you move the mouse.

---

## Table of contents

1. [How it works](#how-it-works)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Permissions](#permissions)
5. [Turning it on and off](#turning-it-on-and-off)
6. [The tray icon](#the-tray-icon)
7. [Startup & tray toggles](#startup--tray-toggles)
8. [The settings, in depth](#the-settings-in-depth)
9. [Tuning guide](#tuning-guide)
10. [The config file](#the-config-file)
11. [Troubleshooting](#troubleshooting)
12. [Uninstall](#uninstall)
13. [How it compares to SteadyMouse (Windows)](#how-it-compares-to-steadymouse-windows)
14. [Technical appendix](#technical-appendix)

---

## How it works

Steady Mouse grabs your physical mouse via **evdev** (`/dev/input`), runs the
motion through an adaptive filter, and emits a *new*, smoothed virtual mouse via
**uinput**. The compositor sees only the smoothed pointer.

The core is a **One Euro filter** — an adaptive low‑pass filter designed for
noisy human input. Its trick is that the amount of smoothing depends on speed:

- **Slow / near‑still motion** (where tremor lives) is smoothed **hard**, so
  shake and the "stair‑stepping" of naive smoothing are cancelled.
- **Deliberate fast motion** passes through with **very low lag**, so the pointer
  still feels responsive and doesn't "swim" behind your hand.

On top of that, **click‑steadying** briefly freezes the pointer around a click so
a wobble on press doesn't drag the cursor, and a **debounce** suppresses
accidental double‑clicks caused by tremor on the button.

Because it works on the raw input device, it filters **every** application and
the whole desktop uniformly — no per‑app support needed.

---

## Requirements

- Linux with `uinput` available (standard on all modern kernels).
- **python‑evdev** (`python-evdev` / installed automatically to the user site by
  the installer if missing).
- Membership of the **`input`** group (see [Permissions](#permissions)).
- Optional, for the tray icon: **`libayatana-appindicator`** and its GObject
  typelib.

---

## Installation

Via the Desktop Manager GUI → **Steady Mouse** card → *Install the app*, or from
this folder:

```bash
./install.sh
```

The installer is desktop‑aware:

- **Hyprland** — adds a `Super+Shift+M` toggle, a float rule for the panel, and
  an autostart entry, all in `~/.config/hypr/hyprland.lua`.
- **KDE / GNOME / other** — installs an XDG autostart entry and points you at
  your DE's keyboard‑shortcut settings to bind the toggle.

---

## Permissions

Steady Mouse needs read access to `/dev/input/*` and write access to
`/dev/uinput`. Both are owned by the **`input`** group:

```bash
sudo usermod -aG input "$USER"
```

Then **log out and back in** for the new group to take effect. Until you do, the
daemon can't grab the mouse and will exit with a permission error.

---

## Turning it on and off

There are four equivalent ways:

| Method | Where |
|--------|-------|
| The main switch | top‑right of the control panel |
| The tray icon | click it → **Steady Mouse active** |
| Keyboard | `Super+Shift+M` (Hyprland; bind your own on other DEs) |
| Command line | `~/.local/bin/steady-toggle.sh` |

The filter starts and stops instantly; nothing needs a restart.

---

## The tray icon

When enabled, Steady Mouse shows a small **mouse** in your system tray:

- **Filled (solid white)** — the filter is **ON**.
- **Outline (empty)** — the filter is **OFF**.

Clicking it opens a menu: toggle the filter, open **Settings…** (the panel),
open **Help** (this document), or **Quit tray** (removes the icon without
stopping the filter).

The tray icon is a separate lightweight process (`tremor-tray.py`) using the
Ayatana AppIndicator / StatusNotifierItem protocol, so it works in any tray that
supports the freedesktop SNI standard.

---

## Startup & tray toggles

Two switches in the control panel, **both ON by default**:

- **Launch at startup** — run Steady Mouse automatically when you log in.
- **Show tray icon** — show (or hide) the tray mouse.

These are remembered in `~/.config/tremor-filter/gui.json` and honoured by the
login launcher (`steady-autostart.py`), which starts the daemon and/or tray to
match your choices.

---

## The settings, in depth

All five live sliders apply immediately. Higher smoothing = steadier but a touch
more lag; lower = snappier but less tremor removed. Find the balance that suits
your hand.

### Smoothing
**Higher = steadier.** This sets how aggressively slow motion is filtered. Raise
it if the pointer still shakes when you're trying to hold still or move slowly;
lower it if the pointer feels laggy or "floaty" on deliberate moves. This is the
main dial — set it first.

### Responsiveness
**Lower = steadier / less wobble.** This controls how quickly the filter "opens
up" as you speed up. Low values keep heavy smoothing even during moderate
movement (very steady, slightly more lag). High values hand back control quickly
(snappier, but small mid‑move wobble can leak through). If fast moves feel
sluggish, raise it; if they feel wobbly, lower it.

### Click freeze (ms)
Holds the pointer **still for this many milliseconds around a click**, so a
tremor on press or release can't drag the cursor or start an accidental
selection. Raise it if clicks slip or drag; lower it (or zero) if it feels like
the pointer "sticks" when you click‑and‑drag intentionally.

### Double‑click block (ms)
**Ignores accidental re‑clicks** within this window — a tremor that taps the
button twice in quick succession is treated as one click. Raise it if you get
unwanted double‑clicks; lower it if intentional double‑clicks are being
swallowed.

### Dead zone (px)
**Ignores sub‑pixel jitter** below this many pixels, so the pointer sits
perfectly still when you're not really moving it. A small value (0.5–1 px)
removes idle shimmer; too high and slow, deliberate nudges get eaten.

---

## Tuning guide

A reasonable starting point for noticeable tremor:

| Setting | Start at | Then… |
|---------|----------|-------|
| Smoothing | ~0.7 | raise if still shaky, lower if laggy |
| Responsiveness | ~0.4 | raise for snappier, lower for steadier |
| Click freeze | ~90 ms | raise if clicks slip |
| Double‑click block | ~60 ms | raise if you get accidental double‑clicks |
| Dead zone | ~0.5 px | raise if the idle pointer shimmers |

Leave the filter **ON while you slide** — changes apply live, so you can feel the
effect immediately and dial it in. Use **Reset to defaults** to start over.

---

## The config file

Settings live in `~/.config/tremor-filter/config.json`:

```json
{
  "smooth": 0.70,
  "beta": 0.40,
  "freeze": 90,
  "debounce": 60,
  "deadzone": 0.0,
  "device": ""
}
```

- `device` empty = **auto‑detect** the mouse. To pin a specific device (e.g. if
  auto‑detect picks the wrong one), set it to a path from
  `/dev/input/by-id/…`.
- The daemon **hot‑reloads** the file on `SIGHUP` (the GUI sends this on every
  change), so edits apply without a restart.

GUI/startup preferences live separately in
`~/.config/tremor-filter/gui.json` (`autostart`, `tray`).

---

## Troubleshooting

**Nothing is being filtered.**
Check you're in the `input` group (`id -nG | grep input`) and have logged out/in
since. Check the daemon is running: `pgrep -af tremor-filter`. Read the log at
`/tmp/tremor-filter.log`.

**It's filtering the wrong device** (or a tablet/touchpad).
Set `device` in `config.json` to the correct `/dev/input/by-id/…` path and
toggle off/on.

**No tray icon.**
The tray needs `libayatana-appindicator` and its typelib
(`gir1.2-ayatanaappindicator3-0.1` on Debian/Ubuntu). Without it the rest of the
app still works — you just won't get the icon. Also confirm your desktop has a
system tray / StatusNotifier host running.

**The pointer feels laggy.**
Lower **Smoothing** and/or raise **Responsiveness**.

**Clicks still slip / drag.**
Raise **Click freeze**.

---

## Uninstall

```bash
./uninstall.sh
```

Removes the app files, the tray, the icons, and the desktop integration. Your
tuning in `~/.config/tremor-filter/` is kept unless you delete it yourself.

---

## How it compares to SteadyMouse (Windows)

SteadyMouse (steadymouse.com) is a mature Windows application that pioneered
approachable tremor filtering, including motion smoothing, click steadying, and
"warp" assistance. Steady Mouse for Linux is an **independent reimplementation of
the same *ideas*** — motion smoothing (via a One Euro filter), click freeze, and
double‑click suppression — built natively on evdev/uinput. It does not use
SteadyMouse's code and is not affiliated with it; credit for popularising the
concept goes to that project.

---

## Technical appendix

| File | Role |
|------|------|
| `tremor-filter.py` | the evdev→uinput daemon (One Euro filter, click‑steadying) |
| `tremor-gui.py` | GTK4 control panel (on/off, sliders, startup + tray toggles, help) |
| `tremor-tray.py` | GTK3 + Ayatana AppIndicator tray icon |
| `steady-autostart.py` | login launcher — starts daemon + tray per the toggles |
| `steady-toggle.sh` | start/stop toggle (bound to `Super+Shift+M`) |
| `config.json` | daemon tuning (device empty = auto‑detect) |
| `gui.json` | GUI prefs — `autostart`, `tray` |

**Signals to the daemon:** `TERM`/`INT` = exit, `HUP` = reload config,
`USR1` = bypass (pass the mouse through unfiltered).
