#!/usr/bin/env bash
# Removes everything this app installed. Your config is left alone unless you
# pass --purge.
set -euo pipefail

DEST="${XDG_DATA_HOME:-$HOME/.local/share}/omarchy-desktop-icons"
CONFDIR="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy-desktop-icons"

"$DEST/bin/omarchy-desktop-icons" stop 2>/dev/null || true
systemctl --user disable --now omarchy-desktop-icons 2>/dev/null || true

rm -f "$HOME/.config/systemd/user/omarchy-desktop-icons.service"
rm -f "$HOME/.local/bin/omarchy-desktop-icons"
rm -rf "$DEST"
systemctl --user daemon-reload 2>/dev/null || true

if [ "${1:-}" = "--purge" ]; then
    rm -rf "$CONFDIR"
    echo "Removed $CONFDIR too."
else
    echo "Left your icons in $CONFDIR (use --purge to delete them)."
fi

echo "Also remove the autostart line you added to ~/.config/hypr/autostart.lua"
echo "or ~/.config/hypr/hyprland.conf, if you added one."
