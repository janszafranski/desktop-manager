#!/usr/bin/env python3
"""GTK front-end for system-replica.

Presents a titled window with an intro paragraph and a grid of desktop
"configuration cards". Each card holds a preview thumbnail plus the install
options for that configuration. Only one card (the captured desktop) exists
today; the grid is laid out so alternative configurations can be added later
as additional cells — see CONFIGS below.

On "Install" it prints the chosen stages and dry-run flag to stdout and exits 0;
the calling script (gui.sh) launches the actual work in a terminal. Cancel/close
exits non-zero. "Restore my own settings" prints a "restore" request instead,
which gui.sh runs through scripts/restore-backup.sh.

Usage: gui_gtk.py [--image PATH]   # PATH = preview thumbnail for the first card
"""
import argparse
import glob
import os
import subprocess
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango  # noqa: E402

# Stable app id / WM_CLASS so window rules and the .desktop icon can match it.
GLib.set_prgname("system-replica")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPT_DIR)


def _p(*parts):
    return os.path.join(REPO, *parts)


# --- dark-mode preference (remembered across runs) --------------------------
def _pref_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "desktop-manager", "prefs")


APPEARANCE_MODES = ("system", "light", "dark")


def load_mode_pref(default="system"):
    """Remembered appearance mode: 'system', 'light' or 'dark'."""
    try:
        with open(_pref_path()) as f:
            v = f.read().strip()
        return v if v in APPEARANCE_MODES else default
    except OSError:
        return default


def save_mode_pref(mode):
    try:
        p = _pref_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(mode)
    except OSError:
        pass


# --- light/dark theme switching ---------------------------------------------
# We standardise on Adwaita as the base theme because its dark variant is a
# built-in, reliably repainted by the `gtk-application-prefer-dark-theme` hint
# (verified on this GTK build). Naming the theme "Adwaita-dark" does NOT work —
# no such theme exists on disk, so GTK falls back to light. The Breeze GTK
# theme is avoided because it follows the Plasma colour scheme, so it can't
# give a genuine light look on a dark desktop.
def detect_system_dark(fallback_theme=""):
    """True if the desktop prefers a dark colour scheme.

    Reads the XDG appearance portal (org.freedesktop.appearance color-scheme:
    1=dark, 2=light, 0=no preference). Falls back to whether the ambient GTK
    theme name contains 'dark'."""
    try:
        from gi.repository import Gio
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Settings", None)
        res = proxy.call_sync(
            "Read",
            GLib.Variant("(ss)",
                         ("org.freedesktop.appearance", "color-scheme")),
            Gio.DBusCallFlags.NONE, 1000, None)
        scheme = res.unpack()[0]      # unwraps the nested variant -> uint32
        if scheme == 1:
            return True
        if scheme == 2:
            return False
    except Exception:
        pass
    return "dark" in (fallback_theme or "").lower()


# --- desktop configurations -------------------------------------------------
# Add more dicts here to grow the grid. Each becomes a card/cell.
#   kind    : "install" (deploy the captured config via install.sh stages) or
#             "profile" (apply/revert a themed look via shell scripts)
#   image   : preview path ("install" card's is overridden by --image)
CONFIGS = [
    {
        "kind": "install",
        "key": "current",
        "name": "KDE Plasma (default)",
        "desc": "KDE Plasma 6 · Nordic-bluish · Krohnkite tiling · Alacritty. "
                "For setting up a fresh CachyOS/Arch machine — it replaces this "
                "user's shell, Hyprland and KDE config files with the ones "
                "captured in this repo. It is not an add-on: on an existing "
                "Omarchy (or other Hyprland) desktop it takes over the bar and "
                "keybindings. Everything it replaces is saved to "
                "~/.config-backup-<date> first, and scripts/restore-backup.sh "
                "puts it all back. Use Dry run before Install.",
        "image": None,
    },
    {
        "kind": "profile",
        "key": "macos",
        "name": "macOS (WhiteSur)",
        "desc": "Top bar + global menu · floating dock · WhiteSur theme, icons & cursors",
        "image": _p("profiles", "macos", "preview.png"),
        "apply": _p("profiles", "macos", "apply.sh"),
        "revert": _p("profiles", "macos", "revert.sh"),
    },
    {
        "kind": "profile",
        "key": "caelestia",
        "name": "Caelestia (Hyprland)",
        "desc": "Adds a Hyprland + Caelestia shell session at the login screen. "
                "Non-destructive — KDE Plasma stays your default.",
        "image": _p("profiles", "caelestia", "preview.png"),
        "apply": _p("profiles", "caelestia", "install.sh"),
        "revert": _p("profiles", "caelestia", "uninstall.sh"),
        "apply_label": "Install the session",
        "revert_label": "Uninstall it",
    },
    {
        "kind": "profile",
        "key": "end4",
        "name": "illogical-impulse (end4)",
        "desc": "Adds an end-4 Hyprland + Quickshell session at the login screen, "
                "installed into an isolated ~/.config-ii tree so it coexists with "
                "Caelestia. Non-destructive — your default session stays put.",
        "image": _p("profiles", "end4", "preview.png"),
        "apply": _p("profiles", "end4", "install.sh"),
        "revert": _p("profiles", "end4", "uninstall.sh"),
        "apply_label": "Install the session",
        "revert_label": "Uninstall it",
    },
    {
        "kind": "profile",
        "key": "hellokitty",
        "name": "Hello Kitty login",
        "desc": "Swaps the SDDM login screen to a Hello Kitty theme. "
                "Non-destructive — White Tiger stays installed and is restored on uninstall.",
        "image": _p("profiles", "hellokitty", "preview-sitting.png"),
        "apply": _p("profiles", "hellokitty", "install.sh"),
        "revert": _p("profiles", "hellokitty", "uninstall.sh"),
        "apply_label": "Install the theme",
        "revert_label": "Uninstall it",
        # A pick-one background chooser for this profile. Selecting an option
        # updates the preview above and is written to `choice_file`, which
        # install.sh reads to set the deployed theme's background.
        "choice_label": "Background:",
        "choice_file": _p("profiles", "hellokitty", ".bg-choice"),
        "choices": [
            {"value": "Background-Sitting.jpg", "label": "Kitty on pink",
             "preview": _p("profiles", "hellokitty", "preview-sitting.png")},
            {"value": "Background-Dress.jpg", "label": "Kitty in a red dress",
             "preview": _p("profiles", "hellokitty", "preview-dress.png")},
            {"value": "Background-Flower.jpg", "label": "Flower + scalloped border",
             "preview": _p("profiles", "hellokitty", "preview-flower.png")},
        ],
    },
    {
        "kind": "profile",
        "key": "sddm",
        "name": "White Tiger login",
        "desc": "The White Tiger SDDM login screen — this repo's default login look "
                "(needs sudo). The Hello Kitty card swaps it; this puts it back.",
        "image": _p("profiles", "sddm", "preview.png"),
        "apply": _p("profiles", "sddm", "install.sh"),
        "revert": _p("profiles", "sddm", "uninstall.sh"),
        "apply_label": "Install the theme",
        "revert_label": "Uninstall it",
    },
]

# stage checkboxes offered on the "install" card: (id, label, default-on).
# NOTE: the SDDM login screen is its own profile card (see CONFIGS), not a
# checkbox here.
STAGES = [
    ("packages", "Install packages (pacman + AUR, needs sudo)", False),
    ("files",    "Deploy config files & themes",                True),
    ("services", "Enable systemd --user services",              False),
]

# --- bundled apps listed below the cards -----------------------------------
# Launchers for the custom tools that ship with this desktop. Commands run
# through the shell with $VARS expanded; keybind hints are shown in the text.
APPS = [
    {
        "name": "Shakefree Mouse",
        "desc": "Hand-tremor mouse filter — smooths the shake and steadies clicks. "
                "Userspace, no root. Toggle with Super+Shift+M. "
                "Own project now: github.com/janszafranski/shakefree-mouse (AUR: shakefree-mouse); "
                "this just installs the package.",
        "install": _p("profiles", "shakefree-mouse", "install.sh"),
        "launch": "shakefree-mouse",
        "button": "Open panel",
        "group": "utilities",
    },
    {
        "name": "Keyboard shortcuts",
        "desc": "On-screen cheat-sheet of every keybinding (Quickshell widget). "
                "Opens with Super+/ (or the top-left hot corner).",
        "install": _p("profiles", "keybinds", "install.sh"),
        "launch": "bash $HOME/.config/hypr/scripts/keybinds-toggle.sh",
        "button": "Show",
        "group": "utilities",
    },
    {
        "name": "OpenClaw flyout",
        "desc": "The OpenClaw AI assistant side panel — chat with your agent via a "
                "local bridge. Toggle with Super+O.",
        "install": _p("profiles", "openclaw-flyout", "install.sh"),
        "launch": "qs -c openclaw-sidebar ipc call sidebar toggle",
        "button": "Toggle",
    },
    {
        "name": "App launcher",
        "desc": "Omarchy-style categorised app launcher (Quickshell) — a centred "
                "portrait popup opening on Favourites, with folders you walk in and "
                "out of. Toggle with Super+Space (Caelestia's own launcher moves to "
                "Super+Shift+Space). Edit categories, favourites and appearance from "
                "the in-launcher App List Config window (no JSON editing). Built by "
                "Coding Colin.",
        "install": _p("profiles", "omarchy-launcher", "install.sh"),
        "launch": "omarchy-launcher",
        "button": "Toggle",
    },
    {
        "name": "Mic Fixer",
        "desc": "Pick a microphone, record a test clip, watch the level meter and "
                "waveform, and get a plain verdict on what is wrong with it. Native "
                "GTK4 build (mic-fixer) plus a browser build (mic-fixer-web). Filed "
                "under the launcher's Utilities folder. Built by Coding Colin.",
        "install": _p("profiles", "mic-fixer", "install.sh"),
        "launch": "mic-fixer",
        "button": "Open",
        "group": "utilities",
    },
    {
        "name": "Desktop icons",
        "desc": "App icons on the wallpaper, double-click to open — the thing you "
                "miss from Windows (Quickshell). Right-click to add, rename or "
                "resize; drag to rearrange. Needs quickshell. No keybinding or "
                "autostart is written for you — see the profile README. Built by "
                "Coding Colin.",
        "install": _p("profiles", "omarchy-desktop-icons", "install.sh"),
        "launch": "omarchy-desktop-icons toggle",
        "button": "Toggle",
        "group": "utilities",
    },
]

COLUMNS = 3  # cards per row in the grid


# --- what the "files" stage would replace ------------------------------------
# The paths are read out of scripts/manifest.sh at runtime rather than listed
# again here: install.sh deploys exactly that manifest, so a second copy in this
# file would drift from it the first time someone edited one and not the other.
# (array name, display root, subdirectory under files/) — one per deploy_into()
# loop in install.sh's install_files(), in the same order.
MANIFEST_ROOTS = [
    ("HOME_ITEMS",       "~",              "home"),
    ("CONFIG_ITEMS",     "~/.config",      "config"),
    ("LOCALSHARE_ITEMS", "~/.local/share", "local-share"),
    ("ICONS_ITEMS",      "~/.icons",       "icons"),
    ("BIN_ITEMS",        "~/bin",          "bin"),
    ("PICTURES_ITEMS",   "~",              "pictures"),
]


def manifest_items():
    """[(array_name, relative_path)] for every entry in scripts/manifest.sh.

    Sourced with bash rather than parsed, so the list is produced by the same
    shell install.sh reads it with. Returns [] if it cannot be read — callers
    treat that as "no list to show", never as "nothing would be replaced"."""
    prog = 'source "$1" || exit 1\n' + "".join(
        'for i in "${%s[@]}"; do printf "%s\\t%%s\\n" "$i"; done\n' % (arr, arr)
        for arr, _, _ in MANIFEST_ROOTS)
    try:
        proc = subprocess.run(
            ["bash", "-c", prog, "bash", _p("scripts", "manifest.sh")],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=10)
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    items = []
    for line in proc.stdout.splitlines():
        arr, _, rel = line.partition("\t")
        if rel:
            items.append((arr, rel))
    return items


def files_stage_targets():
    """(replaced, added) — the paths `install.sh files` would write on this box.

    `replaced` already exist here: the destructive half, and the only ones the
    backup is for. `added` are new files, which cost you nothing.

    Mirrors deploy_into()'s first guard — an item this repo does not actually
    ship is skipped by the deploy, so it is not claimed as at risk either."""
    repo_files = _p("files")
    ships_pictures = os.path.isdir(os.path.join(repo_files, "pictures"))
    roots = {arr: (disp, sub) for arr, disp, sub in MANIFEST_ROOTS}
    replaced, added = [], []
    for arr, rel in manifest_items():
        disp, sub = roots[arr]
        # install.sh only walks PICTURES_ITEMS when files/pictures was bundled.
        if sub == "pictures" and not ships_pictures:
            continue
        if not os.path.exists(os.path.join(repo_files, sub, rel)):
            continue
        dest = os.path.join(os.path.expanduser(disp), rel)
        (replaced if os.path.lexists(dest) else added).append(disp + "/" + rel)
    return replaced, added


def _running(name):
    """True if a process named exactly `name` is running."""
    try:
        return subprocess.run(["pgrep", "-x", name],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,
                              timeout=5).returncode == 0
    except Exception:
        return False


def foreign_desktop_signals():
    """Reasons to think this is not the machine the snapshot was captured on.

    install_files() already reads "live session + plasmashell running" as "this
    is the KDE desktop the snapshot describes", and takes the live-apply path.
    The inverse of that probe is the thing worth saying out loud: a live
    Hyprland session with no plasmashell, or Omarchy's own config tree, means
    the deploy is about to replace a desktop it did not come from."""
    signals = []
    in_hyprland = bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")) or (
        bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
        and _running("Hyprland"))
    if in_hyprland and not _running("plasmashell"):
        signals.append(
            "You are in a live Hyprland session, not KDE Plasma. This card is a "
            "KDE Plasma snapshot, and the files it replaces include the Hyprland "
            "config your current session is running on.")
    if os.path.isdir(os.path.expanduser("~/.config/omarchy")):
        signals.append(
            "~/.config/omarchy is present, so this looks like an Omarchy "
            "desktop. Omarchy's bar and keybindings come from the Hyprland and "
            "shell files below, and would be replaced by this repo's versions.")
    return signals


def backup_dirs():
    """~/.config-backup-* directories, oldest first.

    Name order is chronological: install.sh stamps them -<date>-<time>."""
    return sorted(d for d in glob.glob(os.path.expanduser("~/.config-backup-*"))
                  if os.path.isdir(d))


def show_enlarged(parent, path):
    """Open a modal window showing `path` at a larger size, with an X to close.
    Also closes on Escape or a click on the image."""
    if not path or not os.path.exists(path):
        return
    try:
        pix = GdkPixbuf.Pixbuf.new_from_file(path)
    except Exception:
        return

    win = Gtk.Window()
    win.set_transient_for(parent)
    win.set_modal(True)
    win.set_type_hint(Gdk.WindowTypeHint.DIALOG)
    win.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

    header = Gtk.HeaderBar(title="Desktop preview")
    header.set_show_close_button(True)          # the X
    win.set_titlebar(header)

    # scale to fit ~85% of the screen (don't upscale past native size).
    # Use monitor geometry — Gdk.Screen.get_width/height are deprecated.
    display = Gdk.Display.get_default()
    pwin = parent.get_window() if parent is not None else None
    monitor = (display.get_monitor_at_window(pwin) if pwin is not None else None) \
        or display.get_primary_monitor() or display.get_monitor(0)
    geo = monitor.get_geometry()
    max_w = min(int(geo.width * 0.85), 1600)
    max_h = min(int(geo.height * 0.85), 1000)
    w, h = pix.get_width(), pix.get_height()
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        pix = pix.scale_simple(int(w * scale), int(h * scale),
                               GdkPixbuf.InterpType.BILINEAR)

    ev = Gtk.EventBox()
    ev.add(Gtk.Image.new_from_pixbuf(pix))
    ev.connect("button-press-event", lambda *_: win.destroy())
    win.add(ev)

    win.connect("key-press-event",
                lambda _w, e: win.destroy() if e.keyval == Gdk.KEY_Escape else None)
    win.show_all()


def needs_files_confirmation(replaced, added, signals):
    """Whether to put the confirmation in front of the `files` stage.

    Skipped only when there is demonstrably nothing of the user's to lose: this
    machine has none of the manifest's paths yet and looks like the desktop the
    snapshot came from — i.e. the fresh install the card is written for. An
    empty `added` as well means the manifest could not be read, so what the
    deploy would touch is unknown and the confirmation stays."""
    return bool(replaced) or bool(signals) or not added


def _tilde(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + "/") else path


class ConfirmReplaceDialog(Gtk.Dialog):
    """The guard in front of `install.sh files`.

    The card's description says what the stage does, but a description sits in
    the same grey body text as every other card and the person most at risk is
    the one least likely to read it (JAN-55). This says it at the moment of the
    click, names the files by path, and defaults to Cancel.

    Only the `files` stage gets this. `packages`, `services` and the SDDM theme
    do not take a desktop down, so a dialog in front of them would just be
    noise that teaches people to click through."""

    LIST_H = 190       # px of visible path list before it scrolls
    ROW_H = 17         # px per path row, at the <small> monospace it is drawn in

    def __init__(self, parent, replaced, added, signals):
        super().__init__(title="Replace your desktop config?",
                         transient_for=parent, modal=True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        go = self.add_button("Replace my config", Gtk.ResponseType.ACCEPT)
        go.get_style_context().add_class("destructive-action")
        # Cancel is the default action, so Enter *and* Escape both back out: a
        # keypress aimed at the window behind this cannot turn into a deploy.
        self.set_default_response(Gtk.ResponseType.CANCEL)

        body = self.get_content_area()
        body.set_spacing(8)
        body.set_border_width(12)

        head = Gtk.Label()
        if replaced:
            head.set_markup(
                "<b>%d of your own files and folders will be replaced with this "
                "repo's versions.</b>" % len(replaced))
        else:
            head.set_markup(
                "<b>This deploys another machine's desktop config into your "
                "home directory.</b>")
        head.set_line_wrap(True)
        head.set_xalign(0.0)
        head.set_max_width_chars(62)
        body.pack_start(head, False, False, 0)

        # Why this might be the wrong machine — the loudest thing in the dialog,
        # because it is the part that turns a routine deploy into Miya's bug.
        for sig in signals:
            warn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            icon = Gtk.Image.new_from_icon_name("dialog-warning",
                                                Gtk.IconSize.LARGE_TOOLBAR)
            icon.set_valign(Gtk.Align.START)
            warn_row.pack_start(icon, False, False, 0)
            lbl = Gtk.Label()
            lbl.set_markup("<b>%s</b>" % GLib.markup_escape_text(sig))
            lbl.set_line_wrap(True)
            lbl.set_xalign(0.0)
            lbl.set_max_width_chars(58)
            warn_row.pack_start(lbl, True, True, 0)
            body.pack_start(warn_row, False, False, 0)

        if replaced:
            caption = Gtk.Label()
            caption.set_markup("<small>Replaced (copied to %s first):</small>"
                               % GLib.markup_escape_text(
                                   "~/.config-backup-<date>"))
            caption.set_xalign(0.0)
            body.pack_start(caption, False, False, 0)

            paths = Gtk.Label()
            paths.set_markup("<tt><small>%s</small></tt>"
                             % GLib.markup_escape_text("\n".join(replaced)))
            paths.set_xalign(0.0)
            paths.set_valign(Gtk.Align.START)
            paths.set_selectable(True)      # so they can be copied out
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            # As tall as the list, up to LIST_H and scrolling past that: no dead
            # space under a short list, no row half-cut at the bottom edge.
            # Sized by row count rather than by measuring the label — an
            # unrealised label reports its minimum, not the height of its text.
            list_h = max(44, min(self.LIST_H, self.ROW_H * len(replaced) + 8))
            scroll.set_min_content_height(list_h)
            scroll.set_max_content_height(list_h)
            scroll.set_propagate_natural_height(False)
            scroll.set_shadow_type(Gtk.ShadowType.IN)
            scroll.add(paths)
            body.pack_start(scroll, True, True, 0)

        foot = Gtk.Label()
        if added:
            foot_text = ("%d more %s this machine does not have yet %s added. "
                         % (len(added),
                            "file" if len(added) == 1 else "files",
                            "is" if len(added) == 1 else "are"))
        elif replaced:
            foot_text = ""
        else:
            foot_text = ("The file list could not be read from "
                         "scripts/manifest.sh, so what this would touch is not "
                         "known here — run Dry run first. ")
        foot.set_markup(
            "<small>%sUse <b>Dry run</b> to see the whole change without making "
            "it. Afterwards, <b>Restore my own settings</b> puts your files back "
            "from the backup.</small>"
            % GLib.markup_escape_text(foot_text))
        foot.set_line_wrap(True)
        foot.set_xalign(0.0)
        foot.set_max_width_chars(62)
        body.pack_start(foot, False, False, 0)

        self.show_all()


class Card(Gtk.Frame):
    """One selectable desktop configuration: radio + thumbnail + options."""

    THUMB_W = 190          # card thumbnail width (px)
    THUMB_H = 107          # card thumbnail height (px) — 16:9, matches the previews

    def __init__(self, cfg, group, image_override, image_full=None):
        super().__init__()
        self.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.key = cfg["key"]
        self.kind = cfg.get("kind", "install")
        self.cfg = cfg

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.set_border_width(5)
        self.add(box)

        # selector + title
        self.radio = Gtk.RadioButton.new_with_label_from_widget(group, cfg["name"])
        self.radio.get_child().set_markup(
            f"<b>{GLib.markup_escape_text(cfg['name'])}</b>")
        box.pack_start(self.radio, False, False, 0)

        # thumbnail — a flat button; click enlarges the full-res image. Held as
        # instance state so a profile's chooser (below) can swap it live.
        self._thumb_img = Gtk.Image()
        full_img = image_full or cfg.get("image_full") \
            or image_override or cfg.get("image")
        self._thumb_full = full_img
        init_img = image_override or cfg.get("image")
        if init_img:
            # render the (possibly downscaled) thumbnail, but enlarge to the
            # full-res image, not the thumbnail source.
            self._set_thumb(init_img, full=full_img)
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            # Mouse-only (click to enlarge); don't let it take keyboard focus,
            # or the first card's thumbnail draws a focus frame the others lack.
            btn.set_can_focus(False)
            btn.set_image(self._thumb_img)
            btn.set_always_show_image(True)
            btn.set_tooltip_text("Click to enlarge")
            btn.connect("clicked",
                        lambda _b: show_enlarged(self.get_toplevel(), self._thumb_full))
            box.pack_start(btn, False, False, 0)

        # description
        desc = Gtk.Label()
        desc.set_markup(f"<small>{GLib.markup_escape_text(cfg['desc'])}</small>")
        desc.set_halign(Gtk.Align.START)
        desc.set_line_wrap(True)
        desc.set_max_width_chars(24)   # cap natural width so the card tracks the thumbnail
        desc.set_xalign(0.0)
        box.pack_start(desc, False, False, 0)

        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                       False, False, 2)

        if self.kind == "profile":
            # apply / revert selector (labels are per-card so an installer-style
            # profile can say "Install / Uninstall" instead of "Apply / Revert")
            self.op_apply = Gtk.RadioButton.new_with_label(
                None, cfg.get("apply_label", "Apply this look"))
            op_revert = Gtk.RadioButton.new_with_label_from_widget(
                self.op_apply, cfg.get("revert_label", "Revert to previous"))
            self.op_apply.set_active(True)
            box.pack_start(self.op_apply, False, False, 0)
            box.pack_start(op_revert, False, False, 0)

            # optional pick-one chooser (e.g. which background). Selecting an
            # option swaps the preview above; the value is saved on install.
            self.choices = cfg.get("choices")
            self.choice_combo = None
            if self.choices:
                # No label — the single option list is self-explanatory. The
                # pulldown spans the full thumbnail width so it lines up with the
                # preview above it.
                combo = Gtk.ComboBoxText()
                for ch in self.choices:
                    combo.append(ch["value"], ch["label"])
                combo.set_active(0)
                combo.connect("changed", self._on_choice_changed)
                # Ellipsize very long option labels so they can't force the card
                # (and thus every homogeneous column) wider than the thumbnail.
                for cell in combo.get_cells():
                    cell.set_property("ellipsize", Pango.EllipsizeMode.END)
                combo.set_size_request(self.THUMB_W, -1)
                combo.set_halign(Gtk.Align.CENTER)
                self.choice_combo = combo
                box.pack_start(combo, False, False, 0)
        else:
            # per-card stage checkboxes. Wrap their labels so a long line
            # (e.g. "Install packages (pacman + AUR, needs sudo)") doesn't
            # force the card — and thus the whole grid — wider than the thumb.
            self.checks = {}
            for sid, label, default in STAGES:
                cb = Gtk.CheckButton(label=label)
                cb.set_active(default)
                lbl = cb.get_child()
                if isinstance(lbl, Gtk.Label):
                    lbl.set_line_wrap(True)
                    lbl.set_max_width_chars(24)
                    lbl.set_xalign(0.0)
                self.checks[sid] = cb
                box.pack_start(cb, False, False, 0)

    def _set_thumb(self, path, full=None):
        """Load `path` into a fixed THUMB_W×THUMB_H box (center-crop to fill), so
        every card's thumbnail is the same size regardless of the source image's
        aspect — e.g. card 1's live ultrawide desktop screenshot matches the 16:9
        profile previews instead of coming out short and wide."""
        try:
            src = GdkPixbuf.Pixbuf.new_from_file(path)
            w, h = src.get_width(), src.get_height()
            # scale so the image fills the box, then center-crop the overflow
            scale = max(self.THUMB_W / w, self.THUMB_H / h)
            sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
            scaled = src.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)
            ox, oy = (sw - self.THUMB_W) // 2, (sh - self.THUMB_H) // 2
            pix = GdkPixbuf.Pixbuf.new_subpixbuf(
                scaled, ox, oy, self.THUMB_W, self.THUMB_H)
            self._thumb_img.set_from_pixbuf(pix)
            self._thumb_full = full if full is not None else path
        except Exception:
            pass

    def _on_choice_changed(self, combo):
        val = combo.get_active_id()
        for ch in (self.choices or []):
            if ch["value"] == val and ch.get("preview"):
                self._set_thumb(ch["preview"])
                break

    def commit_choice(self):
        """Persist the picked option to choice_file so the apply script reads it."""
        cf = self.cfg.get("choice_file")
        if self.choice_combo is not None and cf:
            try:
                with open(cf, "w") as f:
                    f.write(self.choice_combo.get_active_id() or "")
            except OSError:
                pass

    def selected_stages(self):
        return [sid for sid, cb in self.checks.items() if cb.get_active()]

    def profile_command(self):
        """For a profile card: absolute path of the apply or revert script."""
        return self.cfg["apply"] if self.op_apply.get_active() else self.cfg["revert"]


class ReplicaWindow(Gtk.Window):
    # Fixed height (px) of the scrollable card-grid viewport. This is the one
    # scroll area in the window, so it is also where the height the Apps list
    # needs comes from: the two together are what the window is tall enough for.
    GRID_VIEWPORT_H = 620
    # Fixed height (px) of the Apps-list viewport. Kept above the natural
    # height of the current rows (244px) so the list is never squeezed and
    # needs no scrollbar of its own — see the note at the widget.
    APPS_VIEWPORT_H = 270

    def __init__(self, image_override, image_full=None):
        super().__init__()
        self.result = None

        # Float (don't tile) on tiling WMs like Krohnkite, pop up centered at a
        # fixed size, but stay resizable / maximizable from the title bar.
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_default_size(500, 540)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_border_width(0)

        # --- title bar --------------------------------------------------------
        header = Gtk.HeaderBar(title="Desktop Manager")
        header.set_subtitle("Config & Theme Installer")
        header.set_show_close_button(True)
        # ensure a maximize (and minimize) button is present in the title bar
        header.set_decoration_layout("icon:minimize,maximize,close")
        self.set_titlebar(header)
        self.set_title("Desktop Manager")
        # App icon: set the window icon (taskbar / alt-tab) and also pack a small
        # copy at the start of the header bar, since GTK3 CSD header bars don't
        # render the window icon in the decoration-layout "icon:" slot themselves.
        _icon = _p("icon.png")
        if os.path.exists(_icon):
            try:
                self.set_icon_from_file(_icon)
                _hpix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    _icon, 40, 40, True)
                _himg = Gtk.Image.new_from_pixbuf(_hpix)
                _himg.set_margin_start(4)
                _himg.set_margin_end(4)
                header.pack_start(_himg)
            except Exception:
                pass

        # appearance selector — System / Light / Dark, remembered across runs.
        # "System" follows the desktop's colour-scheme preference.
        self._settings = Gtk.Settings.get_default()
        self._orig_theme = self._settings.get_property("gtk-theme-name") or ""
        self._mode = load_mode_pref()
        self._apply_mode(self._mode)
        appearance = Gtk.ComboBoxText()
        for mid, label in (("system", "System"),
                           ("light", "Light"),
                           ("dark", "Dark")):
            appearance.append(mid, label)
        appearance.set_active_id(self._mode)
        appearance.set_tooltip_text("Appearance")
        appearance.connect("changed", self.on_mode_changed)
        header.pack_end(appearance)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_border_width(12)
        self.add(outer)

        # Description blurb: the icon now lives in the title bar (moved out of
        # here), and the original first paragraph is dropped — only this second
        # paragraph remains, with no logo beside it.
        intro = Gtk.Label(
            label="Pick a configuration below and tick which parts to apply, "
                  "then click Install. Any existing files are backed up before "
                  "they are overwritten. Turn on Dry run to preview exactly what "
                  "would change without touching anything.")
        intro.set_line_wrap(True)
        intro.set_xalign(0.0)
        intro.set_max_width_chars(66)
        outer.pack_start(intro, False, False, 0)

        # --- grid of configuration cards -------------------------------------
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        grid.set_column_homogeneous(True)
        self.cards = []
        group = None
        for i, cfg in enumerate(CONFIGS):
            override = image_override if i == 0 else None
            full = image_full if i == 0 else None
            card = Card(cfg, group, override, full)
            if group is None:
                group = card.radio
            card.radio.set_active(i == 0)
            grid.attach(card, i % COLUMNS, i // COLUMNS, 1, 1)
            self.cards.append(card)
        # Put the card grid in a fixed-height scroll area so the window keeps its
        # size as more thumbnail rows are added: extra rows scroll instead of
        # growing the window. The vertical scrollbar is always shown as a track
        # (line) with a proportional thumb — full now (all rows fit), shrinking
        # with every extra row added.
        grid_scroll = Gtk.ScrolledWindow()
        grid_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        # Disable overlay scrolling so the bar is a permanent visible track with
        # a proportional thumb (full now, shrinking as rows are added), rather
        # than an overlay that hides until hovered.
        grid_scroll.set_overlay_scrolling(False)
        grid_scroll.add(grid)
        # Fixed viewport sized to the current two rows so the scrollbar track
        # ends at the base of the cards (no overhang). Extra rows added later
        # exceed this and scroll, keeping the window size.
        grid_scroll.set_min_content_height(self.GRID_VIEWPORT_H)
        grid_scroll.set_max_content_height(self.GRID_VIEWPORT_H)
        grid_scroll.set_propagate_natural_height(False)
        outer.pack_start(grid_scroll, False, False, 0)

        # --- Apps: launchers for this desktop's bundled tools -----------------
        apps_frame = Gtk.Frame(label="Apps")
        apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        apps_box.set_border_width(10)
        # Fixed-height area holding the Apps list. It is tall enough for the
        # rows as they are, so there is no scrollbar: a second permanent track
        # beside the card grid's was redundant, and a squeezed one is worse.
        # Should the list ever outgrow the height, an overlay bar appears while
        # scrolling rather than a second track sitting there all the time.
        apps_scroll = Gtk.ScrolledWindow()
        apps_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        apps_scroll.set_min_content_height(self.APPS_VIEWPORT_H)
        apps_scroll.set_max_content_height(self.APPS_VIEWPORT_H)
        apps_scroll.set_propagate_natural_height(False)
        apps_scroll.add(apps_box)
        apps_frame.add(apps_scroll)

        # Top-level apps render as rows in the Apps frame; anything tagged with a
        # "group" is tucked into a collapsed sub-menu (a Gtk.Expander) at the
        # bottom, so single-purpose tools don't make the visible list grow.
        top_apps = [a for a in APPS if not a.get("group")]
        util_apps = [a for a in APPS if a.get("group") == "utilities"]

        self._pack_app_rows(apps_box, top_apps)

        if util_apps:
            # Utilities: a single row that looks like any other app row, but its
            # button opens a separate flyout window listing the utility apps —
            # so the main popup stays short instead of growing inline.
            apps_box.pack_start(
                Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                False, False, 0)
            urow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            utext = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            uname = Gtk.Label()
            uname.set_markup("<b>Utilities</b>")
            uname.set_xalign(0.0)
            udesc = Gtk.Label()
            udesc.set_markup(
                "<small>Small single-purpose tools — "
                + GLib.markup_escape_text(
                    ", ".join(a["name"] for a in util_apps))
                + ".</small>")
            udesc.set_xalign(0.0)
            udesc.set_line_wrap(True)
            udesc.set_max_width_chars(52)
            utext.pack_start(uname, False, False, 0)
            utext.pack_start(udesc, False, False, 0)
            urow.pack_start(utext, True, True, 0)
            ubtn = Gtk.Button(label="Open")
            ubtn.set_valign(Gtk.Align.CENTER)
            ubtn.connect("clicked",
                         lambda _b: self._open_utilities(util_apps))
            urow.pack_end(ubtn, False, False, 0)
            apps_box.pack_start(urow, False, False, 0)

        # --- action row (kept above the Apps list) ---------------------------
        # Inset to match the Apps frame's content padding (border_width 10 + the
        # frame's ~1px line) so the master Install lines up with the per-app ones.
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_margin_start(11)
        actions.set_margin_end(11)
        self.dry = Gtk.CheckButton(label="Dry run (preview only, no changes)")

        # The undo, offered where the thing that needs undoing was pressed.
        # Enabled only when there is a backup to restore from, so it can never
        # look like a general "reset my desktop" button.
        self.restore = Gtk.Button(label="Restore my own settings")
        self._backups = backup_dirs()
        if self._backups:
            self.restore.set_tooltip_text(
                "Put your own shell, Hyprland and KDE config files back from "
                + _tilde(self._backups[-1])
                + ", the backup taken when they were replaced.")
        else:
            self.restore.set_sensitive(False)
            self.restore.set_tooltip_text(
                "Nothing to restore: there is no ~/.config-backup-* directory, "
                "so this repo's config files have never been deployed here.")
        self.restore.connect("clicked", self.on_restore)
        actions.pack_start(self.restore, False, False, 0)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.close())
        install = Gtk.Button(label="Install")
        install.get_style_context().add_class("suggested-action")
        install.connect("clicked", self.on_install)
        # Cluster Dry run next to the buttons on the right (dry · cancel · install)
        actions.pack_end(install, False, False, 0)
        actions.pack_end(cancel, False, False, 0)
        actions.pack_end(self.dry, False, False, 0)
        for _w in (self.dry, cancel, install, self.restore):
            _w.set_valign(Gtk.Align.CENTER)
        # Vertically centre the action row in the gap between the card grid and
        # the Apps frame: equal space above and below (was 4px above / 10px
        # below). outer spacing is 4, so a 3px top margin here + a matching 3px
        # top margin on the Apps frame gives 7px on each side.
        actions.set_margin_top(3)
        outer.pack_start(actions, False, False, 0)
        apps_frame.set_margin_top(3)
        outer.pack_start(apps_frame, False, False, 0)

        self.connect("destroy", Gtk.main_quit)

    def _apply_visual(self, dark):
        # Adwaita is a real, always-present base whose dark variant is toggled
        # by the prefer-dark hint (verified to actually repaint on this build).
        self._settings.set_property("gtk-theme-name", "Adwaita")
        self._settings.set_property("gtk-application-prefer-dark-theme", dark)

    def _apply_mode(self, mode):
        if mode == "system":
            self._apply_visual(detect_system_dark(self._orig_theme))
        else:
            self._apply_visual(mode == "dark")

    def on_mode_changed(self, combo):
        mode = combo.get_active_id() or "system"
        self._mode = mode
        self._apply_mode(mode)
        save_mode_pref(mode)

    def active_card(self):
        for c in self.cards:
            if c.radio.get_active():
                return c
        return self.cards[0]

    def _launch_app(self, cmd):
        """Launch a bundled app command detached from this GUI."""
        try:
            subprocess.Popen(os.path.expandvars(cmd), shell=True,
                             start_new_session=True)
        except Exception:
            pass

    def _pack_app_rows(self, container, apps):
        """Pack one row per app (bold name + wrapped description + Install button)
        into `container`, with separators between rows. Shared by the main Apps
        list and the Utilities flyout so both look identical."""
        for i, app in enumerate(apps):
            if i:
                container.pack_start(
                    Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                    False, False, 0)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            name = Gtk.Label()
            name.set_markup(f"<b>{GLib.markup_escape_text(app['name'])}</b>")
            name.set_xalign(0.0)
            desc = Gtk.Label()
            desc.set_markup(f"<small>{GLib.markup_escape_text(app['desc'])}</small>")
            desc.set_xalign(0.0)
            desc.set_line_wrap(True)
            # Cap so the (single-column) app descriptions don't stretch the
            # window wider than the card grid above them.
            desc.set_max_width_chars(52)
            text.pack_start(name, False, False, 0)
            text.pack_start(desc, False, False, 0)
            row.pack_start(text, True, True, 0)
            if app.get("install"):
                ib = Gtk.Button(label="Install")
                ib.get_style_context().add_class("suggested-action")
                ib.set_valign(Gtk.Align.CENTER)
                ib.connect("clicked",
                           lambda _b, s=app["install"]: self._install_app(s))
                row.pack_end(ib, False, False, 0)
            container.pack_start(row, False, False, 0)

    def _open_utilities(self, util_apps):
        """Pop a separate flyout window listing the utility apps — same row style
        as the main Apps list, so the main popup stays short."""
        win = Gtk.Window()
        win.set_transient_for(self)
        win.set_modal(True)
        win.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        win.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        win.set_border_width(0)
        header = Gtk.HeaderBar(title="Utilities")
        header.set_show_close_button(True)
        win.set_titlebar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(12)
        self._pack_app_rows(box, util_apps)
        win.add(box)
        win.connect("key-press-event",
                    lambda _w, e: win.destroy() if e.keyval == Gdk.KEY_Escape else None)
        win.show_all()

    def _install_app(self, script):
        """Install a bundled app: hand its script to gui.sh to run in a terminal."""
        self.result = ("profile", script,
                       "--dry-run" if self.dry.get_active() else "")
        self.close()

    def _warn(self, text):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK, text=text)
        dlg.run()
        dlg.destroy()

    def confirm_files_stage(self):
        """Ask before `install.sh files` overwrites this user's own config.

        True = go ahead. Returns True without asking on a machine with nothing
        of the manifest's paths to lose — see needs_files_confirmation()."""
        replaced, added = files_stage_targets()
        signals = foreign_desktop_signals()
        if not needs_files_confirmation(replaced, added, signals):
            return True
        dlg = ConfirmReplaceDialog(self, replaced, added, signals)
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.ACCEPT

    def on_install(self, *_):
        card = self.active_card()
        dry = "--dry-run" if self.dry.get_active() else ""
        if card.kind == "profile":
            if card.op_apply.get_active():
                card.commit_choice()
            self.result = ("profile", card.profile_command(), dry)
        else:
            stages = card.selected_stages()
            if not stages:
                self._warn("Select at least one thing to install.")
                return
            # Only the files stage replaces the user's own config, and a dry run
            # replaces nothing at all — so that is the one combination guarded.
            if "files" in stages and not dry and not self.confirm_files_stage():
                return
            self.result = ("stages", " ".join(stages), dry)
        self.close()

    def on_restore(self, *_):
        """Run scripts/restore-backup.sh against the newest backup."""
        if not self._backups:
            return
        backup = self._backups[-1]
        dry = "--dry-run" if self.dry.get_active() else ""
        if not dry:
            dlg = Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.QUESTION,
                text="Restore your own settings from %s?" % _tilde(backup))
            dlg.format_secondary_text(
                "Your files as they were before this repo's config was deployed "
                "are put back, and the files the deploy added where you had none "
                "are removed. Log out and back in afterwards.")
            dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dlg.add_button("Restore", Gtk.ResponseType.ACCEPT)
            dlg.set_default_response(Gtk.ResponseType.CANCEL)
            resp = dlg.run()
            dlg.destroy()
            if resp != Gtk.ResponseType.ACCEPT:
                return
        self.result = ("restore", backup, dry)
        self.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None, help="thumbnail shown on the card")
    ap.add_argument("--image-full", default=None, help="full-res image for enlarge")
    args = ap.parse_args()

    # Fall back to the repo's captured-desktop preview if no --image was passed
    # (e.g. run directly rather than via gui.sh), so card 1 always has a thumbnail.
    image = args.image or next(
        (p for p in (_p(".preview-thumb.png"), _p("preview.png")) if os.path.exists(p)), None)
    image_full = args.image_full or (
        _p("preview.png") if os.path.exists(_p("preview.png")) else None)

    win = ReplicaWindow(image, image_full)
    win.show_all()
    Gtk.main()

    if not win.result:
        sys.exit(1)
    # 3 lines: mode ("stages"|"profile"|"restore"), payload, dry-flag
    mode, payload, dry = win.result
    print(mode)
    print(payload)
    print(dry)


if __name__ == "__main__":
    main()
