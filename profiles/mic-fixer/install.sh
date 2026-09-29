#!/usr/bin/env bash
# install.sh — Mic Fixer: pick a microphone, record a test clip, and see what is
# wrong with it. Two builds ship together:
#   * mic-fixer      native GTK4 / libadwaita + GStreamer window (no browser)
#   * mic-fixer-web  the same tool served to a Chromium app-window over 127.0.0.1
# Both are installed; launch whichever you prefer from the menu. Run as your
# normal user.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

BIN="$HOME/.local/bin"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"

command -v python3 >/dev/null 2>&1 || die "python3 not found."
python3 -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1"); gi.require_version("Gst","1.0")' 2>/dev/null \
  || warn "Native build needs PyGObject with GTK4, libadwaita and GStreamer (python-gobject, gtk4, libadwaita, gstreamer, gst-plugins-good). The browser build works without them."
python3 -c 'import numpy' 2>/dev/null || warn "Native build needs numpy (python-numpy)."

log "Installing the native build"
install -Dm755 "$SELF/mic-fixer"    "$BIN/mic-fixer"
install -Dm755 "$SELF/mic-fixer.py" "$DATA/mic-fixer/mic-fixer.py"

log "Installing the browser build"
install -Dm755 "$SELF/mic-fixer-web"     "$BIN/mic-fixer-web"
install -Dm644 "$SELF/web/mic-fixer.html" "$DATA/mic-fixer-web/mic-fixer.html"
install -Dm755 "$SELF/web/serve.py"       "$DATA/mic-fixer-web/serve.py"

log "Installing menu entries"
# The shipped .desktop files carry an absolute Exec path from the machine they
# were captured on; rewrite it to this user's $HOME so the profile is portable.
for d in mic-fixer.desktop mic-fixer-web.desktop; do
  install -Dm644 "$SELF/$d" "$APPS/$d"
  sed -i "s|Exec=/home/[^/]*/.local/bin/|Exec=$BIN/|" "$APPS/$d"
done
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

log "Done. Launch \"Mic Fixer\" from your app menu, or run: mic-fixer"
warn "If ~/.local/bin is not on your PATH, add it to use the commands directly."
