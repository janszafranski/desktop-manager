#!/usr/bin/env bash
# install.sh — add a fast-open "shudder" window animation to KDE Plasma (KWin).
#
# KWin has no spring/bezier physics like Hyprland, but its animation engine speaks
# QEasingCurve. This installs a small scripted KWin effect ("shudderopen") that scales
# windows in from 70% with an OutBack overshoot = a fast open with a bouncy stop (the
# Plasma analogue of the Hyprland shudder spring on the Caelestia/end4 sessions).
# Swap SHUDDER_CURVE to QEasingCurve.OutElastic in main.js for a stronger multi-wobble.
#
# Enables the effect and disables KWin's stock Scale open effect (so they don't fight).
# Run as your normal user. Applies immediately if KWin is running, else at next login.
set -euo pipefail

log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/shudderopen"
DEST="$HOME/.local/share/kwin/effects/shudderopen"

[[ -d "$SRC" ]] || die "Bundled effect missing: $SRC"
command -v python3 >/dev/null 2>&1 && python3 -c "import json,sys;json.load(open('$SRC/metadata.json'))" \
  || warn "Could not validate metadata.json (python3 missing?) — continuing."

# 1. deploy the scripted effect
log "Installing KWin effect → $DEST"
mkdir -p "$DEST"
cp -a "$SRC/." "$DEST/"

# 2. enable it + disable the stock Scale open effect
if command -v kwriteconfig6 >/dev/null 2>&1; then
  kwriteconfig6 --file kwinrc --group Plugins --key shudderopenEnabled true
  kwriteconfig6 --file kwinrc --group Plugins --key scaleEnabled false
  log "Enabled shudderopen, disabled stock Scale (kwinrc [Plugins])"
else
  warn "kwriteconfig6 not found — enable 'Shudder Open' and disable 'Scale' in System Settings → Desktop Effects."
fi

# 3. hot-reload KWin if it's the running compositor (else applies next login)
if command -v qdbus6 >/dev/null 2>&1 && qdbus6 org.kde.KWin /Effects >/dev/null 2>&1; then
  qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect scale       >/dev/null 2>&1 || true
  qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect   shudderopen >/dev/null 2>&1 || true
  qdbus6 org.kde.KWin /KWin    org.kde.KWin.reconfigure                       >/dev/null 2>&1 || true
  log "Reloaded KWin effects live."
else
  log "KWin not running (or qdbus6 missing) — the effect applies at next Plasma login."
fi

log "Done. Open a window to see the bounce."
