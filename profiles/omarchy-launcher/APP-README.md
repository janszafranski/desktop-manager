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

## App List Config window

Categories, favourites and appearance can all be edited from inside the launcher — no text
editor needed. The **App List Config** window opens from the pinned `tune`-icon row at the top
of the System folder, or `omarchy-launcher config`. Which folder carries that pinned row is a
flag in the data (`"configEntry": true`) rather than a hard-coded id, so renaming or moving the
settings category keeps the row where it belongs.

It has two halves:

- **CATEGORIES** — pick a category on the left; on the right, reorder its apps, drop apps you
  don't want, and **ADD AN APP** by live-searching everything installed. *All Apps* is
  generated from everything installed, so there is no list to edit there — it says so and
  points you at another category.
  The list of categories is editable here too: **New category** (`Ctrl + N`) under the column
  inserts one next to the category you were on — the order of this list is the order of the
  folder rows, so that saves a reorder — and puts the caret in its name. The name in the middle
  column's header *is* the rename field, the button beside it picks the folder's icon from a
  grid of Material Symbols (or any name typed into the box next to it), and **Delete** takes two
  clicks. A delete never strands anything: remove the **opening view** and another category
  becomes it, remove the folder holding the pinned **App List Config** row and it moves, with the
  footer naming whichever category took over. The last remaining category can't be deleted.
  A category's `id` is derived from its name at creation and then left alone — `defaultCategory`
  points at one and `omarchy-launcher category <id>` is the kind of thing a keybind names — so
  after the first save a rename is only a label change.
- **Appearance** — the **Highlight** (the selection pill) and the **Faint outline** (the card
  border). Each has a *source* — text (`onSurface`), accent (`primary`), outline, surface, or
  **Custom** with a `#rrggbb` — and a slider (Highlight *Strength*, outline *Opacity*, both
  0..1). Every source but Custom is read live from Caelestia's scheme, so the pill and border
  keep matching the desktop through a wallpaper recolour.

An **Unsaved changes** banner tracks a working draft; **Save** writes both
`~/.config/omarchy-launcher/categories.json` **and** `~/.config/omarchy-launcher/appearance.json`.
`appearance.json` is a new file the popup owns — delete it and the launcher falls back to the
built-in defaults. Both files are watched, so a save applies on the next open, no restart.

## Categories

Everything about the categories lives in `~/.config/omarchy-launcher/categories.json`
(`omarchy-launcher edit` opens it, or edit it from the App List Config window above). The file
is watched — save it and the next open picks the change up, no restart.

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
  `config` (open the App List Config window), `category <id>` (open straight into one folder),
  `type TEXT` (open with the search seeded — the desktop type-to-open binds), `restart` (after
  editing the QML), `edit`, `daemon`. It also fixes up `XDG_DATA_DIRS` for the daemon so Flatpak
  apps are indexed (see above). Over IPC, `type` is spelled `typed` (with a sequence arg so
  per-keystroke calls that race to the socket can't scramble the search).
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
