#!/usr/bin/env bash
# install.sh — set the SDDM login screen to the "White Tiger" theme (this
# repo's default login look).
#
# Deploys the bundled White-Tiger theme and points SDDM at it, remembering the
# previously-active theme so uninstall.sh can restore it. Does NOT restart
# sddm.service (that would end the running session); it applies at next login.
#
# Run as your normal user (NOT root). It prompts for sudo when writing under
# /usr and /etc.
set -euo pipefail

log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root (the script uses sudo when needed)."

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SRC="$REPO/files/system/usr/share/sddm/themes/White-Tiger"
DEST="/usr/share/sddm/themes/White-Tiger"
CONF="/etc/sddm.conf.d/kde_settings.conf"

[[ -d "$SRC" ]] || die "Bundled theme missing: $SRC (run collect.sh sddm while White Tiger is active)."

# 1. deploy the theme (sudo; /usr/share)
log "Installing the White Tiger SDDM theme -> $DEST (sudo)"
sudo mkdir -p "$DEST"
sudo cp -a "$SRC/." "$DEST/"

# 2. point SDDM at it, remembering the previous theme so uninstall can restore it
prev="$(kreadconfig6 --file "$CONF" --group Theme --key Current 2>/dev/null || true)"
if [[ -n "$prev" && "$prev" != "White-Tiger" ]]; then
  echo "$prev" > "$HERE/.prev-theme"
  log "Remembered current login theme: $prev (uninstall.sh restores it)"
fi

log "Setting SDDM theme to White-Tiger in $CONF (sudo)"
if command -v kwriteconfig6 >/dev/null 2>&1; then
  sudo kwriteconfig6 --file "$CONF" --group Theme --key Current White-Tiger
else
  sudo sed -i '/^\[Theme\]/,/^\[/ s/^Current=.*/Current=White-Tiger/' "$CONF"
fi

log "Done! White Tiger is now the login theme."
echo
echo "  It applies at the NEXT login screen (log out or reboot) — sddm.service"
echo "  is deliberately not restarted so this session stays alive."
echo "  Undo any time with this profile's \"Uninstall it\" option."
