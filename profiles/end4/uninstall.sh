#!/usr/bin/env bash
# uninstall.sh — remove the "illogical-impulse" (end-4) session added by
# install.sh. Removes the login session entry, the launch wrapper, and the
# isolated config tree (~/.config-ii, backed up first). Does NOT remove shared
# packages, and never touches your default ~/.config (Caelestia / KDE).
set -euo pipefail

log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }

II_CONFIG="$HOME/.config-ii"
WRAPPER="$HOME/.local/bin/start-hypr-ii"
SESSION="/usr/share/wayland-sessions/hyprland-ii.desktop"

log "Removing the login session entry (sudo)…"
sudo rm -f "$SESSION"

log "Removing the launch wrapper…"
rm -f "$WRAPPER"

if [[ -d "$II_CONFIG" ]]; then
  bak="$II_CONFIG.removed-$(date +%Y%m%d-%H%M%S)"
  mv "$II_CONFIG" "$bak"
  warn "moved $II_CONFIG -> $bak (delete it yourself when you're sure)"
fi

log "Done. The illogical-impulse session no longer appears at login."
echo
echo "Shared packages were left installed. To remove end-4-specific extras (optional):"
echo "  yay -Rns illogical-impulse-bibata-modern-classic-bin  # cursor, if installed"
echo "  # cava / pavucontrol-qt / playerctl are generally useful — leave them."
echo "Your default session (Caelestia / KDE) is untouched."
