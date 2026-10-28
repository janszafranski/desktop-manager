#!/usr/bin/env bash
# Round-trip test for scripts/restore-backup.sh.
#
# Builds a throwaway $HOME that looks like a stock Omarchy box, runs the real
# `install.sh files` over it, then the real `restore-backup.sh`, and asserts the
# home is byte-for-byte what it was before. Touches nothing outside its own
# temp directory and needs no compositor, so it is safe to run on a live
# desktop.
#
#   ./scripts/tests/restore-backup-test.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$(dirname "$SCRIPT_DIR")")"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/restore-backup-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
ok()   { pass=$((pass+1)); printf '  \033[32mok\033[0m   %s\n' "$1"; }
no()   { fail=$((fail+1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
check() { if [[ "$2" == "$3" ]]; then ok "$1"; else no "$1 (got '$3', want '$2')"; fi; }
exists()    { if [[ -e "$2" ]]; then ok "$1"; else no "$1 — missing $2"; fi; }
notexists() { if [[ ! -e "$2" ]]; then ok "$1"; else no "$1 — still there: $2"; fi; }

export HOME="$TMP/home"
export XDG_CACHE_HOME="$TMP/cache"
export XDG_DATA_HOME="$HOME/.local/share"
mkdir -p "$HOME/.config"/{hypr/scripts,autostart,fish,waybar,micro}

# --- a stock-ish Omarchy home ------------------------------------------------
printf 'MIYA OMARCHY hyprland.lua\nexec-once = waybar\n' > "$HOME/.config/hypr/hyprland.lua"
printf 'miya waybar helper\n'          > "$HOME/.config/hypr/scripts/keybinds.sh"
printf 'miya autostart marker\n'       > "$HOME/.config/autostart/miya.desktop"
printf 'set -g fish_greeting "miya"\n' > "$HOME/.config/fish/config.fish"
printf '{"layer":"top"}\n'             > "$HOME/.config/waybar/config.jsonc"
# Her own file inside a directory the deploy also writes into.
printf 'miya micro colours\n'          > "$HOME/.config/micro/mysettings.json"
printf 'export MIYA=1\n'               > "$HOME/.bashrc"

snapshot() { (cd "$HOME" && find . -path ./.cache -prune -o -path './.config-backup-*' -prune -o -print0 | sort -z | xargs -0 -I{} sh -c 'if [ -f "{}" ]; then printf "%s " "{}"; md5sum < "{}"; else printf "%s dir\n" "{}"; fi'); }
before="$(snapshot)"

echo "=== deploy ==="
"$REPO/scripts/install.sh" files >/dev/null 2>&1
exists   "the deploy ran (a backup directory exists)" "$(echo "$HOME"/.config-backup-*)"
if grep -q MIYA "$HOME/.config/hypr/hyprland.lua"; then
  no "the deploy replaced her hyprland.lua"
else
  ok "the deploy replaced her hyprland.lua"
fi
notexists "the deploy took her autostart entry" "$HOME/.config/autostart/miya.desktop"

echo "=== restore ==="
"$REPO/scripts/restore-backup.sh" >/dev/null 2>&1
after="$(snapshot)"

check "her hyprland.lua is back" "MIYA OMARCHY hyprland.lua" "$(head -1 "$HOME/.config/hypr/hyprland.lua")"
check "her hypr script is back"  "miya waybar helper"        "$(cat "$HOME/.config/hypr/scripts/keybinds.sh")"
exists "her autostart entry is back" "$HOME/.config/autostart/miya.desktop"
check "her fish config is back"  'set -g fish_greeting "miya"' "$(cat "$HOME/.config/fish/config.fish")"
check "her .bashrc is back"      "export MIYA=1"               "$(cat "$HOME/.bashrc")"
check "waybar config never touched" '{"layer":"top"}'          "$(cat "$HOME/.config/waybar/config.jsonc")"
check "her file in a shared dir survived" "miya micro colours" "$(cat "$HOME/.config/micro/mysettings.json")"
notexists "kwinrc removed (she had none)"      "$HOME/.config/kwinrc"
notexists "krohnkite removed (she had none)"   "$HOME/.local/share/kwin/scripts/krohnkite"
notexists "empty dir the deploy created is pruned" "$HOME/.config/caelestia"
exists    "a shared dir with her file in it is kept" "$HOME/.config/micro"
exists    "~/.config itself is kept" "$HOME/.config"

if [[ "$before" == "$after" ]]; then
  ok "home is byte-for-byte what it was before the deploy"
else
  no "home differs from before the deploy"
  diff <(printf '%s\n' "$before") <(printf '%s\n' "$after") | head -20
fi

# A second restore must be a no-op on content, not a cascade of deletions.
"$REPO/scripts/restore-backup.sh" >/dev/null 2>&1
if [[ "$(snapshot)" == "$after" ]]; then
  ok "restoring twice changes nothing the second time"
else
  no "a second restore changed the home again"
fi

# With no backup at all the script must refuse rather than delete anything.
export HOME="$TMP/empty-home"; mkdir -p "$HOME/.config/hypr"
printf 'untouched\n' > "$HOME/.config/hypr/hyprland.lua"
"$REPO/scripts/restore-backup.sh" >/dev/null 2>&1
rc=$?
check "exits non-zero when there is no backup" "1" "$rc"
check "and leaves the home alone" "untouched" "$(cat "$HOME/.config/hypr/hyprland.lua")"

printf '\n==== %d passed, %d failed ====\n' "$pass" "$fail"
[[ $fail == 0 ]]
