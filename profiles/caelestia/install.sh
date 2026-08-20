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
    hl.exec_cmd("qs -c keybinds")  -- persistent keybind widget (hot corner + Super+/)
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
    misc = {
        -- pin the "cats" wallpaper (wall2) for the pre-shell / shell-closed state;
        -- Hyprland shows a random wall0/1/2 otherwise. Leave disable_hyprland_logo
        -- false -- true would blank the default wallpaper entirely.
        force_default_wallpaper = 2,
    },
})

-- --- keybinds (minimal but usable) ---
-- NB: these binds are defined in Lua, so 'hyprctl binds' reports their
-- dispatcher as "__lua" with no action text. The keybind widget therefore
-- relies on the description field below to label each bind -- keep one on
-- every bind so the cheatsheet never falls back to showing "__lua N".
hl.bind(mod .. " + Return", hl.dsp.exec_cmd("alacritty"), { description = "Terminal" })
hl.bind(mod .. " + Space",  hl.dsp.exec_cmd("caelestia shell drawers toggle launcher"), { description = "App launcher" })
hl.bind(mod .. " + Q", hl.dsp.window.close(), { description = "Close window" })
hl.bind(mod .. " + E", hl.dsp.exec_cmd("dolphin"), { description = "File manager" })
hl.bind(mod .. " + K", hl.dsp.exec_cmd("chromium --app=https://keep.google.com"), { description = "Google Keep" })
hl.bind(mod .. " + F", hl.dsp.window.fullscreen(), { description = "Fullscreen" })
hl.bind(mod .. " + SHIFT + F", hl.dsp.exec_cmd("hyprctl dispatch fullscreen 1"), { description = "Maximise (keep bar)" })
hl.bind(mod .. " + V", hl.dsp.exec_cmd("hyprctl dispatch togglefloating"), { description = "Toggle floating" })
-- minimise = stash the window to a special (scratchpad) workspace; Super+Shift+H peeks/restores it
hl.bind(mod .. " + H",         hl.dsp.exec_cmd("hyprctl dispatch movetoworkspacesilent special:magic"), { description = "Minimise (stash to scratchpad)" })
hl.bind(mod .. " + SHIFT + H", hl.dsp.exec_cmd("hyprctl dispatch togglespecialworkspace magic"),        { description = "Show/hide scratchpad (restore)" })
hl.bind(mod .. " + SHIFT + Q", hl.dsp.exit(), { description = "Exit Hyprland" })
hl.bind(mod .. " + M", hl.dsp.exec_cmd("command -v hyprshutdown >/dev/null 2>&1 && hyprshutdown || hyprctl dispatch exit"), { description = "Logout" })

-- focus
hl.bind(mod .. " + left",  hl.dsp.focus({ direction = "left" }),  { description = "Focus left" })
hl.bind(mod .. " + right", hl.dsp.focus({ direction = "right" }), { description = "Focus right" })
hl.bind(mod .. " + up",    hl.dsp.focus({ direction = "up" }),    { description = "Focus up" })
hl.bind(mod .. " + down",  hl.dsp.focus({ direction = "down" }),  { description = "Focus down" })

-- move the active window within the tiling layout
hl.bind(mod .. " + SHIFT + left",  hl.dsp.exec_cmd("hyprctl dispatch movewindow l"), { description = "Move window left" })
hl.bind(mod .. " + SHIFT + right", hl.dsp.exec_cmd("hyprctl dispatch movewindow r"), { description = "Move window right" })
hl.bind(mod .. " + SHIFT + up",    hl.dsp.exec_cmd("hyprctl dispatch movewindow u"), { description = "Move window up" })
hl.bind(mod .. " + SHIFT + down",  hl.dsp.exec_cmd("hyprctl dispatch movewindow d"), { description = "Move window down" })

-- workspaces 1-5 (switch with mod, move active window with mod+SHIFT)
for i = 1, 5 do
    hl.bind(mod .. " + " .. i,         hl.dsp.focus({ workspace = i }),       { description = "Workspace " .. i })
    hl.bind(mod .. " + SHIFT + " .. i, hl.dsp.window.move({ workspace = i }), { description = "Move window to workspace " .. i })
end

-- move / resize with the mouse
hl.bind(mod .. " + mouse:272", hl.dsp.window.drag(),   { mouse = true, description = "Move window (drag)" })
hl.bind(mod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true, description = "Resize window (drag)" })

-- --- Caelestia shell actions (full list: hyprctl globalshortcuts) ---
hl.bind(mod .. " + D", hl.dsp.global("caelestia:dashboard"), { description = "Dashboard" })
hl.bind(mod .. " + N", hl.dsp.global("caelestia:nexus"),     { description = "Nexus" })
hl.bind(mod .. " + S", hl.dsp.global("caelestia:session"),   { description = "Session" })
hl.bind(mod .. " + U", hl.dsp.global("caelestia:utilities"), { description = "Utilities" })
hl.bind(mod .. " + W", hl.dsp.global("caelestia:sidebar"),   { description = "Sidebar" })
hl.bind(mod .. " + L", hl.dsp.global("caelestia:lock"),      { description = "Lock screen" })
hl.bind(mod .. " + Tab", hl.dsp.global("caelestia:showall"), { description = "Show all windows (overview)" })
hl.bind("Print",               hl.dsp.exec_cmd("spectacle"),             { description = "Screenshot (Spectacle)" })
hl.bind(mod .. " + SHIFT + S", hl.dsp.global("caelestia:screenshotClip"), { description = "Screenshot region to clipboard" })

-- volume (no caelestia global exists for it; drive wpctl -- the shell OSD follows the sink)
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true, description = "Volume up" })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"),        { locked = true, repeating = true, description = "Volume down" })
hl.bind("XF86AudioMute",        hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"),        { locked = true, description = "Mute" })
hl.bind("XF86AudioMicMute",     hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"),      { locked = true, description = "Mute microphone" })

-- media / brightness keys
hl.bind("XF86AudioPlay",  hl.dsp.global("caelestia:mediaToggle"), { locked = true, description = "Play/pause media" })
hl.bind("XF86AudioPause", hl.dsp.global("caelestia:mediaToggle"), { locked = true, description = "Play/pause media" })
hl.bind("XF86AudioNext",  hl.dsp.global("caelestia:mediaNext"),   { locked = true, description = "Next track" })
hl.bind("XF86AudioPrev",  hl.dsp.global("caelestia:mediaPrev"),   { locked = true, description = "Previous track" })
hl.bind("XF86MonBrightnessUp",   hl.dsp.global("caelestia:brightnessUp"),   { locked = true, repeating = true, description = "Brightness up" })
hl.bind("XF86MonBrightnessDown", hl.dsp.global("caelestia:brightnessDown"), { locked = true, repeating = true, description = "Brightness down" })

-- --- extra apps & utilities (pulled from upstream Caelestia; my letters kept) ---
hl.bind(mod .. " + B",       hl.dsp.exec_cmd("floorp"),                                { description = "Web browser (Floorp)" })
hl.bind(mod .. " + C",       hl.dsp.exec_cmd("pkill fuzzel || caelestia clipboard"),    { description = "Clipboard history" })
hl.bind(mod .. " + ALT + C", hl.dsp.exec_cmd("pkill fuzzel || caelestia clipboard -d"), { description = "Clipboard: delete an entry" })
hl.bind(mod .. " + Period",  hl.dsp.exec_cmd("pkill fuzzel || caelestia emoji -p"),     { description = "Emoji / glyph picker" })

-- keyboard window resize (mouse-free; hold to repeat)
hl.bind(mod .. " + Minus",         hl.dsp.exec_cmd("hyprctl dispatch resizeactive -60 0"), { repeating = true, description = "Shrink width" })
hl.bind(mod .. " + Equal",         hl.dsp.exec_cmd("hyprctl dispatch resizeactive 60 0"),  { repeating = true, description = "Grow width" })
hl.bind(mod .. " + SHIFT + Minus", hl.dsp.exec_cmd("hyprctl dispatch resizeactive 0 -60"), { repeating = true, description = "Shrink height" })
hl.bind(mod .. " + SHIFT + Equal", hl.dsp.exec_cmd("hyprctl dispatch resizeactive 0 60"),  { repeating = true, description = "Grow height" })

-- window groups (tabbed container)
hl.bind(mod .. " + G",         hl.dsp.exec_cmd("hyprctl dispatch togglegroup"),         { description = "Toggle window group" })
hl.bind(mod .. " + SHIFT + G", hl.dsp.exec_cmd("hyprctl dispatch changegroupactive f"), { description = "Cycle window within group" })
hl.bind(mod .. " + ALT + G",   hl.dsp.exec_cmd("hyprctl dispatch moveoutofgroup"),      { description = "Remove window from group" })

-- restart the Caelestia shell (kill / kill+relaunch)
hl.bind("CTRL + " .. mod .. " + SHIFT + R", hl.dsp.exec_cmd("qs -c caelestia kill"),                               { description = "Kill Caelestia shell" })
hl.bind("CTRL + " .. mod .. " + ALT + R",   hl.dsp.exec_cmd("qs -c caelestia kill; sleep .1; caelestia shell -d"), { description = "Restart Caelestia shell" })

-- keybind widget: Caelestia-styled QuickShell overlay (Super+/),
-- with the plain yad window as a fallback (Super+Shift+/)
hl.bind(mod .. " + slash",         hl.dsp.exec_cmd("~/.config/hypr/scripts/keybinds-toggle.sh"), { description = "Keybindings (this widget)" })
hl.bind(mod .. " + SHIFT + slash", hl.dsp.exec_cmd("~/.config/hypr/scripts/keybinds.sh"),        { description = "Keybindings (fallback list)" })

-- float the yad fallback window like a proper overlay
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
        | jq -r '.[] | [(.modmask|tostring), .key, .dispatcher, .arg, .description] | @tsv' \
        | while IFS=$'\t' read -r modmask key dispatcher arg desc; do
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
                *lua*)  action="" ;;   # opaque lua dispatcher; rely on description
                *)      action="$dispatcher${arg:+ $arg}" ;;
            esac
            [ -n "$desc" ] && action="$desc"
            [ -n "$action" ] || continue   # skip binds we can't label
            printf '%s\t%s\n' "$combo" "$action"
        done \
        | awk '!seen[$0]++' \
        | sort -f -t $'\t' -k1,1
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
log "Wrote $HYPR/scripts/keybinds.sh (yad fallback, bound to Super+Shift+/)"

# --- 2c. Caelestia-styled QuickShell keybind widget (Super+/) -----------------
QSDIR="$HOME/.config/quickshell/keybinds"
mkdir -p "$QSDIR"
cat > "$QSDIR/shell.qml" <<'QML'
// Caelestia-styled keybind widget (standalone QuickShell config).
// Run with:  qs -c keybinds   (runs persistently: hot-corner + Super+/ toggle)
// Reads Hyprland binds live via hyprctl, and pulls its colours + font from the
// running Caelestia scheme so it always matches the shell's current theme.

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root

    // ---------- theme (read live from Caelestia's scheme.json) ----------
    property var colours: ({})
    function col(name, fallback) {
        return "#" + (colours[name] !== undefined ? colours[name] : fallback);
    }

    readonly property string stateDir:
        (Quickshell.env("XDG_STATE_HOME") || (Quickshell.env("HOME") + "/.local/state")) + "/caelestia"

    FileView {
        path: root.stateDir + "/scheme.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                root.colours = JSON.parse(text()).colours;
            } catch (e) {
                // keep fallbacks
            }
        }
    }

    // remembers the dragged position across opens
    FileView {
        id: posStore
        path: root.stateDir + "/keybinds-widget.json"
        printErrors: false
        onLoaded: {
            try {
                const p = JSON.parse(text());
                if (typeof p.x === "number" && typeof p.y === "number") {
                    card.x = p.x;
                    card.y = p.y;
                }
            } catch (e) {
                // no saved position yet
            }
        }
    }

    FontLoader {
        id: sans
        source: "file:///etc/xdg/quickshell/caelestia/assets/google-sans-flex/GoogleSansFlex-VariableFont_GRAD,ROND,opsz,slnt,wdth,wght.ttf"
    }

    // ---------- visibility state ----------
    property bool pinned: false        // toggled open via Super+/ (stays until toggled)
    property bool hoverShown: false    // opened by the hot corner (auto-hides)
    readonly property bool shown: pinned || hoverShown
    readonly property bool rawHover: hotCorner.containsMouse || cardArea.containsMouse
    onRawHoverChanged: {
        if (rawHover) {
            hideTimer.stop();
            hoverShown = true;
        } else {
            hideTimer.restart();
        }
    }
    // re-read binds whenever the widget opens, so it always reflects the live config
    onShownChanged: {
        if (shown)
            gsProc.running = true;
    }

    // Super+/ flips the pinned state: `qs -c keybinds ipc call keybinds toggle`
    IpcHandler {
        target: "keybinds"
        function toggle(): void {
            root.pinned = !root.pinned;
        }
    }

    // ---------- data (built from hyprctl) ----------
    property var rows: []
    property var descs: ({})

    Process {
        id: gsProc
        running: true
        command: ["hyprctl", "globalshortcuts"]
        stdout: StdioCollector {
            onStreamFinished: {
                const d = ({});
                const lines = text.split("\n");
                for (let i = 0; i < lines.length; i++) {
                    const parts = lines[i].split(" -> ");
                    if (parts.length === 2)
                        d[parts[0].trim()] = parts[1].trim();
                }
                root.descs = d;
                bindsProc.running = true;
            }
        }
    }

    Process {
        id: bindsProc
        running: false
        command: ["hyprctl", "-j", "binds"]
        stdout: StdioCollector {
            onStreamFinished: {
                let arr = [];
                try {
                    arr = JSON.parse(text);
                } catch (e) {
                    return;
                }
                const out = [];
                const seen = ({});
                for (let i = 0; i < arr.length; i++) {
                    const b = arr[i];
                    const m = b.modmask;
                    let combo = "";
                    if (m & 64) combo += "Super  ";
                    if (m & 8)  combo += "Alt  ";
                    if (m & 4)  combo += "Ctrl  ";
                    if (m & 1)  combo += "Shift  ";
                    combo += b.key;

                    let action;
                    if (b.description && b.description.length > 0)
                        action = b.description;
                    else if (b.dispatcher === "exec")
                        action = b.arg;
                    else if (b.dispatcher === "global")
                        action = root.descs[b.arg] || b.arg;
                    else if (b.dispatcher && b.dispatcher.indexOf("lua") !== -1)
                        continue;  // opaque __lua bind with no description -- nothing meaningful to show
                    else
                        action = b.dispatcher + (b.arg ? " " + b.arg : "");

                    const dedupKey = combo + "\t" + action;
                    if (seen[dedupKey])
                        continue;
                    seen[dedupKey] = true;
                    out.push({ combo: combo, action: action });
                }
                out.sort(function (a, b) { return a.combo.toLowerCase().localeCompare(b.combo.toLowerCase()); });
                root.rows = out;
            }
        }
    }

    // ---------- window ----------
    PanelWindow {
        id: win
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        // Overlay (not Top) so the top-right hot corner sits ABOVE the Caelestia
        // bar -- on the Top layer the bar would eat the corner hover.
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        WlrLayershell.namespace: "caelestia-keybinds"
        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }

        // input region: the top-right hot corner (always) + the card (when shown)
        mask: Region {
            x: hotCorner.x
            y: hotCorner.y
            width: hotCorner.width
            height: hotCorner.height
            Region {
                x: card.x
                y: card.y
                width: root.shown ? card.width : 0
                height: root.shown ? card.height : 0
            }
        }

        // hovering the very top-right corner opens the widget
        MouseArea {
            id: hotCorner
            anchors.top: parent.top
            anchors.right: parent.right
            width: 12
            height: 12
            hoverEnabled: true
        }

        // grace period so moving from the corner onto the card doesn't hide it
        Timer {
            id: hideTimer
            interval: 350
            onTriggered: root.hoverShown = false
        }

        Rectangle {
            id: card
            width: 640
            // default: top-right corner. Plain bindings until you drag it
            // (a drag assigns literal x/y, and a saved position overrides these).
            x: parent.width - width - 16
            y: 16
            // cap so it stays a compact top-right card (scrolls) instead of
            // stretching into a full-height right-edge sidebar when there are
            // many binds.
            height: Math.min(parent.height - 32, 820, 56 + header.implicitHeight + 16 + list.contentHeight)
            radius: 28
            color: root.col("surface", "131317")
            border.width: 1
            border.color: root.col("outlineVariant", "47464f")

            visible: opacity > 0
            opacity: root.shown ? 1 : 0
            scale: root.shown ? 1 : 0.96
            transformOrigin: Item.TopRight
            Behavior on opacity { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
            Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            ColumnLayout {
                id: cardCol
                anchors.fill: parent
                anchors.margins: 28
                spacing: 16

                RowLayout {
                    id: header
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: "Keybindings"
                        color: root.col("primary", "c2c1ff")
                        font.family: sans.name
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: root.rows.length + " binds"
                        color: root.col("onSurfaceVariant", "c8c5d1")
                        font.family: sans.name
                        font.pixelSize: 13
                    }
                }

                ListView {
                    id: list
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: root.rows
                    spacing: 6
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: Rectangle {
                        id: del
                        required property var modelData
                        width: ListView.view.width
                        height: 44
                        radius: 14
                        color: root.col("surfaceContainer", "201f23")

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 16
                            spacing: 16

                            Text {
                                text: del.modelData.combo
                                color: root.col("primary", "c2c1ff")
                                font.family: "monospace"
                                font.pixelSize: 14
                                font.weight: Font.Medium
                            }
                            Text {
                                Layout.fillWidth: true
                                horizontalAlignment: Text.AlignRight
                                elide: Text.ElideRight
                                text: del.modelData.action
                                color: root.col("onSurface", "e5e1e7")
                                font.family: sans.name
                                font.pixelSize: 14
                            }
                        }
                    }
                }
            }

            // drag the card around by its header strip
            MouseArea {
                id: dragArea
                anchors {
                    top: parent.top
                    left: parent.left
                    right: parent.right
                }
                height: 28 + header.implicitHeight
                drag.target: card
                cursorShape: Qt.OpenHandCursor
                onReleased: posStore.setText(JSON.stringify({ x: card.x, y: card.y }))
            }

            // tracks hover over the whole card (keeps it open); passes buttons through
            MouseArea {
                id: cardArea
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.NoButton
            }
        }
    }
}
QML
log "Wrote $QSDIR/shell.qml (QuickShell widget, run: qs -c keybinds)"

# toggle script for Super+/ (open/close the non-modal widget)
cat > "$HYPR/scripts/keybinds-toggle.sh" <<'TOGGLE'
#!/usr/bin/env bash
# Toggle the Caelestia-styled QuickShell keybind widget open/closed.
#
# The widget runs persistently (for the top-right hot corner), so this just flips
# its pinned state over Quickshell IPC. If it isn't running yet, launch it.
#
# Safe process matching: this ONLY ever targets `qs -c keybinds`, never the bare
# `qs` binary — the Caelestia shell itself runs as `qs -c caelestia`, so matching
# the full config name avoids killing the shell.
if pgrep -f 'qs -c keybinds' >/dev/null; then
    qs -c keybinds ipc call keybinds toggle
else
    setsid qs -c keybinds >/dev/null 2>&1 &
fi
TOGGLE
chmod +x "$HYPR/scripts/keybinds-toggle.sh"
log "Wrote $HYPR/scripts/keybinds-toggle.sh (bound to Super+/)"

# --- 2d. Colour scheme: catppuccin mocha with black (AMOLED) surfaces ---------
# The shell derives every colour from ~/.local/state/caelestia/scheme.json.
# Apply the preferred scheme, then overwrite the neutral/surface family with a
# pure-black ramp (keeping catppuccin accents + text) so the shell reads black.
# NB: re-running `caelestia scheme set` regenerates scheme.json and undoes this,
# so re-run this installer (or re-apply the patch) after any scheme change.
# Write the standalone re-blacken helper first — it is the single source of
# truth for the AMOLED patch, called here and by set-wallpaper.sh below.
cat > "$HYPR/scripts/blacken.sh" <<'BLACKEN'
#!/usr/bin/env bash
# Re-apply the pure-black AMOLED surface ramp to the Caelestia scheme, keeping
# the catppuccin accents. Run this after `caelestia scheme set` or a wallpaper
# change, both of which regenerate scheme.json and reset surfaces to dark-gray.
# The shell reads scheme.json live (FileView watch), so this applies instantly.
set -euo pipefail
scheme="${XDG_STATE_HOME:-$HOME/.local/state}/caelestia/scheme.json"

python3 - "$scheme" <<'PY'
import json, os, sys, tempfile
p = sys.argv[1]
d = json.load(open(p))
d.setdefault("colours", {}).update({
    "background": "000000", "surface": "000000", "surfaceDim": "000000",
    "surfaceBright": "1a1a1a", "surfaceContainerLowest": "000000",
    "surfaceContainerLow": "0a0a0a", "surfaceContainer": "0d0d0d",
    "surfaceContainerHigh": "141414", "surfaceContainerHighest": "1c1c1c",
    "surfaceVariant": "2a2a2a", "surface0": "121212", "surface1": "1a1a1a",
    "surface2": "222222",
})
fd, t = tempfile.mkstemp(dir=os.path.dirname(p))
os.write(fd, json.dumps(d).encode()); os.close(fd); os.replace(t, p)
PY
echo "Black surfaces re-applied to $scheme"
BLACKEN
chmod +x "$HYPR/scripts/blacken.sh"
log "Wrote $HYPR/scripts/blacken.sh (standalone black-surface patch)"

log "Setting scheme to catppuccin mocha with black surfaces…"
caelestia scheme set -n catppuccin -f mocha -m dark >/dev/null 2>&1 \
    || warn "caelestia scheme set failed (is the CLI installed?); black patch may still apply to the existing scheme"

SCHEME_JSON="${XDG_STATE_HOME:-$HOME/.local/state}/caelestia/scheme.json"
if [ -f "$SCHEME_JSON" ]; then
    "$HYPR/scripts/blacken.sh"
    log "Applied black surfaces to $SCHEME_JSON"
else
    warn "$SCHEME_JSON not found; skipped black surface patch"
fi

# --- 2e. On-demand wallpaper switcher (keeps the black surfaces) --------------
cat > "$HYPR/scripts/set-wallpaper.sh" <<'WALLSET'
#!/usr/bin/env bash
# Set the Caelestia wallpaper, keeping the black surfaces.
# Usage: set-wallpaper.sh [image]   (default: Hyprland's "cats" wallpaper)
# The three Hyprland built-in wallpapers live in /usr/share/hypr/wall{0,1,2}.png
# (wall2 = anime girl + cats). These are what you see before the shell loads.
set -euo pipefail
wall="${1:-/usr/share/hypr/wall2.png}"

caelestia wallpaper -f "$wall"

# caelestia re-reads the catppuccin theme colours on a wallpaper change, which
# undoes the black surfaces -- re-apply them (single source of truth).
"$(dirname "$(readlink -f "$0")")/blacken.sh"
echo "Wallpaper: $wall  (black surfaces preserved)"
WALLSET
chmod +x "$HYPR/scripts/set-wallpaper.sh"
log "Wrote $HYPR/scripts/set-wallpaper.sh (on-demand wallpaper switcher)"

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
