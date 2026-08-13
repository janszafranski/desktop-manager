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
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib  # noqa: E402

# Stable app id / WM_CLASS so window rules and the .desktop icon can match it.
GLib.set_prgname("system-replica")

# --- desktop configurations -------------------------------------------------
# Add more dicts here to grow the grid. Each becomes a card/cell.
#   name/desc : shown on the card
#   image     : thumbnail path (the first card's image is overridden by --image)
CONFIGS = [
    {
        "key": "current",
        "name": "Current desktop",
        "desc": "KDE Plasma 6 · Nordic-bluish · Krohnkite tiling · Alacritty",
        "image": None,
    },
    # {"key": "alt", "name": "Alternative look", "desc": "...", "image": "..."},
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


class Card(Gtk.Frame):
    """One selectable desktop configuration: radio + thumbnail + options."""

    def __init__(self, cfg, group, image_override):
        super().__init__()
        self.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.key = cfg["key"]

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        self.add(box)

        # selector + title
        self.radio = Gtk.RadioButton.new_with_label_from_widget(group, cfg["name"])
        self.radio.get_child().set_markup(f"<b>{cfg['name']}</b>")
        box.pack_start(self.radio, False, False, 0)

        # thumbnail
        img_path = image_override or cfg.get("image")
        if img_path:
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file(img_path)
                box.pack_start(Gtk.Image.new_from_pixbuf(pix), False, False, 0)
            except Exception:
                pass

        # description
        desc = Gtk.Label()
        desc.set_markup(f"<small>{cfg['desc']}</small>")
        desc.set_halign(Gtk.Align.START)
        desc.set_line_wrap(True)
        box.pack_start(desc, False, False, 0)

        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                       False, False, 2)

        # per-card stage checkboxes
        self.checks = {}
        for sid, label, default in STAGES:
            cb = Gtk.CheckButton(label=label)
            cb.set_active(default)
            self.checks[sid] = cb
            box.pack_start(cb, False, False, 0)

    def selected_stages(self):
        return [sid for sid, cb in self.checks.items() if cb.get_active()]


class ReplicaWindow(Gtk.Window):
    def __init__(self, image_override):
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
            card = Card(cfg, group, override)
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

    def on_install(self, *_):
        card = self.active_card()
        stages = card.selected_stages()
        if not stages:
            dlg = Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Select at least one thing to install.")
            dlg.run()
            dlg.destroy()
            return
        self.result = (stages, "--dry-run" if self.dry.get_active() else "")
        self.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None)
    args = ap.parse_args()

    win = ReplicaWindow(args.image)
    win.show_all()
    Gtk.main()

    if not win.result:
        sys.exit(1)
    stages, dry = win.result
    print(" ".join(stages))
    print(dry)


if __name__ == "__main__":
    main()
