#!/usr/bin/env bash
# uninstall.sh — remove Shakefree Mouse (files + Hyprland integration). Keeps your
# ~/.config/tremor-filter tuning unless you delete it yourself. Run as your user.
set -euo pipefail
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && { echo "Run as your normal user, not root." >&2; exit 1; }

BIN="$HOME/.local/bin"; APPS="$HOME/.local/share/applications"

# stop a running daemon + tray
if [[ -f "$HOME/.config/tremor-filter/pid" ]]; then
  kill "$(cat "$HOME/.config/tremor-filter/pid")" 2>/dev/null || true
fi
for pid in $(pgrep -f 'python3 .*tremor-tray.py' 2>/dev/null); do
  grep -q python3 "/proc/$pid/cmdline" 2>/dev/null && kill "$pid" 2>/dev/null || true
done

log "Removing files"
rm -f "$BIN/tremor-filter.py" "$BIN/tremor-gui.py" "$BIN/tremor-tray.py" \
      "$BIN/steady-autostart.py" "$BIN/steady-toggle.sh"
rm -f "$APPS/steady-mouse.desktop"
rm -rf "$HOME/.local/share/steady-mouse"
rm -f "$HOME/.config/autostart/steady-mouse.desktop" \
      "$HOME/.config/autostart/steady-mouse-daemon.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

# strip the guarded block from the Hyprland-Lua config
LUA="$HOME/.config/hypr/hyprland.lua"
if [[ -f "$LUA" ]] && grep -qF "steady-mouse (desktop-manager)" "$LUA"; then
  log "Removing Hyprland integration"
  sed -i '/-- >>> steady-mouse (desktop-manager) >>>/,/-- <<< steady-mouse (desktop-manager) <<</d' "$LUA"
  command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
fi

log "Done. (Your tuning in ~/.config/tremor-filter was kept — delete it manually if you want.)"
