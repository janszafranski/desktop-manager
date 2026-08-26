#!/usr/bin/env bash
# uninstall.sh — remove the "shudderopen" KWin effect and restore KWin's stock
# Scale open animation. Run as your normal user.
set -euo pipefail

log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }

[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

DEST="$HOME/.local/share/kwin/effects/shudderopen"

if command -v kwriteconfig6 >/dev/null 2>&1; then
  kwriteconfig6 --file kwinrc --group Plugins --key shudderopenEnabled false
  kwriteconfig6 --file kwinrc --group Plugins --key scaleEnabled true
  log "Disabled shudderopen, re-enabled stock Scale (kwinrc [Plugins])"
else
  warn "kwriteconfig6 not found — toggle the effects back in System Settings → Desktop Effects."
fi

if [[ -d "$DEST" ]]; then
  rm -rf "$DEST"
  log "Removed $DEST"
fi

if command -v qdbus6 >/dev/null 2>&1 && qdbus6 org.kde.KWin /Effects >/dev/null 2>&1; then
  qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect shudderopen >/dev/null 2>&1 || true
  qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect   scale       >/dev/null 2>&1 || true
  qdbus6 org.kde.KWin /KWin    org.kde.KWin.reconfigure                       >/dev/null 2>&1 || true
  log "Reloaded KWin effects live."
fi

log "Done."
