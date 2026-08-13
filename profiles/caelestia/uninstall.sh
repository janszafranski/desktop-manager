#!/usr/bin/env bash
# uninstall.sh — remove the Caelestia session added by install.sh.
# Removes the SDDM session entry and the Hyprland config (backed up first).
# Does NOT remove packages by default — see the note at the end.
set -euo pipefail
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }

log "Removing the 'Caelestia' login session entry (sudo)…"
sudo rm -f /usr/share/wayland-sessions/caelestia.desktop

HYPR="$HOME/.config/hypr"
if [[ -e "$HYPR/hyprland.conf" ]]; then
  bak="$HYPR/hyprland.conf.removed-$(date +%Y%m%d-%H%M%S)"
  mv "$HYPR/hyprland.conf" "$bak"; warn "moved hyprland.conf -> $bak"
fi

log "Done. The Caelestia session no longer appears at login; KDE Plasma is unaffected."
echo
echo "To also remove the packages (optional):"
echo "  yay -Rns hyprland caelestia-shell caelestia-cli xdg-desktop-portal-hyprland"
echo "(leave alacritty / qt6-wayland / polkit-kde-agent — other things may use them)"
