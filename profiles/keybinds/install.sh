#!/usr/bin/env bash
# install.sh — on-screen "Keyboard shortcuts" cheat-sheet. Installs the right
# version for your desktop: on Hyprland the Quickshell widget (Super+/); on KDE
# the KDE-shortcuts variant (Quickshell + a yad fallback, launched from the menu
# or a Custom Shortcut). Run as your normal user.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

detect_de() {
  local d="${XDG_CURRENT_DESKTOP:-}:${DESKTOP_SESSION:-}"
  if [[ "$d" == *[Hh]yprland* ]] || pgrep -x Hyprland >/dev/null 2>&1; then echo hyprland
  elif [[ "$d" == *KDE* || "$d" == *plasma* ]] || [[ -n "${KDE_FULL_SESSION:-}" ]] \
       || pgrep -x plasmashell >/dev/null 2>&1; then echo kde
  else echo other; fi
}

command -v qs >/dev/null 2>&1 || warn "Quickshell (qs) not found — install 'quickshell'."
DE="$(detect_de)"; log "Desktop environment: $DE"

if [[ "$DE" == hyprland ]]; then
  log "Deploying the Hyprland keybinds widget"
  install -Dm644 "$SELF/shell.qml" "$HOME/.config/quickshell/keybinds/shell.qml"
  install -Dm755 "$SELF/keybinds.sh" "$HOME/.config/hypr/scripts/keybinds.sh"
  install -Dm755 "$SELF/keybinds-toggle.sh" "$HOME/.config/hypr/scripts/keybinds-toggle.sh"
  LUA="$HOME/.config/hypr/hyprland.lua"
  MARK_A="-- >>> keybinds-widget (desktop-manager) >>>"
  MARK_B="-- <<< keybinds-widget (desktop-manager) <<<"
  if [[ -f "$LUA" ]] && grep -q "hl\." "$LUA" && ! grep -qF "$MARK_A" "$LUA"; then
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
  command -v qs >/dev/null 2>&1 && setsid -f qs -c keybinds >/dev/null 2>&1 || true
  log "Done. Press Super+/ to toggle the cheat-sheet."
else
  # KDE / other: deploy the KDE-shortcuts variant + menu launchers
  log "Deploying the KDE keybinds variant"
  install -Dm644 "$SELF/kde/shell.qml" "$HOME/.config/quickshell/kde-keybinds/shell.qml"
  for s in list-shortcuts.sh keybinds-yad.sh; do
    [[ -f "$SELF/kde/$s" ]] && install -Dm755 "$SELF/kde/$s" "$HOME/.config/quickshell/kde-keybinds/$s"
  done
  APPS="$HOME/.local/share/applications"
  for d in kde-keybinds-toggle.desktop kde-keybinds-yad.desktop; do
    [[ -f "$SELF/kde/$d" ]] && install -Dm644 "$SELF/kde/$d" "$APPS/$d"
  done
  command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
  command -v yad >/dev/null 2>&1 || warn "For the fallback list, install 'yad'."
  warn "Launch it from your app menu (\"Keybinds\"), or bind a Custom Shortcut in"
  warn "  System Settings → Shortcuts to:  qs -c kde-keybinds ipc call cheatsheet toggle"
  log "Done."
fi
