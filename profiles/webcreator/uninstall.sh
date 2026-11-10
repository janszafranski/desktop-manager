#!/usr/bin/env bash
# uninstall.sh — remove just a... WEBcreator, its launcher, its menu entry and
# the .webc file type. Your sites are your own files and are never touched;
# --purge additionally drops the app's saved window state and settings.
set -euo pipefail
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

BIN="$HOME/.local/bin"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"
MIME="$DATA/mime"
PURGE=0; [[ "${1:-}" == "--purge" ]] && PURGE=1

log "Removing the app and its launcher"
rm -f "$BIN/webcreator"
rm -f "$DATA/webcreator/webcreator.py" "$DATA/webcreator/webcreator.py.bak" \
      "$DATA/webcreator/test_webplus_import.py" "$DATA/webcreator/serif-templates.json"
rm -rf "$DATA/webcreator/__pycache__"
# Leave the directory if anything else is in it (a git checkout of the app, say).
rmdir "$DATA/webcreator" 2>/dev/null || true

log "Removing the menu entry and the .webc file type"
rm -f "$APPS/webcreator.desktop" "$MIME/packages/webcreator.xml"
command -v update-mime-database    >/dev/null && update-mime-database "$MIME" 2>/dev/null || true
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

if [[ $PURGE -eq 1 ]]; then
  log "Purging saved settings and window state"
  rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/justawebcreator/"*.conf
  rmdir "${XDG_CONFIG_HOME:-$HOME/.config}/justawebcreator" 2>/dev/null || true
  rm -f "${XDG_STATE_HOME:-$HOME/.local/state}/WEBcreatorstaterc"
fi

log "Done. Your .webc sites and anything you published are untouched."
