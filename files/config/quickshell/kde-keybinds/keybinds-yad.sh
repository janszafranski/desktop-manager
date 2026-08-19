#!/usr/bin/env bash
# Plain KDE keybinding list (fallback for the QuickShell widget).
#   keybinds-yad.sh            show the yad window
#   keybinds-yad.sh --fuzzel   searchable fuzzel list
#   keybinds-yad.sh --print    dump plain text to stdout
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
render() { "$DIR/list-shortcuts.sh"; }   # already emits sorted "<combo>\t<action>"

case "${1:-}" in
    --print)
        render | column -t -s "$(printf '\t')"
        ;;
    --fuzzel)
        render | awk -F'\t' '{printf "%-28s  %s\n", $1, $2}' \
            | fuzzel --dmenu --prompt "kde keybinds  " --font "monospace:size=11" \
                     --width 72 --lines 25 >/dev/null 2>&1 || true
        ;;
    *)
        render | tr '\t' '\n' \
            | yad --list --title="KDE Keybindings" \
                  --text="Plasma / KWin keybindings" \
                  --column="Key" --column="Action" \
                  --width=620 --height=720 --center \
                  --button="Close:0" --borders=8 >/dev/null 2>&1 || true
        ;;
esac
