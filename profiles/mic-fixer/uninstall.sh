#!/usr/bin/env bash
# uninstall.sh — remove Mic Fixer (both builds) and its menu entries. Leaves the
# browser build's saved mic-permission profile alone unless --purge is given.
set -euo pipefail
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

BIN="$HOME/.local/bin"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"
PURGE=0; [[ "${1:-}" == "--purge" ]] && PURGE=1

log "Removing binaries and payloads"
rm -f "$BIN/mic-fixer" "$BIN/mic-fixer-web"
rm -f "$DATA/mic-fixer/mic-fixer.py"
rm -f "$DATA/mic-fixer-web/mic-fixer.html" "$DATA/mic-fixer-web/serve.py"
rmdir "$DATA/mic-fixer" 2>/dev/null || true

if [[ $PURGE -eq 1 ]]; then
  log "Purging the browser build's saved profile (mic permission)"
  rm -rf "$DATA/mic-fixer-web/browser-profile"
fi
rmdir "$DATA/mic-fixer-web" 2>/dev/null || true

log "Removing menu entries"
rm -f "$APPS/mic-fixer.desktop" "$APPS/mic-fixer-web.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

log "Done."
