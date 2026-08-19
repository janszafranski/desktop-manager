#!/usr/bin/env python3
"""GTK front-end for system-replica.

Presents a titled window with an intro paragraph and a grid of desktop
"configuration cards". Each card holds a preview thumbnail plus the install
options for that configuration. Only one card (the captured desktop) exists
today; the grid is laid out so alternative configurations can be added later
as additional cells — see CONFIGS below.

On "Install" it prints the chosen stages and dry-run flag to stdout and exits 0;
the calling script (gui.sh) launches the actual work in a terminal. Cancel/close
exits non-zero.

Usage: gui_gtk.py [--image PATH]   # PATH = preview thumbnail for the first card
"""
import argparse
import os
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib  # noqa: E402

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
        "name": "Current desktop",
        "desc": "KDE Plasma 6 · Nordic-bluish · Krohnkite tiling · Alacritty",
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
]

# stage checkboxes offered per card: (id, label, default-on)
STAGES = [
    ("packages", "Install packages (pacman + AUR, needs sudo)", False),
    ("files",    "Deploy config files & themes",                True),
    ("sddm",     "Install SDDM login screen (needs sudo)",      False),
    ("services", "Enable systemd --user services",              False),
]

INTRO = (
    "This installer reproduces a captured desktop setup on the current machine — "
    "shell, terminal, editor, GTK/Qt theming and the KDE Plasma / KWin configuration, "
    "along with the bundled Nordic themes, cursors and wallpapers.\n\n"
    "Pick a configuration below and tick which parts to apply, then click Install. "
    "Any existing files are backed up before they are overwritten. Turn on Dry run "
    "to preview exactly what would change without touching anything."
)

COLUMNS = 2  # cards per row in the grid


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

    # scale to fit ~85% of the screen (don't upscale past native size)
    screen = win.get_screen()
    max_w = min(int(screen.get_width() * 0.85), 1600)
    max_h = min(int(screen.get_height() * 0.85), 1000)
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


class Card(Gtk.Frame):
    """One selectable desktop configuration: radio + thumbnail + options."""

    THUMB_W = 340  # card thumbnail width (px)

    def __init__(self, cfg, group, image_override, image_full=None):
        super().__init__()
        self.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.key = cfg["key"]
        self.kind = cfg.get("kind", "install")
        self.cfg = cfg

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        self.add(box)

        # selector + title
        self.radio = Gtk.RadioButton.new_with_label_from_widget(group, cfg["name"])
        self.radio.get_child().set_markup(
            f"<b>{GLib.markup_escape_text(cfg['name'])}</b>")
        box.pack_start(self.radio, False, False, 0)

        # thumbnail — a flat button; click enlarges the full-res image. Held as
        # instance state so a profile's chooser (below) can swap it live.
        self._thumb_img = Gtk.Image()
        self._thumb_full = image_full or cfg.get("image_full") \
            or image_override or cfg.get("image")
        init_img = image_override or cfg.get("image")
        if init_img:
            self._set_thumb(init_img)
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
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
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.pack_start(
                    Gtk.Label(label=cfg.get("choice_label", "Option:")),
                    False, False, 0)
                combo = Gtk.ComboBoxText()
                for ch in self.choices:
                    combo.append(ch["value"], ch["label"])
                combo.set_active(0)
                combo.connect("changed", self._on_choice_changed)
                self.choice_combo = combo
                row.pack_start(combo, True, True, 0)
                box.pack_start(row, False, False, 0)
        else:
            # per-card stage checkboxes
            self.checks = {}
            for sid, label, default in STAGES:
                cb = Gtk.CheckButton(label=label)
                cb.set_active(default)
                self.checks[sid] = cb
                box.pack_start(cb, False, False, 0)

    def _set_thumb(self, path):
        """Load `path` scaled to the card width into the (swappable) thumbnail."""
        try:
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                path, self.THUMB_W, -1, True)
            self._thumb_img.set_from_pixbuf(pix)
            self._thumb_full = path
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
    def __init__(self, image_override, image_full=None):
        super().__init__()
        self.result = None

        # Float (don't tile) on tiling WMs like Krohnkite, pop up centered at a
        # fixed size, but stay resizable / maximizable from the title bar.
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_default_size(600, 640)
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

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.set_border_width(18)
        self.add(outer)

        # --- intro paragraph (app icon on the left) ---------------------------
        intro_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        icon_path = _p("icon.png")
        if os.path.exists(icon_path):
            try:
                ipix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    icon_path, 64, 64, True)
                logo = Gtk.Image.new_from_pixbuf(ipix)
                logo.set_valign(Gtk.Align.START)
                intro_row.pack_start(logo, False, False, 0)
            except Exception:
                pass
        intro = Gtk.Label(label=INTRO)
        intro.set_line_wrap(True)
        intro.set_xalign(0.0)
        intro.set_max_width_chars(64)
        intro_row.pack_start(intro, True, True, 0)
        outer.pack_start(intro_row, False, False, 0)

        # --- grid of configuration cards -------------------------------------
        grid = Gtk.Grid(column_spacing=14, row_spacing=14)
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
        outer.pack_start(grid, True, True, 0)

        # --- action row -------------------------------------------------------
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.dry = Gtk.CheckButton(label="Dry run (preview only, no changes)")
        actions.pack_start(self.dry, False, False, 0)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: self.close())
        install = Gtk.Button(label="Install")
        install.get_style_context().add_class("suggested-action")
        install.connect("clicked", self.on_install)
        actions.pack_end(install, False, False, 0)
        actions.pack_end(cancel, False, False, 0)
        outer.pack_start(actions, False, False, 0)

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

    def _warn(self, text):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK, text=text)
        dlg.run()
        dlg.destroy()

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
            self.result = ("stages", " ".join(stages), dry)
        self.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None, help="thumbnail shown on the card")
    ap.add_argument("--image-full", default=None, help="full-res image for enlarge")
    args = ap.parse_args()

    win = ReplicaWindow(args.image, args.image_full)
    win.show_all()
    Gtk.main()

    if not win.result:
        sys.exit(1)
    # 3 lines: mode ("stages"|"profile"), payload, dry-flag
    mode, payload, dry = win.result
    print(mode)
    print(payload)
    print(dry)


if __name__ == "__main__":
    main()
