#!/usr/bin/env bash
# install.sh — deploy this repo onto a fresh (CachyOS / Arch) install.
#
# Usage:
#   ./install.sh            # everything (prompts before package install)
#   ./install.sh files      # only deploy config files/themes
#   ./install.sh packages   # only install packages
#   ./install.sh services   # only enable user services
#   ./install.sh --dry-run  # show what would happen, change nothing
#
# Existing files are backed up to ~/.config-backup-<timestamp> before overwrite.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
FILES="$REPO/files"
PKGS="$REPO/packages"
# shellcheck source=manifest.sh
source "$SCRIPT_DIR/manifest.sh"

DRY=0
BACKUP="$HOME/.config-backup-$(date +%Y%m%d-%H%M%S)"

say()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
run()  { if [[ $DRY == 1 ]]; then echo "  [dry] $*"; else "$@"; fi; }

# deploy REL from repo dir SRC_ROOT into target dir DEST_ROOT, backing up first
deploy_into() {
  local src_root="$1" dest_root="$2" rel="$3"
  local src="$src_root/$rel" dest="$dest_root/$rel"
  [[ -e "$src" ]] || return 0
  if [[ -e "$dest" || -L "$dest" ]]; then
    local bdest="$BACKUP/${dest#"$HOME"/}"
    run mkdir -p "$(dirname "$bdest")"
    run cp -a "$dest" "$bdest"
    run rm -rf "$dest"
  fi
  run mkdir -p "$(dirname "$dest")"
  run cp -a "$src" "$dest"
  echo "  -> ${dest/#$HOME/\~}"
}

# Apply the just-deployed KDE config to the RUNNING session so a "restore"
# takes effect immediately — no log-out required. Mirrors the manual rescue
# sequence: colour scheme -> KWin reconfigure -> restart plasmashell (which now
# reads the freshly-restored panel/wallpaper layout).
apply_live_kde() {
  say "Applying to the live Plasma session (no log-out needed)"
  # Colour scheme, read back from the deployed kdeglobals.
  local scheme
  scheme="$( (kreadconfig6 --file kdeglobals --group General --key ColorScheme 2>/dev/null \
            || kreadconfig5 --file kdeglobals --group General --key ColorScheme 2>/dev/null) || true )"
  if [[ -n "$scheme" ]] && command -v plasma-apply-colorscheme >/dev/null 2>&1; then
    plasma-apply-colorscheme "$scheme" >/dev/null 2>&1 \
      || plasma-apply-colorscheme "${scheme,,}" >/dev/null 2>&1 || true
  fi
  # KWin: reload decoration, borders, colours and KWin scripts in place.
  qdbus6 org.kde.KWin /KWin reconfigure 2>/dev/null \
    || qdbus org.kde.KWin /KWin reconfigure 2>/dev/null \
    || qdbus-qt6 org.kde.KWin /KWin reconfigure 2>/dev/null || true
  # Panels + wallpaper: bring plasmashell back up against the restored appletsrc.
  setsid -f plasmashell >/dev/null 2>&1 \
    || ( nohup plasmashell >/dev/null 2>&1 & ) || true
  say "Live apply complete — a few already-open apps adopt the colours only when relaunched."
}

install_files() {
  # If a Plasma session is live, stop plasmashell BEFORE copying its config: a
  # running plasmashell keeps the old panel layout in memory and rewrites
  # appletsrc/plasmashellrc on exit, which would clobber the restored panels at
  # the next logout. Stopping first makes the restore actually stick.
  local live_kde=0
  if [[ $DRY == 0 ]] && [[ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]] \
     && pgrep -x plasmashell >/dev/null 2>&1; then
    live_kde=1
  fi
  if [[ $live_kde == 1 ]]; then
    say "Live Plasma session detected — stopping plasmashell so panels restore cleanly"
    kquitapp6 plasmashell 2>/dev/null || kquitapp5 plasmashell 2>/dev/null \
      || killall plasmashell 2>/dev/null || true
  elif [[ $DRY == 1 ]]; then
    echo "  [dry] (in a live Plasma session) would stop plasmashell, deploy, then apply the colour scheme, reconfigure KWin and restart plasmashell"
  fi

  say "Deploying config (backup of any existing files -> $BACKUP)"

  for item in "${HOME_ITEMS[@]}";       do deploy_into "$FILES/home"        "$HOME"              "$item"; done
  for item in "${CONFIG_ITEMS[@]}";     do deploy_into "$FILES/config"      "$HOME/.config"      "$item"; done
  for item in "${LOCALSHARE_ITEMS[@]}"; do deploy_into "$FILES/local-share" "$HOME/.local/share" "$item"; done
  for item in "${ICONS_ITEMS[@]}";      do deploy_into "$FILES/icons"       "$HOME/.icons"       "$item"; done
  for item in "${BIN_ITEMS[@]}";        do deploy_into "$FILES/bin"         "$HOME/bin"          "$item"; done

  if [[ -d "$FILES/pictures" ]]; then
    for item in "${PICTURES_ITEMS[@]}"; do deploy_into "$FILES/pictures" "$HOME" "$item"; done
  fi

  say "Rebuilding caches"
  command -v gtk-update-icon-cache >/dev/null && run gtk-update-icon-cache -f -t "$HOME/.local/share/icons/Nordic-bluish" 2>/dev/null || true
  command -v fc-cache >/dev/null && run fc-cache -f >/dev/null 2>&1 || true
  command -v kbuildsycoca6 >/dev/null && run kbuildsycoca6 >/dev/null 2>&1 || \
    { command -v kbuildsycoca5 >/dev/null && run kbuildsycoca5 >/dev/null 2>&1; } || true

  if [[ $live_kde == 1 ]]; then
    apply_live_kde
  else
    warn "Log out & back in (or restart Plasma) for KDE/KWin/GTK changes to fully apply."
  fi
}

need_aur_helper() {
  command -v yay >/dev/null && { echo yay; return; }
  command -v paru >/dev/null && { echo paru; return; }
  echo ""
}

install_packages() {
  local native="$PKGS/pacman-native.txt" aur="$PKGS/aur.txt"
  [[ -f "$native" ]] || { warn "No package list ($native). Run collect.sh first."; return; }

  say "Installing native packages ($(wc -l < "$native") listed)"
  run sudo pacman -S --needed --noconfirm - < "$native"

  if [[ -s "$aur" ]]; then
    local helper; helper="$(need_aur_helper)"
    if [[ -z "$helper" ]]; then
      warn "No AUR helper (yay/paru) found. Skipping AUR packages:"
      sed 's/^/    /' "$aur"
    else
      say "Installing AUR packages with $helper ($(wc -l < "$aur") listed)"
      run "$helper" -S --needed --noconfirm - < "$aur"
    fi
  fi

  warn "Nordic GTK/icon/cursor themes & KWin tiling scripts are bundled in this"
  warn "repo (not packages) and are deployed by the 'files' step."
}

install_services() {
  local list="$PKGS/user-services-enabled.txt"
  say "Enabling user services"
  run systemctl --user daemon-reload || true
  # Always try the app-specific service we ship a unit for:
  run systemctl --user enable --now shelly-notifications.service 2>/dev/null || \
    warn "shelly-notifications.service not enabled (shelly may not be installed yet)"
  if [[ -f "$list" ]]; then
    while read -r svc; do
      [[ -z "$svc" ]] && continue
      case "$svc" in shelly-notifications.service) continue;; esac
      run systemctl --user enable "$svc" 2>/dev/null || warn "could not enable $svc (may be system-managed)"
    done < "$list"
  fi
}

main() {
  local target="${1:-all}"
  [[ "${*:-}" == *--dry-run* ]] && { DRY=1; say "DRY RUN — no changes will be made"; }
  case "$target" in
    files)    install_files ;;
    packages) install_packages ;;
    services) install_services ;;
    --dry-run|all)
      install_packages
      install_files
      install_services
      ;;
    *) warn "Unknown target: $target"; grep '^#' "$0" | head -12; exit 1 ;;
  esac
  say "Finished."
}
main "$@"
