#!/usr/bin/env bash
# install.sh — add an "illogical-impulse" (end-4 dots) Hyprland + Quickshell
# session next to your existing desktop, selectable at the SDDM login screen.
#
# KEY IDEA: end-4's shell is ALSO a Quickshell rice, so it would collide with
# Caelestia (which owns ~/.config/hypr and ~/.config/quickshell). To keep BOTH,
# this installs end-4 into an ISOLATED config tree at ~/.config-ii via
# XDG_CONFIG_HOME, and gives it its own login session that points there. Your
# default ~/.config (Caelestia / KDE) is never touched.
#
# Non-destructive: ADDS packages, ~/.config-ii, a wrapper, and a session entry.
# Run as your normal user (NOT root); it prompts for sudo when needed.
set -euo pipefail

log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root (uses sudo when needed)."

II_CONFIG="$HOME/.config-ii"          # isolated XDG_CONFIG_HOME for end-4
REPO_DIR="$HOME/src/dots-hyprland"    # where end-4's source is cloned
WRAPPER="$HOME/.local/bin/start-hypr-ii"
SESSION="/usr/share/wayland-sessions/hyprland-ii.desktop"

# --- 0. prerequisites --------------------------------------------------------
AUR=""
command -v yay  >/dev/null 2>&1 && AUR=yay
[[ -z $AUR ]] && command -v paru >/dev/null 2>&1 && AUR=paru
[[ -z $AUR ]] && die "Need an AUR helper (yay or paru)."
command -v git >/dev/null 2>&1 || die "git is required."
log "AUR helper: $AUR"

# --- 1. CachyOS audio fix (do this BEFORE end-4's installer) ------------------
# end-4's bundled 'illogical-impulse-audio' meta-package pulls STOCK pipewire,
# which DOWNGRADES CachyOS's own pipewire rebuild (…-1.1) and breaks packages
# pinned to it (gst-plugin-pipewire, pipewire-alsa). The pipewire stack is
# already present on CachyOS; only these three tools are actually missing.
# Install them natively first, then tell end-4's installer to IGNORE ('i') the
# audio step when it errors — the real deps are already satisfied.
if grep -qiE '^ID=cachyos' /etc/os-release 2>/dev/null; then
  log "CachyOS detected — pre-installing native audio tools (avoids pipewire downgrade)…"
  sudo pacman -S --needed --noconfirm cava pavucontrol-qt playerctl || \
    warn "Could not pre-install audio tools; if end-4's audio step fails, press 'i' to ignore."
fi

# --- 1b. Material Symbols font conflict (Caelestia coexistence) ---------------
# Caelestia installs the STABLE 'ttf-material-symbols-variable'; end-4 wants the
# '-git' variant. They conflict (same files), but the -git pkg Provides the
# stable name, so caelestia-shell's dependency stays satisfied after the swap.
# Do the replace up front so end-4's font batch doesn't abort on the conflict.
if pacman -Q ttf-material-symbols-variable >/dev/null 2>&1 && \
   ! pacman -Q ttf-material-symbols-variable-git >/dev/null 2>&1; then
  log "Replacing stable Material Symbols font with the -git variant end-4 needs…"
  "$AUR" -S --noconfirm --ask=4 ttf-material-symbols-variable-git || \
    warn "Font swap failed; when end-4's font step conflicts, remove the stable pkg then press 'r'."
fi

# --- 2. fetch end-4 source ---------------------------------------------------
if [[ -d "$REPO_DIR/.git" ]]; then
  log "Refreshing existing clone at $REPO_DIR…"
  git -C "$REPO_DIR" stash --include-untracked >/dev/null 2>&1 || true
  git -C "$REPO_DIR" pull --ff-only || warn "pull failed; using existing checkout."
else
  log "Cloning end-4/dots-hyprland → $REPO_DIR…"
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone --depth 1 https://github.com/end-4/dots-hyprland "$REPO_DIR"
fi

# --- 3. run end-4's installer into the ISOLATED tree -------------------------
# This is INTERACTIVE by design (prints every command, prompts per step).
#   * On the pipewire/audio step: press 'i' (ignore) — see step 1.
#   * If it offers to set a default session / touch SDDM: DECLINE — we add our
#     own session entry below.
warn "end-4's installer is interactive. Reminders:"
warn "  • ANY step failing with 'installing libpipewire (…-1) breaks dependency'"
warn "    is the CachyOS stock-vs-.1 skew — the real deps are already present."
warn "    Install any genuinely-missing pkgs from that batch in another terminal"
warn "    (WITHOUT libpipewire/pipewire), then press 'i' (ignore). Never let it"
warn "    downgrade pipewire. Seen in: the audio meta AND the qt6 batch."
warn "  • 'set default session?'-> decline (we handle the session)"
log "Launching end-4 setup with XDG_CONFIG_HOME=$II_CONFIG …"
( cd "$REPO_DIR" && XDG_CONFIG_HOME="$II_CONFIG" ./setup install )

# --- 4. isolation wrapper ----------------------------------------------------
log "Installing session wrapper → $WRAPPER"
mkdir -p "$(dirname "$WRAPPER")"
cat > "$WRAPPER" <<EOF
#!/bin/sh
# Launch end-4 (illogical-impulse) with an isolated config tree so it never
# collides with the default (Caelestia / KDE) setup in ~/.config.
export XDG_CONFIG_HOME="$II_CONFIG"
export XDG_CURRENT_DESKTOP="Hyprland"
# end-4 ships a Lua config (hyprland.lua), NOT hyprland.conf — point Hyprland at
# it explicitly, otherwise it boots a default empty config.
exec Hyprland -c "$II_CONFIG/hypr/hyprland.lua"
EOF
chmod +x "$WRAPPER"

# --- 5. login session entry --------------------------------------------------
log "Adding SDDM session entry → $SESSION (sudo)"
tmp="$(mktemp)"
cat > "$tmp" <<EOF
[Desktop Entry]
Name=Hyprland (illogical-impulse)
Comment=end-4 dots, isolated config tree ~/.config-ii
Exec=$WRAPPER
Type=Application
DesktopNames=Hyprland
EOF
sudo install -Dm644 "$tmp" "$SESSION"
rm -f "$tmp"

# --- 6. convenience keybind (SUPER+O launches OpenClaw web UI) ---------------
# end-4 uses a LUA config; binds are hl.bind(...) calls. Its "custom" override
# folder is gated on a HARDCODED ~/.config/hypr path in hyprland.lua, so in this
# relocated ~/.config-ii tree those overrides don't load. Append to the base
# hyprland/keybinds.lua (loaded unconditionally) instead. NOTE: that file is
# end-4-tracked, so re-running the installer may overwrite this bind.
KB="$II_CONFIG/hypr/hyprland/keybinds.lua"
if [[ -f "$KB" ]] && ! grep -q 'OpenClaw web UI' "$KB"; then
  if command -v floorp >/dev/null 2>&1; then
    BROWSER_CMD="floorp --new-window http://127.0.0.1:18789/"
  else
    BROWSER_CMD="xdg-open http://127.0.0.1:18789/"
  fi
  printf '\n-- added by desktop-manager: launch OpenClaw web UI\nhl.bind("SUPER + O", hl.dsp.exec_cmd("%s"), { description = "Launch OpenClaw web UI" })\n' \
    "$BROWSER_CMD" >> "$KB"
  log "Added SUPER+O bind → $KB"
fi

# --- 7. OpenClaw AI flyout bridge -------------------------------------------
# end-4's left-edge AI flyout speaks raw OpenAI/Gemini HTTP; it can't reach the
# OpenClaw agent directly. This bridge exposes a loopback OpenAI-compatible
# endpoint that forwards to `openclaw agent`, so the flyout becomes the actual
# OpenClaw agent (memory + persona), not a raw model. Skipped if openclaw/node
# aren't present.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_SRC="$SCRIPT_DIR/openclaw-ai-bridge.js"
BRIDGE_DST="$HOME/.local/bin/openclaw-ai-bridge.js"
UNIT="$HOME/.config/systemd/user/openclaw-ai-bridge.service"
if command -v openclaw >/dev/null 2>&1 && command -v node >/dev/null 2>&1 && [[ -f "$BRIDGE_SRC" ]]; then
  log "Installing OpenClaw AI flyout bridge…"
  install -Dm755 "$BRIDGE_SRC" "$BRIDGE_DST"

  mkdir -p "$(dirname "$UNIT")"
  cat > "$UNIT" <<EOF
[Unit]
Description=OpenClaw AI bridge (OpenAI-compatible endpoint for end4 AI flyout)
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/node %h/.local/bin/openclaw-ai-bridge.js
Restart=on-failure
RestartSec=3
Environment=OPENCLAW_BRIDGE_PORT=8787

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload 2>/dev/null || true
  systemctl --user enable --now openclaw-ai-bridge.service 2>/dev/null || \
    warn "Could not start the bridge service (no systemd --user session?). It'll start on next login."

  # Register the "OpenClaw (me)" model in end-4's config and make it default.
  # Idempotent: config hot-reloads (watchChanges), so no shell restart needed.
  CFG="$II_CONFIG/illogical-impulse/config.json"
  STATE="$HOME/.local/state/quickshell/states.json"
  if command -v python3 >/dev/null 2>&1 && [[ -f "$CFG" ]]; then
    CFG="$CFG" STATE="$STATE" python3 - <<'PY' || warn "Could not register OpenClaw model; add it via the flyout settings."
import json, os
cfg_path = os.environ["CFG"]
cfg = json.load(open(cfg_path))
models = cfg.setdefault("ai", {}).setdefault("extraModels", [])
models = [m for m in models if m.get("model") != "openclaw"]  # idempotent
models.append({
    "api_format": "openai",
    "description": "The actual OpenClaw agent — memory, persona, workspace — via local bridge (systemd: openclaw-ai-bridge).",
    "endpoint": "http://127.0.0.1:8787/v1/chat/completions",
    "icon": "spark-symbolic",
    "key_id": "openclaw",
    "model": "openclaw",
    "name": "OpenClaw (me)",
    "requires_key": False,
})
cfg["ai"]["extraModels"] = models
json.dump(cfg, open(cfg_path, "w"), indent=2)

state_path = os.environ["STATE"]
try:
    st = json.load(open(state_path))
except Exception:
    st = {}
st.setdefault("ai", {})["model"] = "openclaw"
os.makedirs(os.path.dirname(state_path), exist_ok=True)
json.dump(st, open(state_path, "w"), indent=2)
print("registered OpenClaw model + set as default")
PY
    log "OpenClaw flyout ready — select 'OpenClaw (me)' in the flyout (CTRL+SUPER+R to reload)."
  fi
  warn "Bridge is loopback-only (127.0.0.1:8787). Anything local that can POST to it can trigger agent turns."
else
  warn "openclaw or node not found — skipping AI flyout bridge."
fi

log "Done. Log out and pick 'Hyprland (illogical-impulse)' at the login screen."
log "Your default session (Caelestia / KDE) is unchanged."
