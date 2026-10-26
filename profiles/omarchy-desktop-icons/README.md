# Desktop icons — app icons on the wallpaper

<p align="center"><img src="docs/screenshot.png" alt="The desktop icon grid with its right-click menu open" width="520"></p>

App icons on your desktop, double-click to open — the thing you miss from
Windows. A Quickshell layer-shell surface that sits on the wallpaper, underneath
every window. It does **not** replace your bar, dock, wallpaper or theme; it
just adds icons.

Built by **Coding Colin** (Paperclip agent) for this desktop. Currently
**v1-rev4** (see `VERSION`; `omarchy-desktop-icons version` reports it).

## Install

Desktop Manager → Apps → **Utilities → Open** → **Desktop icons → Install**, or
`./install.sh`.

Requires **quickshell** (`yay -S quickshell`, or `quickshell-git` if that target
is not found) — the installer refuses to run without it. It copies the QML app to
`~/.local/share/omarchy-desktop-icons`, symlinks the `omarchy-desktop-icons`
wrapper into `~/.local/bin`, and drops a systemd **--user** unit into place
without enabling it.

Unlike the [App launcher](../omarchy-launcher) profile, this one **does not
touch your Hyprland config** — no keybinding and no autostart line are written
for you. Start it by hand first:

```bash
omarchy-desktop-icons          # start   (Ctrl+C or `omarchy-desktop-icons stop` to quit)
omarchy-desktop-icons toggle   # raise the same grid as a dimmed full-screen overlay
```

…then wire up autostart and (optionally) a toggle key yourself — step 4 and step
5 of **[APP-README.md](APP-README.md)** give both the Lua and the older `.conf`
form. `./uninstall.sh` removes everything it installed; add `--purge` to delete
your icon layout too.

## On this machine (Caelestia / end-4, not Omarchy)

v1 was developed and tested on **Hyprland 0.56.2 + end-4
illogical-impulse** — the rice behind the *illogical-impulse (end4)* card — so
that is the better-tested of its two targets. Three things differ from the
Omarchy instructions:

- **The first icon column lands under the end-4 bar**, which reserves roughly
  the left 506px. Set `geometry.margins.left` to about `560` in the config, or
  flip `geometry.anchor` to `"top-right"`.
- **`SUPER+I` is already end-4's Settings app** — use `SUPER+SHIFT+I` for the
  overlay toggle.
- **The `bottom` layer is shared with end-4's wallpaper surface and it works**
  (verified live), but only because Hyprland stacks by creation order within a
  layer. Start your shell first, the grid second.

Run it straight from this profile directory without installing anything:

```bash
qs -p profiles/omarchy-desktop-icons        # start
qs -p profiles/omarchy-desktop-icons kill   # stop
```

Quickshell identifies an instance by its config path, so that is a *separate*
instance from your Caelestia / end-4 shell. Never run a bare `qs kill` — it
would take your bar, dock and wallpaper with it.

## Use it

| Action | Result |
| --- | --- |
| double-click | open the app (single-click with `behaviour.activate: "single"`) |
| single click | select |
| drag | move the icon; snaps to the grid and is remembered |
| middle-click | open it on a fresh, empty workspace (needs `hyprctl`) |
| right-click wallpaper | **Add app…** · Icon size · Auto-arrange · **Settings…** · Reload config |
| right-click an icon | **Rename…** · **Remove "…"** · Icon size |

## Settings

<p align="center"><img src="docs/screenshot-settings.png" alt="The Settings dialog" width="420"></p>

Right-click the wallpaper → **Settings…**. Corner, edge spacing (one slider, or
four behind a disclosure), columns, monitor, icon size, single- vs double-click
to open, and where the labels go. Live — there is no OK button; each control
writes and saves as you move it, so the grid updates behind the dialog. `Esc`,
a click outside, or **Done** closes it.

This replaces the old **Edit config…** menu entry, which shelled out to
`$EDITOR`. That path still exists, one level down: **Settings… → Edit config
file…**, or `omarchy-desktop-icons edit`.

## Config

One hand-editable file, `~/.config/omarchy-desktop-icons/config.json`
(`config.example.json` here is the seed), and it stays the only source of
truth — Settings is a front end for it, not a replacement. Writes are atomic,
the file is watched, and a hand-edit made while the dialog is open moves the
dialog's controls instead of being clobbered by them. **Reload config** forces
a re-read. Menu colours follow the desktop theme, reading Omarchy's
`current/theme` first, then end-4's generated `material_colors.scss`, then
built-in defaults. Full schema, the control-to-key mapping, and the caveats —
one monitor only, drag-and-drop-to-add untested, keyboard focus limited to the
menu and dialogs — are in **[APP-README.md](APP-README.md)**.

## Files

- `bin/omarchy-desktop-icons` → `~/.local/bin/` — wrapper (no arg = start; `toggle` / `settings` / `open` / `close` / `reload` / `stop` / `status` / `edit`)
- `*.qml` → `~/.local/share/omarchy-desktop-icons/` — the Quickshell app
  (`shell.qml`, `IconGrid.qml`, `DesktopIcon.qml`, `ContextMenu.qml`,
  `AppPicker.qml`, `SettingsDialog.qml`, `TextPrompt.qml`, `Config.qml`,
  `Apps.qml`, `Theme.qml`)
- `packaging/omarchy-desktop-icons.service` → `~/.config/systemd/user/` — installed, not enabled
- `config.example.json` — seed for `~/.config/omarchy-desktop-icons/config.json`
- `VERSION` — the app revision, reported by `omarchy-desktop-icons version`
- `tests/run.sh` — offscreen behaviour tests for the Settings dialog and the icon layout (not installed; safe to run on a live desktop)
- `APP-README.md` — the app's own manual (installed as `README.md` alongside the app)
