#!/usr/bin/env bash
# uninstall.sh — remove the OpenClaw flyout (panel, bridge, service, wiring).
set -euo pipefail
log() { printf '\033[1;36m::\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

pkill -f "qs -c openclaw-sidebar" 2>/dev/null || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now openclaw-ai-bridge.service 2>/dev/null || true
fi
log "Removing files"
rm -f "$HOME/.local/bin/openclaw-ai-bridge.js" \
      "$HOME/.local/bin/openclaw-cli-chat.sh" \
      "$HOME/.local/bin/openclaw-dashboard.sh" \
      "$HOME/.config/systemd/user/openclaw-ai-bridge.service"
rm -rf "$HOME/.config/quickshell/openclaw-sidebar"
command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload || true

LUA="$HOME/.config/hypr/hyprland.lua"
if [[ -f "$LUA" ]] && grep -qF "openclaw-flyout (desktop-manager)" "$LUA"; then
  log "Removing Hyprland wiring"
  sed -i '/-- >>> openclaw-flyout (desktop-manager) >>>/,/-- <<< openclaw-flyout (desktop-manager) <<</d' "$LUA"
  command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
fi
log "Done."
