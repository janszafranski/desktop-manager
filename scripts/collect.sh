#!/usr/bin/env bash
# collect.sh — snapshot the current machine's config/look into this repo.
# Re-runnable: refreshes the bundled files and regenerates package lists.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
FILES="$REPO/files"
PKGS="$REPO/packages"
# shellcheck source=manifest.sh
source "$SCRIPT_DIR/manifest.sh"

say()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }

# copy SRC (abs) into DEST_ROOT preserving the relative path REL
copy_into() {
  local src="$1" dest_root="$2" rel="$3"
  [[ -e "$src" ]] || return 0
  local dest="$dest_root/$rel"
  mkdir -p "$(dirname "$dest")"
  if [[ -d "$src" ]]; then
    rm -rf "$dest"
    cp -a "$src" "$(dirname "$dest")/"
  else
    cp -a "$src" "$dest"
  fi
  echo "  + $rel"
}

# Resolve the currently-selected SDDM theme by scanning the login-manager
# config (/etc/sddm.conf plus every drop-in in /etc/sddm.conf.d/). The last
# non-empty `Current=` wins, matching SDDM's own drop-in override order.
sddm_current_theme() {
  local f v t=""
  for f in /etc/sddm.conf /etc/sddm.conf.d/*.conf; do
    [[ -e "$f" ]] || continue
    v="$(sed -n 's/^[[:space:]]*Current[[:space:]]*=[[:space:]]*//p' "$f" | tail -n1)"
    [[ -n "$v" ]] && t="$v"
  done
  printf '%s' "$t"
}

# Snapshot the SDDM login screen: the config drop-ins plus whichever theme is
# currently active. System files (/etc, /usr/share) are world-readable, so no
# sudo is needed to collect. They land under files/system/ mirroring their
# absolute paths, so install.sh can deploy them straight back to "/".
# Re-running always captures the *current* theme, so changing your login look
# and re-collecting is all it takes to update the bundle.
collect_sddm() {
  if [[ ! -e /etc/sddm.conf && ! -d /etc/sddm.conf.d ]]; then
    say "No SDDM config found — skipping login-screen snapshot"
    return 0
  fi
  say "Collecting SDDM login screen (config + active theme)"
  local sys="$FILES/system"
  copy_into /etc/sddm.conf "$sys" "etc/sddm.conf"
  local c
  for c in /etc/sddm.conf.d/*.conf; do
    [[ -e "$c" ]] || continue
    copy_into "$c" "$sys" "etc/sddm.conf.d/$(basename "$c")"
  done
  local theme; theme="$(sddm_current_theme)"
  if [[ -n "$theme" && -d "/usr/share/sddm/themes/$theme" ]]; then
    copy_into "/usr/share/sddm/themes/$theme" "$sys" "usr/share/sddm/themes/$theme"
    echo "  active theme: $theme"
  else
    warn "Could not resolve current SDDM theme dir (Current='${theme:-unset}') — only config bundled"
  fi
}

collect_all() {
  say "Collecting HOME dotfiles"
  for item in "${HOME_ITEMS[@]}"; do
    copy_into "$HOME/$item" "$FILES/home" "$item"
  done

  say "Collecting ~/.config"
  for item in "${CONFIG_ITEMS[@]}"; do
    copy_into "$HOME/.config/$item" "$FILES/config" "$item"
  done

  say "Collecting ~/.local/share (themes, cursors, kwin scripts, wallpapers)"
  for item in "${LOCALSHARE_ITEMS[@]}"; do
    copy_into "$HOME/.local/share/$item" "$FILES/local-share" "$item"
  done

  say "Collecting ~/.icons"
  for item in "${ICONS_ITEMS[@]}"; do
    copy_into "$HOME/.icons/$item" "$FILES/icons" "$item"
  done

  say "Collecting ~/bin scripts"
  for item in "${BIN_ITEMS[@]}"; do
    copy_into "$HOME/bin/$item" "$FILES/bin" "$item"
  done

  if [[ "${REPLICA_INCLUDE_PICTURES:-0}" == "1" ]]; then
    say "Collecting Pictures/Wallpapers (REPLICA_INCLUDE_PICTURES=1)"
    for item in "${PICTURES_ITEMS[@]}"; do
      copy_into "$HOME/$item" "$FILES/pictures" "$item"
    done
  fi

  collect_sddm

  say "Generating package lists"
  # Native, explicitly-installed packages that are NOT from AUR/foreign
  comm -23 <(pacman -Qqe | sort) <(pacman -Qqm | sort) > "$PKGS/pacman-native.txt"
  # Foreign (AUR / manually built) packages
  pacman -Qqm | sort > "$PKGS/aur.txt"
  echo "  native: $(wc -l < "$PKGS/pacman-native.txt") packages"
  echo "  aur:    $(wc -l < "$PKGS/aur.txt") packages"

  say "Recording enabled user services"
  systemctl --user list-unit-files --state=enabled --no-legend 2>/dev/null \
    | awk '{print $1}' > "$PKGS/user-services-enabled.txt" || true
}

main() {
  local target="${1:-all}"
  case "$target" in
    all)  collect_all ;;
    sddm) collect_sddm ;;
    *) warn "Unknown collect target: $target  (use: all | sddm)"; exit 1 ;;
  esac
  say "Done. Review with: git -C '$REPO' status"
}

main "$@"
