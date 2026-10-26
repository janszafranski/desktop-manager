#!/usr/bin/env bash
# Installs omarchy-desktop-icons into ~/.local/share and puts the launcher on
# $PATH. Run it from inside the source directory:  ./install.sh
#
# Vendored into desktop-manager as profiles/omarchy-desktop-icons, so it is also
# what Desktop Manager → Apps → Utilities → "Desktop icons → Install" runs.
set -euo pipefail

SRC="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-desktop-icons"
BIN="$HOME/.local/bin"

if ! command -v qs >/dev/null 2>&1; then
    echo "quickshell is not installed. On Omarchy / Arch:"
    echo "    yay -S quickshell        # or: yay -S quickshell-git"
    exit 1
fi

echo "Installing to $DEST"
mkdir -p "$DEST" "$BIN"
cp -r "$SRC"/*.qml "$SRC"/bin "$SRC"/packaging "$SRC"/docs \
      "$SRC"/config.example.json "$SRC"/uninstall.sh "$SRC"/VERSION "$DEST"/
# The app's own manual ships in this profile as APP-README.md (README.md here is
# the Desktop Manager-facing one); install it under its upstream name, because
# the uninstall instructions tell you to cd into $DEST and read it.
cp "$SRC/APP-README.md" "$DEST/README.md"
chmod +x "$DEST"/bin/omarchy-desktop-icons "$DEST"/uninstall.sh
ln -sf "$DEST/bin/omarchy-desktop-icons" "$BIN/omarchy-desktop-icons"

mkdir -p "$HOME/.config/systemd/user"
cp "$SRC/packaging/omarchy-desktop-icons.service" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload 2>/dev/null || true

cat <<EOF

Installed.

Start it now:
    omarchy-desktop-icons

Start it every login — pick ONE:

  A) Hyprland autostart (recommended on Omarchy)
     Lua config  (~/.config/hypr/autostart.lua):
         o.launch_on_start("omarchy-desktop-icons")
     Older .conf (~/.config/hypr/hyprland.conf):
         exec-once = omarchy-desktop-icons

  B) systemd user unit (only if your session reaches graphical-session.target,
     e.g. you start Hyprland through uwsm)
         systemctl --user enable --now omarchy-desktop-icons

If ~/.local/bin is not on your PATH, add it to ~/.bashrc:
    export PATH="\$HOME/.local/bin:\$PATH"
EOF
