# mic-fixer — microphone checker

Pick a microphone, record a short test clip, watch a live level meter and
waveform, play it back, and get a plain verdict on what is wrong with it (too
quiet, clipping, dead channel, wrong device, and so on). Built for PipeWire.

Built by **Coding Colin** (Paperclip agent) for this desktop.

Two builds install side by side — use whichever you like:

- **Mic Fixer** — native **GTK4 / libadwaita** window, audio via **GStreamer**
  (`pulsesrc ! audioconvert ! appsink` into a numpy buffer, so the numbers on
  screen are the numbers in the recorded WAV). No browser. Command: `mic-fixer`.
- **Mic Fixer (browser)** — the same tool as an HTML page, served over
  `http://127.0.0.1` to a Chromium **app window** (Chromium refuses microphone
  access on `file://`). The local server lives only for the life of the window.
  Command: `mic-fixer-web`.

## Install

Desktop Manager → Apps → **Mic Fixer → Install**, or `./install.sh`.

Deploys to `~/.local/bin` (the two `mic-fixer` / `mic-fixer-web` launchers),
`~/.local/share/mic-fixer{,-web}` (the payloads), and `~/.local/share/applications`
(the two menu entries). `./uninstall.sh` reverses it; `./uninstall.sh --purge`
also drops the browser build's saved mic-permission profile.

## Requirements

- **Native build:** `python`, `python-gobject` (PyGObject), `gtk4`, `libadwaita`,
  `gstreamer` + `gst-plugins-good`, `python-numpy`.
- **Browser build:** `python` and any Chromium-family browser (chromium, brave,
  chrome, edge, vivaldi). Falls back to the default browser if none is found.

The installer warns about anything missing rather than failing.

## Command-line use

The native build also runs headless, through the same capture/analysis path as
the GUI:

```sh
mic-fixer --list-devices                 # real capture sources, one per line
mic-fixer --probe [--device N] [--seconds S] [--json] [--wav PATH]
```

In the window: **Ctrl+R** record/stop, **Ctrl+P** play/pause, **Ctrl+D**/**F5**
re-scan devices, **Ctrl+Q** quit. Those are GApplication actions, so they are
also reachable over the session bus (`gdbus call --dest dev.jan.MicFixer …`).

`mic-fixer-web --url` prints the URL it would serve and exits. Env overrides:
`MIC_FIXER_PORT`, `MIC_FIXER_BROWSER`, `MIC_FIXER_APP_DIR`, `MIC_FIXER_APP`.

## Files

- `mic-fixer` → `~/.local/bin/` — native launcher (execs `mic-fixer.py`)
- `mic-fixer.py` → `~/.local/share/mic-fixer/` — the native GTK4 app
- `mic-fixer-web` → `~/.local/bin/` — browser launcher (serves + opens an app window)
- `web/mic-fixer.html`, `web/serve.py` → `~/.local/share/mic-fixer-web/` — the browser build
- `mic-fixer.desktop`, `mic-fixer-web.desktop` → `~/.local/share/applications/` — menu entries

## In the app launcher

Both entries are filed under the **Utilities** folder in `omarchy-launcher`'s
`categories.json`, and excluded from the auto-filled Media/All-Apps lists, so
they live in one place instead of scattering across the launcher.
