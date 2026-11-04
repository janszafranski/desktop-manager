#!/usr/bin/env bash
# uninstall.sh — remove the Keyboard shortcuts cheat-sheet (both DE variants).
#
# Destinations are resolved from the SESSION's environment, not this shell's —
# installing to one root and uninstalling from another leaves the widget running.
set -euo pipefail
SELF="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
log() { printf '\033[1;36m::\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

for candidate in "$SELF/../../scripts/xdg-session-paths.sh" "$SELF/xdg-session-paths.sh"; do
  if [[ -r "$candidate" ]]; then
    # shellcheck source=../../scripts/xdg-session-paths.sh
    . "$candidate"
    break
  fi
done
command -v xdg_session_paths_resolve >/dev/null 2>&1 \
  || { echo "xdg-session-paths.sh not found next to this script" >&2; exit 1; }
xdg_session_paths_resolve

pkill -f '(^|/)qs -c keybinds( |$)' 2>/dev/null || true
pkill -f '(^|/)qs -c kde-keybinds( |$)' 2>/dev/null || true

log "Removing files"
rm -rf "$XDGS_CONFIG_HOME/quickshell/keybinds" "$XDGS_CONFIG_HOME/quickshell/kde-keybinds"
rm -f  "$XDGS_BIN_DIR/keybinds.sh" "$XDGS_BIN_DIR/keybinds-toggle.sh"
rm -f  "$XDGS_DATA_HOME/applications/kde-keybinds-toggle.desktop" \
       "$XDGS_DATA_HOME/applications/kde-keybinds-yad.desktop"
# Pre-JAN-78 installs put the toggle scripts under a hardcoded ~/.config.
rm -f  "$XDGS_HOME/.config/hypr/scripts/keybinds.sh" \
       "$XDGS_HOME/.config/hypr/scripts/keybinds-toggle.sh"
command -v update-desktop-database >/dev/null && \
  update-desktop-database "$XDGS_DATA_HOME/applications" 2>/dev/null || true

# Every config root, not just this session's: an install from before JAN-78
# wired up a hardcoded ~/.config, and leaving that behind means a dangling
# keybind for a widget that is no longer installed.
for lua in "$XDGS_HOME"/.config*/hypr/*.lua "$XDGS_HOME"/.config*/hypr/custom/*.lua; do
  [[ -f "$lua" ]] && grep -qF "keybinds-widget (desktop-manager)" "$lua" || continue
  log "Removing the Hyprland wiring in $lua"
  sed -i '/-- >>> keybinds-widget (desktop-manager) >>>/,/-- <<< keybinds-widget (desktop-manager) <<</d' "$lua"
done
command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
log "Done."
