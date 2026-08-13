#!/usr/bin/env bash
# install.sh — add a "Caelestia" session (Hyprland + the Caelestia shell) next
# to your existing KDE Plasma, selectable at the SDDM login screen.
#
# Non-destructive to KDE: it only ADDS packages, a ~/.config/hypr config, and a
# login session entry. Plasma stays your default and fallback.
#
# Run as your normal user (NOT root). It will prompt for your password when it
# needs sudo (package install + the session file).
set -euo pipefail

log()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] && die "Run as your normal user, not root (the script uses sudo when needed)."

# --- 0. prerequisites --------------------------------------------------------
AUR=""
command -v yay  >/dev/null 2>&1 && AUR=yay
[[ -z $AUR ]] && command -v paru >/dev/null 2>&1 && AUR=paru
[[ -z $AUR ]] && die "Need an AUR helper (yay or paru)."
command -v Hyprland >/dev/null 2>&1 || true
log "AUR helper: $AUR"

# --- 1. packages -------------------------------------------------------------
# caelestia-shell pulls its own deps (quickshell-git, caelestia-cli, cava, etc).
# We add Hyprland itself, a terminal, portals and a polkit agent for a usable
# session. Building quickshell-git can take several minutes.
log "Installing Hyprland + Caelestia shell + session essentials (this can take a while)…"
# NOTE: caelestia-shell depends on 'quickshell-git'. Several packages *provide*
# that name — notably 'noctalia-qs', a FORK of Quickshell that Caelestia will
# not run on. Install the genuine upstream 'quickshell-git' EXPLICITLY (and
# first) so the resolver doesn't substitute the fork.
"$AUR" -S --needed --noconfirm --answerclean=All --answerdiff=None \
  aur/quickshell-git \
  hyprland \
  caelestia-shell caelestia-cli \
  alacritty wl-clipboard \
  xdg-desktop-portal-hyprland qt6-wayland polkit-kde-agent \
  || die "Package install failed — fix the error above and re-run."

# --- 2. Hyprland user config (autostarts Caelestia) --------------------------
HYPR="$HOME/.config/hypr"
if [[ -e "$HYPR/hyprland.conf" ]]; then
  bak="$HYPR/hyprland.conf.bak-$(date +%Y%m%d-%H%M%S)"
  cp -a "$HYPR/hyprland.conf" "$bak"; warn "backed up existing config -> $bak"
fi
mkdir -p "$HYPR"

# detect keyboard layout (KDE, else localectl, else us)
KBLAYOUT="$(kreadconfig6 --file kxkbrc --group Layout --key LayoutList 2>/dev/null | cut -d, -f1)"
[[ -z $KBLAYOUT ]] && KBLAYOUT="$(localectl status 2>/dev/null | awk -F: '/X11 Layout/{gsub(/ /,"",$2);print $2}')"
KBLAYOUT="${KBLAYOUT:-us}"

cat > "$HYPR/hyprland.conf" <<CONF
# Minimal Hyprland config that autostarts the Caelestia shell.
# For the full Caelestia keybind/UX set, install the caelestia dotfiles later:
#   https://github.com/caelestia-dots/caelestia

monitor = , preferred, auto, 1

# --- environment ---
env = XCURSOR_SIZE,24
env = QT_QPA_PLATFORM,wayland

# --- autostart ---
exec-once = caelestia shell -d
exec-once = /usr/lib/polkit-kde-authentication-agent-1

# --- input ---
input {
    kb_layout = ${KBLAYOUT}
    follow_mouse = 1
    touchpad { natural_scroll = true }
}

general {
    gaps_in = 5
    gaps_out = 10
    border_size = 2
    layout = dwindle
}
decoration { rounding = 10 }

\$mod = SUPER
# --- keybinds (minimal but usable) ---
bind = \$mod, Return, exec, alacritty
bind = \$mod, Q, killactive,
bind = \$mod, E, exec, dolphin
# NOTE: the Caelestia shell registers its OWN global shortcuts (launcher,
# dashboard, etc.) once running, so we don't bind a launcher here.
bind = \$mod, F, fullscreen,
bind = \$mod SHIFT, Q, exit,
# focus
bind = \$mod, left,  movefocus, l
bind = \$mod, right, movefocus, r
bind = \$mod, up,    movefocus, u
bind = \$mod, down,  movefocus, d
# workspaces 1-5
bind = \$mod, 1, workspace, 1
bind = \$mod, 2, workspace, 2
bind = \$mod, 3, workspace, 3
bind = \$mod, 4, workspace, 4
bind = \$mod, 5, workspace, 5
bind = \$mod SHIFT, 1, movetoworkspace, 1
bind = \$mod SHIFT, 2, movetoworkspace, 2
bind = \$mod SHIFT, 3, movetoworkspace, 3
bind = \$mod SHIFT, 4, movetoworkspace, 4
bind = \$mod SHIFT, 5, movetoworkspace, 5
# move / resize with the mouse
bindm = \$mod, mouse:272, movewindow
bindm = \$mod, mouse:273, resizewindow
CONF
log "Wrote $HYPR/hyprland.conf (keyboard layout: $KBLAYOUT)"

# --- 3. SDDM session entry (needs root) --------------------------------------
log "Creating the 'Caelestia' login session entry (sudo)…"
sudo install -Dm644 /dev/stdin /usr/share/wayland-sessions/caelestia.desktop <<'DESK'
[Desktop Entry]
Name=Caelestia
Comment=Hyprland with the Caelestia shell
Exec=Hyprland
Type=Application
DesktopNames=Hyprland
DESK

log "Done!"
echo
echo "  Log out, then at the SDDM login screen choose the session menu and pick"
echo "  \"Caelestia\". Your KDE Plasma session is untouched and stays the default."
echo
warn "First launch tip: SUPER+Return opens a terminal, SUPER+SHIFT+Q exits Hyprland."
warn "If the Caelestia bar doesn't appear, run 'caelestia shell -d' from a terminal"
warn "inside the session to see any error output."
