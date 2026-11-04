#!/usr/bin/env bash
# uninstall.sh — remove the omarchy-launcher and its Hyprland wiring.
# Leaves your categories.json and appearance.json in place (your data).
#
# Destinations are resolved from the SESSION's environment, not this shell's —
# installing to one root and uninstalling from another leaves the app running.
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

CFG_DIR="$XDGS_CONFIG_HOME/omarchy-launcher"

pkill -f '(^|/)qs -c omarchy-launcher( |$)' 2>/dev/null || true

log "Removing files"
rm -f  "$XDGS_BIN_DIR/omarchy-launcher"
rm -rf "$XDGS_CONFIG_HOME/quickshell/omarchy-launcher"
log "Kept $CFG_DIR (delete it by hand if you want your categories gone)."

# Every config root, not just this session's: an install from before JAN-78
# wired up a hardcoded ~/.config, and leaving that behind means a dangling
# autostart for a launcher that is no longer installed.
for lua in "$XDGS_HOME"/.config*/hypr/*.lua "$XDGS_HOME"/.config*/hypr/custom/*.lua; do
  [[ -f "$lua" ]] && grep -qF "omarchy-launcher (desktop-manager)" "$lua" || continue
  log "Removing the Hyprland wiring in $lua"
  sed -i '/-- >>> omarchy-launcher (desktop-manager) >>>/,/-- <<< omarchy-launcher (desktop-manager) <<</d' "$lua"
done
command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
log "Done."
