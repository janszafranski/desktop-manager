#!/usr/bin/env bash
# install.sh — just a... WEBcreator: design a website by laying pages out, then
# publish it as plain HTML. One Python file plus a launcher, a menu entry and
# the .webc file type. Run as your normal user; nothing here needs root.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

BIN="$HOME/.local/bin"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS="$DATA/applications"
MIME="$DATA/mime"

command -v python3 >/dev/null 2>&1 || die "python3 not found."
python3 -c 'import PySide6' 2>/dev/null \
  || die "Needs PySide6 — the distro package, not pip, so the app follows your desktop theme:
     sudo pacman -S --needed pyside6"
python3 -c 'import bs4' 2>/dev/null \
  || warn "File ▸ Import Website Folder… needs BeautifulSoup: sudo pacman -S --needed python-beautifulsoup4"
python3 -c 'import PySide6.QtWebEngineWidgets' 2>/dev/null \
  || warn "Imported pages match the original layout only with qt6-webengine installed; without it they reflow."

log "Installing the app"
install -Dm755 "$SELF/webcreator.py" "$DATA/webcreator/webcreator.py"
install -Dm644 "$SELF/test_webplus_import.py" "$DATA/webcreator/test_webplus_import.py"
# The 89 template page trees and their colour schemes. The app runs without
# it — the Startup Assistant just falls back to the three design templates —
# so this is installed beside the app, not demanded by it.
install -Dm644 "$SELF/serif-templates.json" "$DATA/webcreator/serif-templates.json"

log "Installing the launcher"
install -d "$BIN"
cat > "$BIN/webcreator" <<'LAUNCH'
#!/usr/bin/env bash
exec python3 "${XDG_DATA_HOME:-$HOME/.local/share}/webcreator/webcreator.py" "$@"
LAUNCH
chmod 755 "$BIN/webcreator"

log "Installing the menu entry and the .webc file type"
# The shipped .desktop says Exec=webcreator, which only works if ~/.local/bin is
# on PATH — and a desktop launcher often has a shorter PATH than your shell.
# Write the absolute path in, the way the other profiles here do.
install -d "$APPS"
sed "s|^Exec=webcreator|Exec=$BIN/webcreator|" "$SELF/webcreator.desktop" > "$APPS/webcreator.desktop"
chmod 644 "$APPS/webcreator.desktop"
install -Dm644 "$SELF/webcreator-mime.xml" "$MIME/packages/webcreator.xml"
command -v update-mime-database    >/dev/null && update-mime-database "$MIME" 2>/dev/null || true
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
command -v xdg-mime >/dev/null && xdg-mime default webcreator.desktop application/x-webcreator-site 2>/dev/null || true

# Opening Serif WebPlus .wpp sites is the one thing that needs something else on
# the machine: the Serif-for-Linux checkout, whose serif.webplus does the
# reading. Everything else works without it, so this is a note, not a failure.
if ! python3 - <<'PY' 2>/dev/null
import os, sys
for p in ('~/src/serif-linux', '~/Documents/Development/serif-linux', '~/serif-linux', '~/.local/opt/serif-linux'):
    if os.path.isfile(os.path.join(os.path.expanduser(p), 'serif', 'webplus.py')):
        sys.exit(0)
sys.exit(1)
PY
then
  warn "No Serif-for-Linux checkout found, so File ▸ Open Serif WebPlus Site… will ask where it is.
     Everything else — new sites, templates, importing a website folder, publishing — works without it."
fi

log "Done. Open \"just a... WEBcreator\" from your app menu, or run: webcreator"
warn "If ~/.local/bin is not on your PATH, add it to use the command directly."
