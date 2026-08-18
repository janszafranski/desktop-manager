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
# Hyprland 0.56+ uses a Lua config (hyprland.lua); the legacy hyprland.conf is
# deprecated and slated for removal, so we write the Lua format.
HYPR="$HOME/.config/hypr"
for old in hyprland.conf hyprland.lua; do
  if [[ -e "$HYPR/$old" ]]; then
    bak="$HYPR/$old.bak-$(date +%Y%m%d-%H%M%S)"
    cp -a "$HYPR/$old" "$bak"; warn "backed up existing config -> $bak"
  fi
done
# A leftover legacy hyprland.conf would just sit unused next to hyprland.lua;
# move it aside so it's clear the Lua file is authoritative.
[[ -e "$HYPR/hyprland.conf" ]] && mv "$HYPR/hyprland.conf" "$HYPR/hyprland.conf.pre-lua"
mkdir -p "$HYPR"

# detect keyboard layout (KDE, else localectl, else us)
KBLAYOUT="$(kreadconfig6 --file kxkbrc --group Layout --key LayoutList 2>/dev/null | cut -d, -f1)"
[[ -z $KBLAYOUT ]] && KBLAYOUT="$(localectl status 2>/dev/null | awk -F: '/X11 Layout/{gsub(/ /,"",$2);print $2}')"
KBLAYOUT="${KBLAYOUT:-us}"

cat > "$HYPR/hyprland.lua" <<CONF
-- Minimal Hyprland (Lua) config that autostarts the Caelestia shell.
-- For the full Caelestia keybind/UX set, install the caelestia dotfiles later:
--   https://github.com/caelestia-dots/caelestia

local mod = "SUPER"

-- --- monitors ---
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "1" })

-- --- environment ---
hl.env("XCURSOR_SIZE", "24")
hl.env("QT_QPA_PLATFORM", "wayland")

-- --- autostart ---
hl.on("hyprland.start", function()
    hl.exec_cmd("caelestia shell -d")
    hl.exec_cmd("/usr/lib/polkit-kde-authentication-agent-1")
end)

-- --- look, feel and input ---
hl.config({
    general = {
        gaps_in  = 5,
        gaps_out = 10,
        border_size = 2,
        layout = "dwindle",
    },
    decoration = {
        rounding = 18,
    },
    input = {
        kb_layout = "${KBLAYOUT}",
        follow_mouse = 1,
        touchpad = {
            natural_scroll = true,
        },
    },
})

-- --- keybinds (minimal but usable) ---
hl.bind(mod .. " + Return", hl.dsp.exec_cmd("alacritty"))
hl.bind(mod .. " + Space",  hl.dsp.exec_cmd("caelestia shell drawers toggle launcher"))
hl.bind(mod .. " + Q", hl.dsp.window.close())
hl.bind(mod .. " + E", hl.dsp.exec_cmd("dolphin"))
hl.bind(mod .. " + F", hl.dsp.window.fullscreen())
hl.bind(mod .. " + SHIFT + Q", hl.dsp.exit())

-- focus
hl.bind(mod .. " + left",  hl.dsp.focus({ direction = "left" }))
hl.bind(mod .. " + right", hl.dsp.focus({ direction = "right" }))
hl.bind(mod .. " + up",    hl.dsp.focus({ direction = "up" }))
hl.bind(mod .. " + down",  hl.dsp.focus({ direction = "down" }))

-- workspaces 1-5 (switch with mod, move active window with mod+SHIFT)
for i = 1, 5 do
    hl.bind(mod .. " + " .. i,         hl.dsp.focus({ workspace = i }))
    hl.bind(mod .. " + SHIFT + " .. i, hl.dsp.window.move({ workspace = i }))
end

-- move / resize with the mouse
hl.bind(mod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind(mod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- --- Caelestia shell actions (full list: hyprctl globalshortcuts) ---
hl.bind(mod .. " + D", hl.dsp.global("caelestia:dashboard"))
hl.bind(mod .. " + N", hl.dsp.global("caelestia:nexus"))
hl.bind(mod .. " + S", hl.dsp.global("caelestia:session"))
hl.bind(mod .. " + U", hl.dsp.global("caelestia:utilities"))
hl.bind(mod .. " + B", hl.dsp.global("caelestia:sidebar"))
hl.bind(mod .. " + L", hl.dsp.global("caelestia:lock"))
hl.bind("Print",               hl.dsp.global("caelestia:screenshot"))
hl.bind(mod .. " + SHIFT + S", hl.dsp.global("caelestia:screenshotClip"))

-- media / brightness keys
hl.bind("XF86AudioPlay",  hl.dsp.global("caelestia:mediaToggle"), { locked = true })
hl.bind("XF86AudioPause", hl.dsp.global("caelestia:mediaToggle"), { locked = true })
hl.bind("XF86AudioNext",  hl.dsp.global("caelestia:mediaNext"),   { locked = true })
hl.bind("XF86AudioPrev",  hl.dsp.global("caelestia:mediaPrev"),   { locked = true })
hl.bind("XF86MonBrightnessUp",   hl.dsp.global("caelestia:brightnessUp"),   { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.global("caelestia:brightnessDown"), { locked = true, repeating = true })

-- keybind cheatsheet overlay (this popup)
hl.bind(mod .. " + slash", hl.dsp.exec_cmd("~/.config/hypr/scripts/keybinds.sh"))

-- float the keybind widget window like a proper overlay
hl.window_rule({ name = "float-keybinds", match = { class = "yad" }, float = true })
CONF
log "Wrote $HYPR/hyprland.lua (keyboard layout: $KBLAYOUT)"

# --- 2b. Keybind cheatsheet script (Super+/) ---------------------------------
mkdir -p "$HYPR/scripts"
cat > "$HYPR/scripts/keybinds.sh" <<'SHEET'
#!/usr/bin/env bash
# Hyprland keybind widget — a simple window that just lists your keybindings.
# Auto-generated from `hyprctl binds`, so it always matches the running config
# (no manual upkeep). Global shortcuts (caelestia:*) show their descriptions
# from `hyprctl globalshortcuts`.
#
# Usage:
#   keybinds.sh            show the widget (yad window)
#   keybinds.sh --fuzzel   show as a searchable fuzzel list instead
#   keybinds.sh --print    dump plain text to stdout
set -uo pipefail

render() {   # emits one "<combo>\t<action>" line per bind
    # Map: global-shortcut name -> description ("caelestia:dashboard" -> "Toggle dashboard")
    declare -A DESC
    while IFS= read -r line; do
        [[ $line == *" -> "* ]] || continue
        DESC["${line%% -> *}"]="${line#* -> }"
    done < <(hyprctl globalshortcuts 2>/dev/null)

    hyprctl binds -j 2>/dev/null \
        | jq -r '.[] | [(.modmask|tostring), .key, .dispatcher, .arg] | @tsv' \
        | while IFS=$'\t' read -r modmask key dispatcher arg; do
            combo=""
            (( modmask & 64 )) && combo+="Super+"
            (( modmask & 8  )) && combo+="Alt+"
            (( modmask & 4  )) && combo+="Ctrl+"
            (( modmask & 1  )) && combo+="Shift+"
            combo+="$key"

            case "$dispatcher" in
                exec)   action="$arg" ;;
                global) action="${DESC[$arg]:-$arg}" ;;
                "")     action="(none)" ;;
                *)      action="$dispatcher${arg:+ $arg}" ;;
            esac
            printf '%s\t%s\n' "$combo" "$action"
        done
}

case "${1:-}" in
    --print)
        render | column -t -s $'\t'
        ;;
    --fuzzel)
        render | awk -F'\t' '{printf "%-26s  %s\n", $1, $2}' \
            | fuzzel --dmenu --prompt "keybinds  " --font "monospace:size=11" \
                     --width 64 --lines 25 >/dev/null 2>&1 || true
        ;;
    *)
        # yad: one field per line feeds the two-column list widget
        render | tr '\t' '\n' \
            | yad --list --title="Keybindings" \
                  --text="Hyprland / Caelestia keybindings" \
                  --column="Key" --column="Action" \
                  --width=560 --height=680 --center \
                  --button="Close:0" --borders=8 >/dev/null 2>&1 || true
        ;;
esac
SHEET
chmod +x "$HYPR/scripts/keybinds.sh"
log "Wrote $HYPR/scripts/keybinds.sh (bound to Super+/)"

# --- 3. SDDM session entry (needs root) --------------------------------------
log "Creating the 'Caelestia' login session entry (sudo)…"
sudo install -Dm644 /dev/stdin /usr/share/wayland-sessions/caelestia.desktop <<'DESK'
[Desktop Entry]
Name=Caelestia
Comment=Hyprland with the Caelestia shell
Exec=start-hyprland
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
