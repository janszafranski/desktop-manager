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
        kb_layout = "us",
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
-- NB: because these binds are defined in Lua, `hyprctl binds` reports their
-- dispatcher as "__lua" with no action text. The keybind widget therefore
-- relies on the `description` field below to label each bind — keep one on
-- every bind so the cheatsheet never falls back to showing "__lua N".
hl.bind(mod .. " + Return", hl.dsp.exec_cmd("alacritty"), { description = "Terminal" })
hl.bind(mod .. " + Space",  hl.dsp.exec_cmd("caelestia shell drawers toggle launcher"), { description = "App launcher" })
hl.bind(mod .. " + Q", hl.dsp.window.close(), { description = "Close window" })
hl.bind(mod .. " + E", hl.dsp.exec_cmd("dolphin"), { description = "File manager" })
hl.bind(mod .. " + K", hl.dsp.exec_cmd("chromium --app=https://keep.google.com"), { description = "Google Keep" })
hl.bind(mod .. " + O", hl.dsp.exec_cmd("alacritty --title OpenClaw -e openclaw chat"), { description = "OpenClaw chat" })
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
hl.bind("Print",               hl.dsp.global("caelestia:screenshot"),     { description = "Screenshot" })
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
hl.bind(mod .. " + C",       hl.dsp.exec_cmd("alacritty --title 'Claude Code' -e claude --dangerously-skip-permissions"), { description = "Claude Code" })
hl.bind(mod .. " + SHIFT + C", hl.dsp.exec_cmd("pkill fuzzel || caelestia clipboard"), { description = "Clipboard history" })
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

-- float the Desktop Manager (system-replica) GUI instead of tiling it fullscreen
hl.window_rule({ name = "float-desktop-manager", match = { class = "system-replica" }, float = true })
