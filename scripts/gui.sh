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
TITLE="Desktop Manager"

# ---- locate the original (full-res) preview image ---------------------------
preview_source() {
  local c
  for c in "$REPO/preview.png" "$REPO/preview.jpg" "$REPO/files/preview.png"; do
    [[ -f "$c" ]] && { echo "$c"; return 0; }
  done
}

# ---- render a scaled preview at a given size --------------------------------
# Resizes the whole desktop screenshot to fit (keeps full aspect — nothing is
# cropped, so the entire desktop is visible, just smaller).
# _render_preview <geometry> <outfile>; echoes outfile, or the source on failure.
_render_preview() {
  local geom="$1" out="$2" src; src="$(preview_source)"
  [[ -z "$src" ]] && return 0
  local mg
  if   command -v magick  >/dev/null 2>&1; then mg=magick
  elif command -v convert >/dev/null 2>&1; then mg=convert
  else echo "$src"; return 0; fi
  if [[ ! -f "$out" || "$src" -nt "$out" ]]; then
    "$mg" "$src" -resize "$geom" "$out" 2>/dev/null || { echo "$src"; return 0; }
  fi
  echo "$out"
}

# small thumbnail for the card (fits within this box, keeps aspect)
prepare_preview()       { _render_preview '360x240>'  "$REPO/.preview-thumb.png"; }
# larger image for the click-to-enlarge popup
prepare_preview_large() { _render_preview '1600x1000>' "$REPO/.preview-large.png"; }

# ---- pick a dialog tool -----------------------------------------------------
# Prefer the GTK app (grid of desktop cards). Fall back to yad, then kdialog/zenity.
has_gtk() { python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" >/dev/null 2>&1; }
if   command -v python3 >/dev/null 2>&1 && has_gtk; then DLG=gtk
elif command -v yad     >/dev/null 2>&1; then DLG=yad
elif command -v kdialog >/dev/null 2>&1; then DLG=kdialog
elif command -v zenity  >/dev/null 2>&1; then DLG=zenity
else echo "Need python-gobject, yad, kdialog or zenity for the GUI." >&2; exit 1; fi

# Set by the chooser below.
#   MODE   = "stages" (run install.sh stages) or "profile" (run a profile script)
#   STAGES = space-separated stage list (MODE=stages)
#   CMD    = absolute path of an apply/revert script (MODE=profile)
#   DRY    = "--dry-run" or ""
MODE="stages"; STAGES=""; CMD=""; DRY=""

choose_gtk() {
  local img full out; img="$(prepare_preview)"; full="$(prepare_preview_large)"
  local -a a=(python3 "$SCRIPT_DIR/gui_gtk.py")
  [[ -n "$img" ]]  && a+=(--image "$img")
  [[ -n "$full" ]] && a+=(--image-full "$full")
  out="$("${a[@]}")" || return 1     # cancel/close -> non-zero
  MODE="$(sed -n 1p <<<"$out")"      # "stages" | "profile"
  local payload; payload="$(sed -n 2p <<<"$out")"
  DRY="$(sed -n 3p <<<"$out")"
  if [[ $MODE == profile ]]; then CMD="$payload"; [[ -n $CMD ]]
  else STAGES="$payload"; [[ -n $STAGES ]]; fi
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
if [[ $MODE == profile ]]; then
  # apply/revert a themed look; dry-run just prints what would run
  if [[ -n $DRY ]]; then
    inner+=" echo '[dry] would run: bash $(printf '%q' "$CMD")';"
  else
    inner+=" echo '==== running: $CMD ===='; bash $(printf '%q' "$CMD") || rc=1;"
  fi
else
  for s in $STAGES; do
    inner+=" echo; echo '==== stage: $s ${DRY} ===='; bash ./install.sh $s $DRY || rc=1;"
  done
fi
inner+=" echo; if [ \$rc -eq 0 ]; then echo '[OK] Finished.'; else echo '[!!] Errors reported - scroll up.'; fi;"
inner+=" read -rp 'Press Enter to close this window... ' _"

run_in_terminal "$inner"
