#!/usr/bin/env bash
# uninstall.sh — flip the SDDM login screen off "White Tiger".
#
# Restores whatever login theme was active before install.sh ran. Since White
# Tiger is this repo's default, the fallback when nothing was remembered is
# SDDM's stock "breeze" theme. The White-Tiger theme files are left on disk so
# re-installing is instant; pass --purge to also remove them.
#
# Does NOT restart sddm.service; the change applies at the next login screen.
set -euo pipefail

log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root (the script uses sudo when needed)."

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="/etc/sddm.conf.d/kde_settings.conf"
DEST="/usr/share/sddm/themes/White-Tiger"

# restore the remembered previous theme, or fall back to SDDM's stock breeze
target="breeze"
[[ -f "$HERE/.prev-theme" ]] && target="$(cat "$HERE/.prev-theme")"
[[ "$target" == "White-Tiger" ]] && target="breeze"

log "Restoring SDDM login theme to $target in $CONF (sudo)"
if command -v kwriteconfig6 >/dev/null 2>&1; then
  sudo kwriteconfig6 --file "$CONF" --group Theme --key Current "$target"
else
  sudo sed -i "/^\[Theme\]/,/^\[/ s/^Current=.*/Current=$target/" "$CONF"
fi
rm -f "$HERE/.prev-theme"

if [[ "${1:-}" == "--purge" ]]; then
  log "Removing installed theme files $DEST (sudo)"
  sudo rm -rf "$DEST"
fi

log "Done! Login screen restored to $target (applies at next login / reboot)."
