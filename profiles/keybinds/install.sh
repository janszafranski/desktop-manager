#!/usr/bin/env bash
# install.sh — install the on-screen "Keyboard shortcuts" cheat-sheet: a
# Quickshell widget (qs -c keybinds) opened by Super+/ (or the hot corner).
# Run as your normal user.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

command -v qs >/dev/null 2>&1 || warn "Quickshell (qs) not found — install 'quickshell' for this to run."

log "Deploying keybinds widget + scripts"
install -Dm644 "$SELF/shell.qml" "$HOME/.config/quickshell/keybinds/shell.qml"
install -Dm755 "$SELF/keybinds.sh" "$HOME/.config/hypr/scripts/keybinds.sh"
install -Dm755 "$SELF/keybinds-toggle.sh" "$HOME/.config/hypr/scripts/keybinds-toggle.sh"

LUA="$HOME/.config/hypr/hyprland.lua"
MARK_A="-- >>> keybinds-widget (desktop-manager) >>>"
MARK_B="-- <<< keybinds-widget (desktop-manager) <<<"
if [[ -f "$LUA" ]] && grep -q "hl\." "$LUA"; then
  if grep -qF "$MARK_A" "$LUA"; then
    log "Hyprland rules already present — skipping"
  else
    log "Adding Super+/ binding and autostart"
    cat >> "$LUA" <<EOF

$MARK_A
hl.exec_cmd("qs -c keybinds")
hl.bind(mod .. " + slash", hl.dsp.exec_cmd("~/.config/hypr/scripts/keybinds-toggle.sh"), { description = "Keybindings (widget)" })
hl.bind(mod .. " + SHIFT + slash", hl.dsp.exec_cmd("~/.config/hypr/scripts/keybinds.sh"), { description = "Keybindings (fallback list)" })
$MARK_B
EOF
    command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
  fi
else
  warn "No Hyprland-Lua config found. Add manually:"
  warn '  exec-once = qs -c keybinds'
  warn '  bind = SUPER, slash, exec, ~/.config/hypr/scripts/keybinds-toggle.sh'
fi

command -v qs >/dev/null 2>&1 && { log "Starting the widget"; setsid -f qs -c keybinds >/dev/null 2>&1 || true; }
log "Done. Press Super+/ to toggle the shortcuts cheat-sheet."
