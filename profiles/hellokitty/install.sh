#!/usr/bin/env bash
# install.sh — switch the SDDM login screen to the "Hello Kitty" theme.
#
# Non-destructive: it deploys the bundled Hello-Kitty theme alongside the
# existing White-Tiger theme and points SDDM at it. White-Tiger stays on disk
# and remains this repo's default — uninstall.sh flips SDDM back to it.
#
# We do NOT restart sddm.service (that would kill the running session); the new
# login screen applies at the next logout / reboot.
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
SRC="$REPO/files/system/usr/share/sddm/themes/Hello-Kitty"
DEST="/usr/share/sddm/themes/Hello-Kitty"
CONF="/etc/sddm.conf.d/kde_settings.conf"

[[ -d "$SRC" ]] || die "Bundled theme missing: $SRC"

# 0. which background? The GUI writes the pick to .bg-choice; default otherwise.
BG_DEFAULT="Background-Sitting.jpg"
bg="$BG_DEFAULT"
[[ -f "$HERE/.bg-choice" ]] && bg="$(tr -d '[:space:]' < "$HERE/.bg-choice")"
# only accept a name that actually ships with the theme
if [[ ! -f "$SRC/$bg" ]]; then
  warn "Chosen background '$bg' not found in theme; using $BG_DEFAULT."
  bg="$BG_DEFAULT"
fi
log "Background: $bg"

# 1. deploy the theme (sudo; /usr/share)
log "Installing the Hello Kitty SDDM theme -> $DEST (sudo)"
sudo mkdir -p "$DEST"
sudo cp -a "$SRC/." "$DEST/"

# 1b. bake the chosen background into the deployed theme.conf.user (the
# `background=` key overrides theme.conf; see Main.qml `config.background`).
log "Setting login background to $bg"
if command -v kwriteconfig6 >/dev/null 2>&1; then
  sudo kwriteconfig6 --file "$DEST/theme.conf.user" --group General --key background "$bg"
else
  sudo sed -i "s|^background=.*|background=$bg|" "$DEST/theme.conf.user"
fi

# 2. point SDDM at it, remembering the previous theme so uninstall can restore it
prev="$(kreadconfig6 --file "$CONF" --group Theme --key Current 2>/dev/null || true)"
[[ -z "$prev" ]] && prev="White-Tiger"
if [[ "$prev" != "Hello-Kitty" ]]; then
  echo "$prev" > "$HERE/.prev-theme"
  log "Remembered current login theme: $prev (uninstall.sh restores it)"
fi

log "Setting SDDM theme to Hello-Kitty in $CONF (sudo)"
if command -v kwriteconfig6 >/dev/null 2>&1; then
  sudo kwriteconfig6 --file "$CONF" --group Theme --key Current Hello-Kitty
else
  # fallback: rewrite the Current= line inside the [Theme] section
  sudo sed -i '/^\[Theme\]/,/^\[/ s/^Current=.*/Current=Hello-Kitty/' "$CONF"
fi

log "Done! Hello Kitty is now the login theme."
echo
echo "  It applies at the NEXT login screen (log out or reboot) — sddm.service"
echo "  is deliberately not restarted so this session stays alive."
echo "  Undo any time with this profile's \"Uninstall it\" option."
