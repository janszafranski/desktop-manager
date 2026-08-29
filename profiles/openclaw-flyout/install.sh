#!/usr/bin/env bash
# install.sh — install the OpenClaw AI flyout: a pinnable Quickshell side panel
# (qs -c openclaw-sidebar, Super+O) that chats with your OpenClaw agent via a
# local OpenAI-compatible bridge (127.0.0.1:8787). Run as your normal user.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

# --- prerequisites (warn, don't fail) ----------------------------------------
command -v node    >/dev/null 2>&1 || warn "Node.js not found — needed for the bridge (install 'nodejs')."
command -v qs      >/dev/null 2>&1 || warn "Quickshell (qs) not found — needed for the panel (install 'quickshell')."
command -v openclaw >/dev/null 2>&1 || warn "The 'openclaw' CLI is not on PATH — the flyout needs OpenClaw installed to answer."

# --- deploy ------------------------------------------------------------------
log "Deploying bridge, panel and helper scripts"
install -Dm755 "$SELF/openclaw-ai-bridge.js" "$HOME/.local/bin/openclaw-ai-bridge.js"
for f in openclaw-cli-chat.sh openclaw-dashboard.sh; do
  [[ -f "$SELF/$f" ]] && install -Dm755 "$SELF/$f" "$HOME/.local/bin/$f"
done
mkdir -p "$HOME/.config/quickshell/openclaw-sidebar"
cp -r "$SELF/openclaw-sidebar/." "$HOME/.config/quickshell/openclaw-sidebar/"

# --- bridge service ----------------------------------------------------------
log "Installing + enabling the bridge service"
install -Dm644 "$SELF/openclaw-ai-bridge.service" "$HOME/.config/systemd/user/openclaw-ai-bridge.service"
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload || true
  systemctl --user enable --now openclaw-ai-bridge.service 2>/dev/null \
    || warn "Could not enable the bridge service (no user systemd session?). Start it later with: systemctl --user enable --now openclaw-ai-bridge"
fi

# --- Hyprland integration ----------------------------------------------------
LUA="$HOME/.config/hypr/hyprland.lua"
MARK_A="-- >>> openclaw-flyout (desktop-manager) >>>"
MARK_B="-- <<< openclaw-flyout (desktop-manager) <<<"
if [[ -f "$LUA" ]] && grep -q "hl\." "$LUA"; then
  if grep -qF "$MARK_A" "$LUA"; then
    log "Hyprland rules already present — skipping"
  else
    log "Adding Super+O toggle, autostart and blur rule"
    cat >> "$LUA" <<EOF

$MARK_A
hl.exec_cmd("qs -c openclaw-sidebar")
hl.bind(mod .. " + O", hl.dsp.exec_cmd("qs -c openclaw-sidebar ipc call sidebar toggle"), { description = "OpenClaw flyout" })
hl.layer_rule({ name = "openclaw-flyout-noblur", match = { namespace = "openclaw-sidebar" }, blur = false })
$MARK_B
EOF
    command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
  fi
else
  warn "No Hyprland-Lua config found. Add manually:"
  warn '  exec-once = qs -c openclaw-sidebar'
  warn '  bind = SUPER, O, exec, qs -c openclaw-sidebar ipc call sidebar toggle'
fi

command -v qs >/dev/null 2>&1 && { log "Launching the panel"; setsid -f qs -c openclaw-sidebar >/dev/null 2>&1 || true; }
cat <<'DONE'

OpenClaw flyout installed.
  • Toggle: Super+O   • Bridge: 127.0.0.1:8787 (systemd --user service)
  • It answers via your OpenClaw agent — make sure OpenClaw is installed and running.
DONE
