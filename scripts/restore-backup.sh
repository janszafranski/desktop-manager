#!/usr/bin/env bash
# restore-backup.sh — undo an `install.sh files` deploy.
#
# `install.sh files` copies this repo's captured dotfiles over yours, saving
# whatever it replaced into ~/.config-backup-<timestamp> first. This puts those
# files back, and deletes the ones the deploy created where you had nothing.
#
# Usage:
#   ./restore-backup.sh                  # newest ~/.config-backup-* directory
#   ./restore-backup.sh --list           # show the backups you have
#   ./restore-backup.sh --dry-run        # show what would change, change nothing
#   ./restore-backup.sh ~/.config-backup-20261028-093000
#
# Only the user-level "files" stage is reversed. Packages installed by the
# `packages` stage and the system-level SDDM theme are left alone — neither of
# them touches your desktop config.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
FILES="$REPO/files"
# shellcheck source=manifest.sh
source "$SCRIPT_DIR/manifest.sh"

DRY=0
BACKUP=""

say()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
run()  { if [[ $DRY == 1 ]]; then echo "  [dry] $*"; else "$@"; fi; }

list_backups() {
  local found=0 d
  for d in "$HOME"/.config-backup-*; do
    [[ -d "$d" ]] || continue
    found=1
    printf '  %s\n' "${d/#$HOME/\~}"
  done
  [[ $found == 1 ]] || warn "No ~/.config-backup-* directory found — nothing was ever deployed from this repo."
}

# Newest by name: the timestamp suffix sorts chronologically.
newest_backup() {
  local d newest=""
  for d in "$HOME"/.config-backup-*; do
    [[ -d "$d" ]] && newest="$d"
  done
  printf '%s' "$newest"
}

restored=0
removed=0
untouched=0

# Manifest entries like `micro/settings.json` leave an empty `~/.config/micro`
# behind once the file is removed. Walk back up and clear the directories the
# deploy created, stopping at the first one that still has something in it (so
# a directory of your own is never touched) and never going above $HOME.
prune_empty_dirs() {
  local dir="$1"
  while [[ "$dir" != "$HOME" && "$dir" != "/" && -d "$dir" ]]; do
    rmdir "$dir" 2>/dev/null || break
    dir="$(dirname "$dir")"
  done
}

# Reverse one manifest entry. Mirrors install.sh's deploy_into(), in the other
# direction and with the same "did the repo actually ship this?" guard: if it
# did not, the deploy skipped the item and whatever is there now is yours.
restore_item() {
  local src_root="$1" dest_root="$2" rel="$3"
  local src="$src_root/$rel" dest="$dest_root/$rel"
  [[ -e "$src" ]] || return 0

  local back="$BACKUP/${dest#"$HOME"/}"
  if [[ -e "$back" || -L "$back" ]]; then
    run rm -rf "$dest"
    run mkdir -p "$(dirname "$dest")"
    run cp -a "$back" "$dest"
    echo "  restored ${dest/#$HOME/\~}"
    restored=$((restored + 1))
  elif [[ -e "$dest" || -L "$dest" ]]; then
    # Nothing in the backup means you had no such file before the deploy, so
    # the deploy is what put it there. Taking it away is the restore.
    run rm -rf "$dest"
    if [[ $DRY == 0 ]]; then prune_empty_dirs "$(dirname "$dest")"; fi
    echo "  removed  ${dest/#$HOME/\~}  (you had none before)"
    removed=$((removed + 1))
  else
    untouched=$((untouched + 1))
  fi
}

main() {
  local arg
  for arg in "$@"; do
    case "$arg" in
      --dry-run) DRY=1 ;;
      --list)    say "Backups in $HOME:"; list_backups; exit 0 ;;
      -h|--help) grep '^#' "$0" | head -17 | sed 's/^# \{0,1\}//'; exit 0 ;;
      -*)        warn "Unknown option: $arg"; exit 1 ;;
      *)         BACKUP="$arg" ;;
    esac
  done

  [[ -n "$BACKUP" ]] || BACKUP="$(newest_backup)"
  if [[ -z "$BACKUP" ]]; then
    warn "No ~/.config-backup-* directory found. Nothing to restore."
    warn "If your desktop changed and there is no backup here, this repo is not what changed it."
    exit 1
  fi
  [[ -d "$BACKUP" ]] || { warn "Not a directory: $BACKUP"; exit 1; }

  [[ $DRY == 1 ]] && say "DRY RUN — no changes will be made"
  say "Restoring from ${BACKUP/#$HOME/\~}"

  for item in "${HOME_ITEMS[@]}";       do restore_item "$FILES/home"        "$HOME"              "$item"; done
  for item in "${CONFIG_ITEMS[@]}";     do restore_item "$FILES/config"      "$HOME/.config"      "$item"; done
  for item in "${LOCALSHARE_ITEMS[@]}"; do restore_item "$FILES/local-share" "$HOME/.local/share" "$item"; done
  for item in "${ICONS_ITEMS[@]}";      do restore_item "$FILES/icons"       "$HOME/.icons"       "$item"; done
  for item in "${BIN_ITEMS[@]}";        do restore_item "$FILES/bin"         "$HOME/bin"          "$item"; done
  if [[ -d "$FILES/pictures" ]]; then
    for item in "${PICTURES_ITEMS[@]}"; do restore_item "$FILES/pictures" "$HOME" "$item"; done
  fi

  say "$restored put back, $removed removed, $untouched already as they were."
  if [[ $DRY == 0 ]]; then
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$HOME/.local/share/icons" >/dev/null 2>&1 || true
    command -v fc-cache >/dev/null && fc-cache -f >/dev/null 2>&1 || true
    say "Log out and back in to pick up your own bar, keybindings and theme again."
  fi
}
main "$@"
