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

say() { printf '\033[1;34m::\033[0m %s\n' "$*"; }

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

say "Done. Review with: git -C '$REPO' status"
