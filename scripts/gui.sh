#!/usr/bin/env bash
# gui.sh — graphical front-end for install.sh.
# Lets you pick which stages to run, then executes them in a terminal window
# so sudo prompts and live output work.
#
# Preferred tool is `yad` (shows a desktop preview image + checkboxes in one
# window). Falls back to kdialog (KDE) or zenity if yad is not installed.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
INSTALL="$SCRIPT_DIR/install.sh"
TITLE="System Replica"

# ---- locate a display-ready preview image -----------------------------------
# Returns (echoes) a path to a scaled preview, or nothing if none available.
prepare_preview() {
  local src="" thumb="$REPO/.preview-thumb.png"
  for c in "$REPO/preview.png" "$REPO/preview.jpg" "$REPO/files/preview.png"; do
    [[ -f "$c" ]] && { src="$c"; break; }
  done
  [[ -z "$src" ]] && return 0
  # scale down large screenshots so the dialog stays a sane size
  if command -v magick >/dev/null 2>&1;  then MG=(magick "$src");   MGT=magick
  elif command -v convert >/dev/null 2>&1; then MG=(convert "$src"); MGT=convert
  else echo "$src"; return 0; fi
  if [[ ! -f "$thumb" || "$src" -nt "$thumb" ]]; then
    # center-crop to a 16:9 "normal monitor" shape, then scale down
    "${MG[@]}" -gravity center -crop 16:9 +repage -resize '360x203>' "$thumb" \
      2>/dev/null || { echo "$src"; return 0; }
  fi
  echo "$thumb"
}

# ---- pick a dialog tool -----------------------------------------------------
# Prefer the GTK app (grid of desktop cards). Fall back to yad, then kdialog/zenity.
has_gtk() { python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" >/dev/null 2>&1; }
if   command -v python3 >/dev/null 2>&1 && has_gtk; then DLG=gtk
elif command -v yad     >/dev/null 2>&1; then DLG=yad
elif command -v kdialog >/dev/null 2>&1; then DLG=kdialog
elif command -v zenity  >/dev/null 2>&1; then DLG=zenity
else echo "Need python-gobject, yad, kdialog or zenity for the GUI." >&2; exit 1; fi

# STAGES (space-separated canonical order) and DRY ("--dry-run" or "") are set
# by the chooser below.
STAGES=""; DRY=""

choose_gtk() {
  local img out; img="$(prepare_preview)"
  local -a a=(python3 "$SCRIPT_DIR/gui_gtk.py")
  [[ -n "$img" ]] && a+=(--image "$img")
  out="$("${a[@]}")" || return 1     # cancel/close -> non-zero
  STAGES="$(sed -n 1p <<<"$out")"
  DRY="$(sed -n 2p <<<"$out")"
  [[ -n $STAGES ]]
}

choose_yad() {
  local img out; img="$(prepare_preview)"
  local -a args=(--title="$TITLE" --form --width=420
                 --text="<b>Select what to install / deploy</b>"
                 --button=gtk-cancel:1 --button=gtk-ok:0)
  [[ -n "$img" ]] && args+=(--image="$img")
  args+=(--field="Install packages (pacman + AUR, needs sudo):CHK" FALSE
         --field="Deploy config files & themes:CHK" TRUE
         --field="Enable systemd --user services:CHK" FALSE
         --field="Dry run (preview only, no changes):CHK" FALSE)
  out="$(yad "${args[@]}")" || return 1     # cancel/close -> non-zero
  IFS='|' read -r p f s d _ <<<"$out"
  [[ ${p^^} == TRUE ]] && STAGES+="packages "
  [[ ${f^^} == TRUE ]] && STAGES+="files "
  [[ ${s^^} == TRUE ]] && STAGES+="services "
  STAGES=${STAGES% }
  [[ ${d^^} == TRUE ]] && DRY="--dry-run"
  [[ -n $STAGES ]]
}

choose_kdialog_zenity() {
  local sel
  if [[ $DLG == kdialog ]]; then
    sel=$(kdialog --title "$TITLE" \
      --checklist "Select what to install / deploy:" \
      packages "Install packages (pacman + AUR, needs sudo)" off \
      files    "Deploy config files & themes"                 on  \
      services "Enable systemd --user services"               off) || return 1
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
  for s in packages files services; do
    [[ " $sel " == *" $s "* ]] && STAGES+="$s "
  done
  STAGES=${STAGES% }
  [[ -n $STAGES ]] || return 1
  # separate dry-run prompt for these tools
  if [[ $DLG == kdialog ]]; then
    kdialog --title "$TITLE" --yesno "Dry run? (Yes = preview only, No = apply)" && DRY="--dry-run"
  else
    zenity --question --title "$TITLE" --text "Dry run? (Yes = preview only, No = apply)" && DRY="--dry-run"
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
  bash -c "$inner"
}

# ---- main -------------------------------------------------------------------
case $DLG in
  gtk) choose_gtk           || { echo "Cancelled / nothing selected."; exit 0; } ;;
  yad) choose_yad           || { echo "Cancelled / nothing selected."; exit 0; } ;;
  *)   choose_kdialog_zenity || { echo "Cancelled / nothing selected."; exit 0; } ;;
esac

inner="cd $(printf '%q' "$SCRIPT_DIR"); rc=0;"
for s in $STAGES; do
  inner+=" echo; echo '==== stage: $s ${DRY} ===='; bash ./install.sh $s $DRY || rc=1;"
done
inner+=" echo; if [ \$rc -eq 0 ]; then echo '[OK] All selected stages finished.'; else echo '[!!] Some stages reported errors - scroll up.'; fi;"
inner+=" read -rp 'Press Enter to close this window... ' _"

run_in_terminal "$inner"
