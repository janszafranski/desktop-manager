#!/usr/bin/env bash
# uninstall.sh — remove the omarchy-launcher and its Hyprland wiring.
# Leaves ~/.config/omarchy-launcher/categories.json in place (your data).
set -euo pipefail
log() { printf '\033[1;36m::\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

pkill -f "qs -c omarchy-launcher" 2>/dev/null || true

log "Removing files"
rm -f  "$HOME/.local/bin/omarchy-launcher"
rm -rf "$HOME/.config/quickshell/omarchy-launcher"
log "Kept ~/.config/omarchy-launcher/categories.json (delete it by hand if you want it gone)."

LUA="$HOME/.config/hypr/hyprland.lua"
if [[ -f "$LUA" ]] && grep -qF "omarchy-launcher (desktop-manager)" "$LUA"; then
  log "Removing Hyprland wiring (Super+Space binding + autostart)"
  sed -i '/-- >>> omarchy-launcher (desktop-manager) >>>/,/-- <<< omarchy-launcher (desktop-manager) <<</d' "$LUA"
  command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
  log "Note: Super+Space is now unbound — re-add your preferred launcher to hyprland.lua."
fi
log "Done."
