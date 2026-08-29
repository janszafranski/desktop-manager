#!/usr/bin/env bash
# uninstall.sh — remove the Keyboard shortcuts widget + its Hyprland wiring.
set -euo pipefail
log() { printf '\033[1;36m::\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

pkill -f "qs -c keybinds" 2>/dev/null || true
log "Removing files"
rm -f "$HOME/.config/quickshell/keybinds/shell.qml"
rmdir "$HOME/.config/quickshell/keybinds" 2>/dev/null || true
rm -f "$HOME/.config/hypr/scripts/keybinds.sh" "$HOME/.config/hypr/scripts/keybinds-toggle.sh"

LUA="$HOME/.config/hypr/hyprland.lua"
if [[ -f "$LUA" ]] && grep -qF "keybinds-widget (desktop-manager)" "$LUA"; then
  log "Removing Hyprland wiring"
  sed -i '/-- >>> keybinds-widget (desktop-manager) >>>/,/-- <<< keybinds-widget (desktop-manager) <<</d' "$LUA"
  command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
fi
log "Done."
