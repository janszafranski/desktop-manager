#!/usr/bin/env bash
# install.sh — Steady Mouse: a SteadyMouse-style hand-tremor filter for Linux.
# The daemon works on ANY desktop (it filters at the evdev/uinput input layer,
# so X11 or Wayland, KDE or Hyprland). Userspace: NO root (needs the 'input'
# group). On Hyprland it also adds a Super+Shift+M toggle + float rule + autostart;
# on KDE/GNOME/other it uses XDG autostart and points you at the keybind setting.
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

BIN="$HOME/.local/bin"; APPS="$HOME/.local/share/applications"; CFGDIR="$HOME/.config/tremor-filter"
SHARE="$HOME/.local/share/steady-mouse"

# --- 1. deploy files (desktop-agnostic) --------------------------------------
log "Deploying app files"
mkdir -p "$BIN" "$APPS" "$CFGDIR" "$SHARE/icons"
install -m755 "$SELF/tremor-filter.py" "$SELF/tremor-gui.py" "$SELF/tremor-tray.py" \
              "$SELF/steady-autostart.py" "$SELF/steady-toggle.sh" "$BIN/"
install -m644 "$SELF/steady-mouse.desktop" "$APPS/steady-mouse.desktop"
install -m644 "$SELF/assets/icons/"steady-mouse-*.svg "$SELF/assets/icons/"steady-mouse-*.png "$SHARE/icons/"
[[ -f "$CFGDIR/config.json" ]] || install -m644 "$SELF/config.json" "$CFGDIR/config.json"
# GUI prefs — both toggles default ON
[[ -f "$CFGDIR/gui.json" ]] || printf '{\n  "autostart": true,\n  "tray": true\n}\n' > "$CFGDIR/gui.json"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true

# --- 2. python-evdev ---------------------------------------------------------
if python3 -c "import evdev" 2>/dev/null; then log "python-evdev already present"
else
  log "Installing python-evdev (user site)"
  python3 -m pip install --user --break-system-packages --quiet evdev \
    || warn "Could not pip-install evdev — install 'python-evdev' via your package manager."
fi

# --- 2b. tray dependency (Ayatana AppIndicator, for the system-tray icon) -----
if python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')" 2>/dev/null; then
  log "Ayatana AppIndicator present (tray icon supported)"
else
  warn "Tray icon needs libayatana-appindicator + its GObject typelib:"
  warn "  Arch:   sudo pacman -S --needed libayatana-appindicator"
  warn "  Debian/Ubuntu: sudo apt install gir1.2-ayatanaappindicator3-0.1"
  warn "  (the app still works without it — just no tray icon)"
fi

# --- 3. permissions ----------------------------------------------------------
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx input; then
  warn "You are not in the 'input' group — needed for /dev/uinput and /dev/input."
  warn "Run:  sudo usermod -aG input \"$USER\"   then log out and back in."
fi

# --- 4. desktop integration --------------------------------------------------
DE="$(detect_de)"; log "Desktop environment: $DE"
if [[ "$DE" == hyprland ]]; then
  LUA="$HOME/.config/hypr/hyprland.lua"
  MARK_A="-- >>> steady-mouse (desktop-manager) >>>"
  MARK_B="-- <<< steady-mouse (desktop-manager) <<<"
  if [[ -f "$LUA" ]] && grep -q "hl\." "$LUA"; then
    if grep -qF "$MARK_A" "$LUA"; then log "Hyprland rules already present — skipping"
    else
      log "Adding Hyprland float rule, Super+Shift+M toggle and autostart"
      cat >> "$LUA" <<EOF

$MARK_A
hl.window_rule({ name = "float-steady-mouse", match = { class = "ai.openclaw.steadymouse" }, float = true })
hl.bind(mod .. " + SHIFT + M", hl.dsp.exec_cmd("~/.local/bin/steady-toggle.sh"), { description = "Toggle steady mouse (tremor filter)" })
hl.exec_cmd("python3 $HOME/.local/bin/steady-autostart.py")  -- autostart daemon + tray per GUI toggles (single-instance guarded)
$MARK_B
EOF
      command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 || true
    fi
  else
    warn "Hyprland detected but no Lua config — add manually:"
    warn '  exec-once = python3 ~/.local/bin/tremor-filter.py'
    warn '  bind = SUPER SHIFT, M, exec, ~/.local/bin/steady-toggle.sh'
  fi
else
  # universal XDG autostart (honoured by KDE, GNOME, most DEs)
  install -Dm644 /dev/stdin "$HOME/.config/autostart/steady-mouse.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Steady Mouse
Exec=python3 $HOME/.local/bin/steady-autostart.py
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
  log "Added XDG autostart (daemon + tray, per GUI toggles)"
  if [[ "$DE" == kde ]]; then
    warn "KDE: to bind the on/off toggle, add a Custom Shortcut in"
    warn "  System Settings → Shortcuts → Add Command:  $HOME/.local/bin/steady-toggle.sh"
  else
    warn "Bind  $HOME/.local/bin/steady-toggle.sh  to a hotkey in your DE for quick on/off."
  fi
fi

# --- 5. start it now ---------------------------------------------------------
log "Starting Steady Mouse (daemon + tray, per GUI toggles)"
setsid -f python3 "$BIN/steady-autostart.py" >/tmp/steady-autostart.log 2>&1 || true

cat <<'DONE'

Steady Mouse installed.
  • Launch the tuning panel from your app menu ("Steady Mouse") or: tremor-gui.py
  • Toggle: Super+Shift+M (Hyprland) or the hotkey you bind (KDE/other)
  • Works on any desktop — the filter runs at the input layer.
DONE
