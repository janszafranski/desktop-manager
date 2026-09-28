#!/usr/bin/env bash
# install.sh — omarchy-launcher: an Omarchy-style categorised app launcher for
# Hyprland (Quickshell). Deploys the launcher QML + wrapper + categories config,
# starts the warm daemon, and binds Super+Space (moving Caelestia's own launcher
# to Super+Shift+Space so nothing is lost). Idempotent; run as your normal user.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

command -v qs >/dev/null 2>&1 || warn "Quickshell (qs) not found — install 'quickshell'."

log "Deploying the omarchy-launcher"
install -Dm755 "$SELF/omarchy-launcher"  "$HOME/.local/bin/omarchy-launcher"
install -Dm644 "$SELF/shell.qml"         "$HOME/.config/quickshell/omarchy-launcher/shell.qml"
# Never clobber an existing (user-edited) categories file; only seed it if absent.
if [[ ! -f "$HOME/.config/omarchy-launcher/categories.json" ]]; then
  install -Dm644 "$SELF/categories.json" "$HOME/.config/omarchy-launcher/categories.json"
  log "Seeded categories.json"
else
  warn "Kept your existing ~/.config/omarchy-launcher/categories.json"
fi

LUA="$HOME/.config/hypr/hyprland.lua"
MARK_A="-- >>> omarchy-launcher (desktop-manager) >>>"
MARK_B="-- <<< omarchy-launcher (desktop-manager) <<<"
if [[ -f "$LUA" ]] && grep -q "hl\." "$LUA" && ! grep -qF "$MARK_A" "$LUA"; then
  log "Adding Super+Space binding + login autostart (Caelestia launcher -> Super+Shift+Space)"
  cat >> "$LUA" <<EOF

$MARK_A
hl.exec_cmd("$HOME/.local/bin/omarchy-launcher daemon")
hl.bind(mod .. " + Space",        hl.dsp.exec_cmd("$HOME/.local/bin/omarchy-launcher"), { description = "App launcher (categories)" })
hl.bind(mod .. " + SHIFT + Space", hl.dsp.exec_cmd("caelestia shell drawers toggle launcher"), { description = "App launcher (Caelestia)" })
$MARK_B
EOF
  command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
else
  grep -qF "$MARK_A" "$LUA" 2>/dev/null && warn "hyprland.lua already has the binding block — left as-is."
fi

# Warm the daemon now so the first Super+Space is instant.
command -v qs >/dev/null 2>&1 && "$HOME/.local/bin/omarchy-launcher" daemon >/dev/null 2>&1 &
log "Done. Press Super+Space to open. Edit categories: omarchy-launcher edit"
