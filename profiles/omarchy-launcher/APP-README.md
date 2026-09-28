# omarchy-launcher

An Omarchy-style categorised application launcher for this Caelestia / Hyprland desktop:
a centred, **narrow portrait popup** — one column, one line per app, tight rows, a selection
pill barely lighter than the card, no footer. It opens on **Favourites** — that is the default
view.

Categories are *not* a second pane and *not* a separate menu you have to summon. Following
Omarchy's **root-menu pattern**, they are the first rows of the one list — drawn as folders
with a count and a chevron — and under a hairline come the apps of the default category:

```
  Home            19 ›
  Work            18 ›
  Church          14 ›     <- folders: every category except the default one
  …
  All Apps       168 ›
  ─────────────────────
  Gmail                    <- the rest of the root list *is* Favourites
  Proton Mail
  …
```

Open a folder and its apps replace the rows under the same search line; walk back out and you
land on the folder you came from. The default category (Favourites) has no folder of its own,
because at root you are already standing in it. The search placeholder doubles as the
breadcrumb — `Apps…` at root, the category name once you are inside one.

## Using it

| Key | Action |
| --- | --- |
| `Super + Space` | open / close the launcher (primary) |
| `Super + Alt + Space` | same — the original bind, kept |
| type | search the current level |
| `↑` `↓` / `PgUp` `PgDn` | move the selection |
| `Ctrl + Home` | jump to the top of the list |
| `Enter` | launch the app — or, on a folder row, open that category |
| `→` | open the folder under the selection |
| `←` / `Backspace` (empty search) | walk back out to root |
| `Tab` / `Shift+Tab` | inside a folder: next / previous category. At root: hop down the folder block |
| `Ctrl + ←` `→` | next / previous category |
| `Alt + 1…9` | open the Nth folder from anywhere |
| `Esc` | clear the search → walk back out to root → close |
| click outside | close |

`Super + Shift + Space` is now Caelestia's own launcher, which moved off `Super + Space`.

Searching a category that has no match automatically widens to **all apps** and says so, so a
typo'd category never leaves you at a dead end.

## Categories

Everything about the categories lives in `~/.config/omarchy-launcher/categories.json`
(`omarchy-launcher edit` opens it). The file is watched — save it and the next open picks the
change up, no restart.

```json
{
  "id": "church",              // unique key
  "name": "Church",            // label in the category list
  "icon": "church",            // any Material Symbols Rounded name
  "apps": ["libreoffice-impress", "com.obsproject.Studio"],
  "xdgCategories": ["Office"], // optional: auto-include by freedesktop category
  "exclude": ["some-app"]      // optional: keep something out of the auto-fill
}
```

- `apps` are desktop-entry ids **in the order you want them displayed** — this is what makes
  Favourites a hand-ranked list rather than an alphabetical dump. Matching is case-insensitive.
- `xdgCategories` entries are appended after the explicit ones, alphabetically. Use it for
  categories that should pick up newly installed apps on their own (Development, System, …).
- `"all": true` means every installed application (that's how *All Apps* works).
- `defaultCategory` at the top of the file decides the opening view.

A desktop id is the `.desktop` filename without the extension:

```sh
ls /usr/share/applications ~/.local/share/applications \
   /var/lib/flatpak/exports/share/applications
```

Every shipped list was seeded from the apps actually installed on this machine, and every id in
them resolves — the counts on the folder rows are the proof. They're a starting point, not a
guess you have to live with.

### Opening one folder directly

```sh
qs -c omarchy-launcher ipc call launcher category media
```

Categories are addressable now that they're real rows, so a folder can have its own keybind —
e.g. `Super+Alt+M` straight into Media, with the search line already live. An unknown id just
opens at root rather than failing shut.

### Flatpak apps

Hyprland leaves `XDG_DATA_DIRS` unset here, so Quickshell's desktop-entry index fell back to
the spec default (`/usr/local/share:/usr/share`) and **all 16 Flatpak-exported apps were
invisible** — Bitwarden, Proton Pass, Proton VPN, Synology Drive, Simple Scan, Déjà Dup,
Yakuake, Upscaler, Video Downloader and friends, several of which `categories.json` names. The
wrapper now appends `/var/lib/flatpak/exports/share` and `~/.local/share/flatpak/exports/share`
for the daemon it starts, which took *All Apps* from 152 to 168. The login session's own
environment is deliberately left alone.

## How it's wired up

- **UI**: `~/.config/quickshell/omarchy-launcher/shell.qml` — its own Quickshell instance.
- **Control**: `~/.local/bin/omarchy-launcher` — `toggle` (default), `open`, `close`,
  `restart` (after editing the QML), `edit`, `daemon`. It also fixes up `XDG_DATA_DIRS` for the
  daemon so Flatpak apps are indexed (see above). IPC adds `category <id>`.
- **Keybind + autostart**: `~/.config/hypr/hyprland.lua` — `Super+Alt+Space`, plus an
  `omarchy-launcher daemon` line in the `hyprland.start` block so the desktop-entry index is
  warm before the first keypress.
- **Size**: portrait at roughly 1:2.1 (470 × 988 on this 3440×1440 display), derived from the
  screen rather than pinned — `height = min(screenH × 0.78, 1160) × uiScale`,
  `width = height / 2.1` clamped to 360…620 (also × `uiScale`). Rows are 38 px with 22 px icons.
  **One knob:** `readonly property real uiScale` on the `card` item (currently `0.88`; `1.0` is
  the original 535 × 1123). Everything — card, rows, icons, margins, type — derives from it, so
  resizing the launcher is a one-digit edit followed by `omarchy-launcher restart`. Two curves
  come off it: `mScale` (geometry, shrinks almost in step with the card) and `fScale` (type,
  shrinks half as much) so the names stay legible as the box comes down.
- **Theme**: read live from Caelestia's generated scheme at
  `~/.local/state/caelestia/scheme.json`, so wallpaper recolours, `blacken.sh` and light/dark
  flips are picked up without touching this config. Fonts follow Caelestia's bundled
  Google Sans Flex when present. The selection pill and the card border are *derived* from that
  scheme (a ~7.5% `onSurface` wash over `surfaceContainer`, and a half-opacity `outline`), so
  they stay a whisper in both light and dark instead of being hard-coded.

It is deliberately **not** a patch to `caelestia-shell`: that ships as a pacman package under
`/etc/xdg/quickshell/caelestia`, so any edit there is destroyed by the next `pacman -Syu`.
This config only reads Caelestia's output, and survives shell updates.

### Which key opens what

`Super+Space` is **this** launcher (promoted 2026-09-28 at Jan's request); `Super+Alt+Space`
still opens it too. Caelestia's own launcher moved to `Super+Shift+Space`. All three binds are
adjacent and commented in `~/.config/hypr/hyprland.lua`; `hyprctl reload` after editing.

## Troubleshooting

```sh
omarchy-launcher restart     # after editing shell.qml
qs -c omarchy-launcher       # run in the foreground to see QML errors
```

If the categories look wrong, `categories.json` failed to parse — the launcher prints the
parse error on the notice line under the search box rather than failing silently, and falls
back to searching every installed app so you are never locked out.
