#!/usr/bin/env bash
# install.sh — install "Steady Mouse", a hand-tremor mouse filter (SteadyMouse-style)
# for Linux / Wayland. Userspace: NO root for normal use (needs the 'input' group).
#
# Deploys the daemon + GTK control panel + app launcher, installs python-evdev,
# and (on a Hyprland-Lua setup) adds a float rule, a Super+Shift+M toggle and
# autostart. Re-runnable / idempotent. Run as your normal user.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root."

BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
CFGDIR="$HOME/.config/tremor-filter"

# --- 1. deploy files ---------------------------------------------------------
log "Deploying app files"
mkdir -p "$BIN" "$APPS" "$CFGDIR"
install -m755 "$SELF/tremor-filter.py" "$SELF/tremor-gui.py" "$SELF/steady-toggle.sh" "$BIN/"
install -m644 "$SELF/steady-mouse.desktop" "$APPS/steady-mouse.desktop"
# preserve the user's existing tuning if they already have a config
[[ -f "$CFGDIR/config.json" ]] || install -m644 "$SELF/config.json" "$CFGDIR/config.json"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

# --- 2. python-evdev ---------------------------------------------------------
if python3 -c "import evdev" 2>/dev/null; then
  log "python-evdev already present"
else
  log "Installing python-evdev (user site)"
  python3 -m pip install --user --break-system-packages --quiet evdev \
    || warn "Could not pip-install evdev — install 'python-evdev' via your package manager."
fi

# --- 3. permissions note -----------------------------------------------------
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  warn "You are not in the 'input' group — needed for /dev/uinput and /dev/input."
  warn "Run:  sudo usermod -aG input \"$USER\"   then log out and back in."
fi

# --- 4. Hyprland integration (idempotent) ------------------------------------
LUA="$HOME/.config/hypr/hyprland.lua"
MARK_A="-- >>> steady-mouse (desktop-manager) >>>"
MARK_B="-- <<< steady-mouse (desktop-manager) <<<"
if [[ -f "$LUA" ]] && grep -q "hl\." "$LUA"; then
  if grep -qF "$MARK_A" "$LUA"; then
    log "Hyprland (Lua) rules already present — skipping"
  else
    log "Adding Hyprland float rule, Super+Shift+M toggle and autostart"
    cat >> "$LUA" <<EOF

$MARK_A
hl.window_rule({ name = "float-steady-mouse", match = { class = "ai.openclaw.steadymouse" }, float = true })
hl.bind(mod .. " + SHIFT + M", hl.dsp.exec_cmd("~/.local/bin/steady-toggle.sh"), { description = "Toggle steady mouse (tremor filter)" })
hl.exec_cmd("python3 $HOME/.local/bin/tremor-filter.py")  -- autostart (single-instance guarded)
$MARK_B
EOF
    command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
  fi
else
  warn "No Hyprland-Lua config found. To integrate manually add:"
  warn '  exec-once = python3 ~/.local/bin/tremor-filter.py       # autostart'
  warn '  bind = SUPER SHIFT, M, exec, ~/.local/bin/steady-toggle.sh   # toggle'
  warn '  windowrulev2 = float, class:^(ai.openclaw.steadymouse)$'
fi

# --- 5. start it now ---------------------------------------------------------
log "Starting Steady Mouse"
setsid -f python3 "$BIN/tremor-filter.py" >/tmp/tremor-filter.log 2>&1 || true

cat <<'DONE'

Steady Mouse installed.
  • Launch the tuning panel from your app menu ("Steady Mouse"), or run: tremor-gui.py
  • Toggle on/off:  Super+Shift+M
  • Tune:           the panel's sliders (Smoothing / Responsiveness / Click freeze / …)
DONE
