# system-replica

A self-contained snapshot of this machine's **look & configuration**, plus
scripts to reproduce it on a fresh **CachyOS / Arch** install.

Base setup captured: KDE Plasma 6 (Wayland) with the **Nordic / Nordic-bluish**
theme, **Krohnkite** tiling, **Alacritty** (Nord), **Fish** + Zsh (CachyOS
configs), **Micro** (Catppuccin), and the GTK/Qt theming to match.

## Layout

```
system-replica/
├── scripts/
│   ├── manifest.sh   # single source of truth: what gets backed up / restored
│   ├── collect.sh    # system  -> repo  (re-run to refresh this snapshot)
│   └── install.sh    # repo    -> system (deploy onto a fresh machine)
├── packages/
│   ├── pacman-native.txt         # explicit repo packages
│   ├── aur.txt                   # AUR / foreign packages
│   └── user-services-enabled.txt # enabled systemd --user units
└── files/            # the actual bundled config + themes
    ├── home/         -> $HOME            (.bashrc, .zshrc, .gtkrc-2.0, …)
    ├── config/       -> ~/.config        (fish, alacritty, micro, KDE rc files…)
    ├── local-share/  -> ~/.local/share   (Nordic icon themes, color-schemes,
    │                                       aurorae, kwin scripts, wallpapers)
    ├── icons/        -> ~/.icons         (Nordic-cursors)
    └── bin/          -> ~/bin            (small helper scripts)
```

The Nordic GTK/icon/cursor themes, the Plasma *look-and-feel*, the Aurorae
window decoration, and the Krohnkite / UltrawideWindows KWin scripts are **not
in any package repo** on this system, so they are bundled here directly.

## Restore on a fresh install

```bash
git clone <your-remote> ~/system-replica    # or copy the folder over
cd ~/system-replica

./scripts/install.sh --dry-run   # preview everything, change nothing
./scripts/install.sh             # packages + files + services
```

### GUI (KDE / any desktop)

Prefer clicking? `scripts/gui.sh` opens a graphical picker: choose a desktop
configuration and which stages to run (with a Dry-run option), then it launches
the work in a terminal window (so `sudo` prompts and live output work).

```bash
./scripts/gui.sh                 # run the picker now
./scripts/install-launcher.sh    # add "System Replica" to your app menu
```

It uses the best available toolkit, in order:

1. **GTK** (`gui_gtk.py`, via `python-gobject`) — a titled window with an intro,
   a preview thumbnail and a grid of configuration cards. Preferred.
2. **yad** — single window with the preview image + checkboxes.
3. **kdialog / zenity** — plain checklist, no image.

The preview image comes from `preview.png` in the repo root (a desktop
screenshot); it's auto-cropped to 16:9 and scaled for the dialog. Replace that
file to change the preview.

> **TODO — float the GUI window on tiling setups.** On KDE + Krohnkite the
> window still gets tiled. The app sets a `DIALOG` type hint and a stable
> `system-replica` WM_CLASS, and we added `System Replica` to Krohnkite's
> `floatingTitle` (in the bundled `kwinrc`), but that didn't take on Wayland.
> Next thing to try: add the `system-replica` **class** to Krohnkite's
> `ignoreClass`, or ship a KWin window rule (force-float + size + center).

Or run a single stage:

```bash
./scripts/install.sh packages    # sudo pacman + yay/paru from packages/*.txt
./scripts/install.sh files       # deploy configs & themes
./scripts/install.sh services    # enable systemd --user units
```

Existing files are **backed up** to `~/.config-backup-<timestamp>/` before being
overwritten — nothing is destroyed silently.

After the `files` stage: **log out and back in** (or restart Plasma) so KWin,
the color scheme, and GTK/Qt theming reload.

## Refresh the snapshot from the current machine

```bash
./scripts/collect.sh                          # updates files/ + package lists
REPLICA_INCLUDE_PICTURES=1 ./scripts/collect.sh   # also bundle ~/Pictures/Wallpapers (~48MB)
git -C ~/system-replica add -A && git commit -m "refresh snapshot"
```

## What is deliberately NOT included

- Heavy per-machine app state: browsers (Zen/Firefox/Brave/LibreWolf/Chromium),
  Teams, LibreOffice, VS Code, GIMP/Krita caches. These aren't "the look" and
  are large / machine-specific.
- The 162MB `~/bin/pandoc` binary — install it with `sudo pacman -S pandoc-cli`.
- Secrets / credentials.

## Manual notes (things a script can't fully carry over)

- **SDDM Nordic login theme** comes from the AUR pkg `sddm-nordic-theme-git`
  (in `aur.txt`); select it in *System Settings → Login Screen (SDDM)*.
- **KWin tiling (Krohnkite):** after install, enable it in
  *System Settings → Window Management → KWin Scripts*.
- **libinput-gestures** needs the `libinput-gestures` package running:
  `libinput-gestures-setup autostart start`.
- **Fish/Zsh** source CachyOS's shared configs
  (`cachyos-fish-config` / `cachyos-zsh-config` packages — in the native list).
- Activities, per-activity wallpapers and desktop applet layout live in the
  bundled `plasma-org.kde.plasma.desktop-appletsrc` / `plasmarc`, but Plasma
  sometimes needs a re-login before they render correctly.

## To edit what gets captured

Everything is driven by the arrays in `scripts/manifest.sh`. Add/remove paths
there and both `collect.sh` and `install.sh` follow automatically.
