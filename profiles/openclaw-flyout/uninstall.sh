#!/usr/bin/env bash
# uninstall.sh — remove the OpenClaw flyout.
#
# The flyout lives in its own repo (github.com/janszafranski/openclaw-flyout);
# this profile clones it to a cache and runs its installer. On uninstall, prefer
# the cached repo's own uninstall.sh; fall back to removing the deployed files
# directly if the cache is gone.
set -euo pipefail
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/desktop-manager/openclaw-flyout"

if [[ -f "$CACHE/uninstall.sh" ]]; then
  log "Running the OpenClaw flyout uninstaller from the cached checkout"
  exec bash "$CACHE/uninstall.sh"
fi

# Fallback: cache missing — remove the known deployed artifacts directly.
log "Cache not found — removing deployed files directly"
pkill -f "qs -c openclaw-sidebar" 2>/dev/null || true   # NB: never `pkill qs` blindly
command -v systemctl >/dev/null 2>&1 && systemctl --user disable --now openclaw-ai-bridge.service 2>/dev/null || true
rm -f "$HOME/.local/bin/openclaw-ai-bridge.js" \
      "$HOME/.local/bin/openclaw-cli-chat.sh" \
      "$HOME/.local/bin/openclaw-dashboard.sh" \
      "$HOME/.config/systemd/user/openclaw-ai-bridge.service"
rm -rf "$HOME/.config/quickshell/openclaw-sidebar"
rm -f "$HOME/.config/autostart/openclaw-sidebar.desktop"
command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload || true
LUA="$HOME/.config/hypr/hyprland.lua"
if [[ -f "$LUA" ]] && grep -qF "openclaw-flyout" "$LUA"; then
  log "Removing Hyprland wiring"
  sed -i '/-- >>> openclaw-flyout.*>>>/,/-- <<< openclaw-flyout.*<<</d' "$LUA"
  command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
fi
log "Done."
