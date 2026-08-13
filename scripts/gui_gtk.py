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
]

# stage checkboxes offered per card: (id, label, default-on)
STAGES = [
    ("packages", "Install packages (pacman + AUR, needs sudo)", False),
    ("files",    "Deploy config files & themes",                True),
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

        # thumbnail — a flat button; click enlarges the full-res image
        img_path = image_override or cfg.get("image")
        full_path = image_full or cfg.get("image_full") or img_path
        if img_path:
            try:
                # scale to a uniform card width, preserving aspect
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    img_path, self.THUMB_W, -1, True)
                btn = Gtk.Button()
                btn.set_relief(Gtk.ReliefStyle.NONE)
                btn.set_image(Gtk.Image.new_from_pixbuf(pix))
                btn.set_always_show_image(True)
                btn.set_tooltip_text("Click to enlarge")
                btn.connect("clicked",
                            lambda _b, p=full_path: show_enlarged(self.get_toplevel(), p))
                box.pack_start(btn, False, False, 0)
            except Exception:
                pass

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
        else:
            # per-card stage checkboxes
            self.checks = {}
            for sid, label, default in STAGES:
                cb = Gtk.CheckButton(label=label)
                cb.set_active(default)
                self.checks[sid] = cb
                box.pack_start(cb, False, False, 0)

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
        header = Gtk.HeaderBar(title="System Replica")
        header.set_subtitle("Config & Theme Installer")
        header.set_show_close_button(True)
        # ensure a maximize (and minimize) button is present in the title bar
        header.set_decoration_layout("icon:minimize,maximize,close")
        self.set_titlebar(header)
        self.set_title("System Replica")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.set_border_width(18)
        self.add(outer)

        # --- intro paragraph --------------------------------------------------
        intro = Gtk.Label(label=INTRO)
        intro.set_line_wrap(True)
        intro.set_xalign(0.0)
        intro.set_max_width_chars(64)
        outer.pack_start(intro, False, False, 0)

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
