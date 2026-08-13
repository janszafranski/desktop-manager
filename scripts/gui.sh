#!/usr/bin/env bash
# gui.sh — graphical front-end for install.sh.
# Lets you pick which stages to run, then executes them in a terminal window
# so sudo prompts and live output work. Uses kdialog (KDE) or zenity.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL="$SCRIPT_DIR/install.sh"
TITLE="system-replica"

# ---- pick a dialog tool -----------------------------------------------------
if   command -v kdialog >/dev/null 2>&1; then DLG=kdialog
elif command -v zenity  >/dev/null 2>&1; then DLG=zenity
else
  echo "Need kdialog or zenity installed for the GUI." >&2
  exit 1
fi

err() {
  if [[ $DLG == kdialog ]]; then kdialog --title "$TITLE" --error "$1"
  else zenity --error --title "$TITLE" --text "$1"; fi
}

# ---- choose stages ----------------------------------------------------------
# Returns selected stage keywords in $STAGES (space-separated, order fixed).
choose_stages() {
  local sel
  if [[ $DLG == kdialog ]]; then
    sel=$(kdialog --title "$TITLE" \
      --checklist "Select what to install / deploy:" \
      packages "Install packages (pacman + AUR, needs sudo)" off \
      files    "Deploy config files & themes"                 on  \
      services "Enable systemd --user services"               off) || return 1
    # kdialog returns quoted, space-separated tags: "files" "services"
    sel=${sel//\"/}
  else
    sel=$(zenity --list --checklist --title "$TITLE" \
      --text "Select what to install / deploy:" \
      --column "" --column "Stage" --column "Description" \
      FALSE packages "Install packages (pacman + AUR, needs sudo)" \
      TRUE  files    "Deploy config files & themes" \
      FALSE services "Enable systemd --user services") || return 1
    sel=${sel//|/ }
  fi
  # normalise to canonical order
  STAGES=""
  for s in packages files services; do
    [[ " $sel " == *" $s "* ]] && STAGES+="$s "
  done
  STAGES=${STAGES% }
  [[ -n $STAGES ]]
}

# ---- dry-run? ---------------------------------------------------------------
ask_dryrun() {
  if [[ $DLG == kdialog ]]; then
    kdialog --title "$TITLE" --yesno \
      "Dry run?\n\nYes = preview only (no changes)\nNo  = actually apply changes" \
      && echo "--dry-run"
  else
    zenity --question --title "$TITLE" \
      --text "Dry run? (Yes = preview only, No = actually apply)" \
      && echo "--dry-run"
  fi
  return 0
}

# ---- find a terminal to run in ----------------------------------------------
run_in_terminal() {
  local inner="$1" term
  for term in konsole alacritty kitty gnome-terminal xterm x-terminal-emulator; do
    if command -v "$term" >/dev/null 2>&1; then
      case "$term" in
        gnome-terminal) "$term" -- bash -c "$inner" ;;
        *)              "$term" -e bash -c "$inner" ;;
      esac
      return 0
    fi
  done
  # no terminal found: run inline
  bash -c "$inner"
}

# ---- main -------------------------------------------------------------------
STAGES=""
choose_stages || { echo "Cancelled / nothing selected."; exit 0; }
DRY=$(ask_dryrun)

# build the command that runs each selected stage, then waits for the user
inner="cd $(printf '%q' "$SCRIPT_DIR"); rc=0;"
for s in $STAGES; do
  inner+=" echo; echo '==== stage: $s ${DRY} ===='; bash ./install.sh $s $DRY || rc=1;"
done
inner+=" echo; if [ \$rc -eq 0 ]; then echo '[OK] All selected stages finished.'; else echo '[!!] Some stages reported errors - scroll up.'; fi;"
inner+=" read -rp 'Press Enter to close this window… ' _"

run_in_terminal "$inner"
