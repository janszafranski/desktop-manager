#!/usr/bin/env bash
# Hyprland keybind widget — a simple window that just lists your keybindings.
# Auto-generated from `hyprctl binds`, so it always matches the running config
# (no manual upkeep). Global shortcuts (caelestia:*) show their descriptions
# from `hyprctl globalshortcuts`.
#
# Usage:
#   keybinds.sh            show the widget (yad window)
#   keybinds.sh --fuzzel   show as a searchable fuzzel list instead
#   keybinds.sh --print    dump plain text to stdout
set -uo pipefail

render() {   # emits one "<combo>\t<action>" line per bind
    # Map: global-shortcut name -> description ("caelestia:dashboard" -> "Toggle dashboard")
    declare -A DESC
    while IFS= read -r line; do
        [[ $line == *" -> "* ]] || continue
        DESC["${line%% -> *}"]="${line#* -> }"
    done < <(hyprctl globalshortcuts 2>/dev/null)

    hyprctl binds -j 2>/dev/null \
        | jq -r '.[] | [(.modmask|tostring), .key, .dispatcher, .arg, .description] | @tsv' \
        | while IFS=$'\t' read -r modmask key dispatcher arg desc; do
            combo=""
            (( modmask & 64 )) && combo+="Super+"
            (( modmask & 8  )) && combo+="Alt+"
            (( modmask & 4  )) && combo+="Ctrl+"
            (( modmask & 1  )) && combo+="Shift+"
            combo+="$key"

            case "$dispatcher" in
                exec)   action="$arg" ;;
                global) action="${DESC[$arg]:-$arg}" ;;
                "")     action="(none)" ;;
                *lua*)  action="" ;;   # opaque lua dispatcher; rely on description
                *)      action="$dispatcher${arg:+ $arg}" ;;
            esac
            [ -n "$desc" ] && action="$desc"
            [ -n "$action" ] || continue   # skip binds we can't label
            printf '%s\t%s\n' "$combo" "$action"
        done \
        | awk '!seen[$0]++' \
        | sort -f -t $'\t' -k1,1
}

case "${1:-}" in
    --print)
        render | column -t -s $'\t'
        ;;
    --fuzzel)
        render | awk -F'\t' '{printf "%-26s  %s\n", $1, $2}' \
            | fuzzel --dmenu --prompt "keybinds  " --font "monospace:size=11" \
                     --width 64 --lines 25 >/dev/null 2>&1 || true
        ;;
    *)
        # yad: one field per line feeds the two-column list widget
        render | tr '\t' '\n' \
            | yad --list --title="Keybindings" \
                  --text="Hyprland / Caelestia keybindings" \
                  --column="Key" --column="Action" \
                  --width=560 --height=680 --center \
                  --button="Close:0" --borders=8 >/dev/null 2>&1 || true
        ;;
esac
