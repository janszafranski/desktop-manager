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
    -- OpenClaw flyout: launch HERE (login start block), not as a bare top-level stmt.
    -- A top-level hl.exec_cmd fires at config-parse time, before the Wayland socket
    -- is ready, so the QS process died on cold boot every time (recurring "flyout
    -- won't start"). Inside hyprland.start it comes up reliably, like qs -c keybinds. (2026-09-03)
    -- Launch guard: hyprland.start can fire more than once on boot, which spawned
    -- duplicate overlapping panels. Inline shell operators break bare hl.exec_cmd
    -- (it runs argv, not a shell), so the guard lives in a plain script exec'd by
    -- path — the same reliable pattern as blacken.sh below. Starts one panel, and
    -- a repeat fire no-ops. (2026-09-03)
    hl.exec_cmd("bash /home/jan/.config/hypr/scripts/start-openclaw-sidebar.sh")
    -- OpenClaw flyout tray: the "AI" taskbar icon that opens/closes the flyout with
    -- a mouse (StatusNotifierItem in the Caelestia bar tray). Same guard pattern as
    -- the sidebar: dedup so a repeat hyprland.start fire won't spawn a second tray.
    hl.exec_cmd("bash /home/jan/.config/hypr/scripts/start-openclaw-tray.sh")
    -- Re-apply the pure-black AMOLED surface ramp to Caelestia every login. caelestia
    -- regenerates scheme.json (dark-grey #131317 surfaces) from the wallpaper, so without
    -- this the bar/panels revert to grey. blacken.sh is idempotent; shell reads it live.
    hl.exec_cmd("bash ~/.config/hypr/scripts/blacken.sh")
    hl.exec_cmd("/usr/bin/shakefree-mouse-autostart")  -- shakefree-mouse: launches daemon + tray per GUI toggles (SUPER+SHIFT+M toggles, run shakefree-mouse to tune)
    -- Guard script: bare "easyeffects --service-mode" fired here at cold boot BEFORE
    -- PipeWire was ready, so it exited without ever creating easyeffects_source (mic
    -- effects silently dead every boot). The guard waits for PipeWire, launches the
    -- headless service, then sets easyeffects_source as the default mic. (2026-09-04)
    hl.exec_cmd("bash /home/jan/.config/hypr/scripts/start-easyeffects.sh")  -- mic effects (RNNoise + Autogain + EQ); provides easyeffects_source = the default mic
end)

-- OpenClaw sidebar: blur OFF. On the Intel HD 630 iGPU a full-height, always-pinned
-- blurred layer surface drags the whole compositor's frame pacing (loses the app-open
-- bounce, sluggish motion). The panel is near-opaque (colBg alpha) so it looks clean
-- without frost. Flip blur = true to restore frost if you ever move to a real GPU.
hl.layer_rule({ match = { namespace = "openclaw-sidebar" }, blur = false })

-- --- look, feel and input ---
hl.config({
    general = {
        gaps_in  = 5,
        gaps_out = 10,
        border_size = 2,
        layout = "dwindle",
        ["col.active_border"]   = "rgba(000000ff)",  -- black window frames (Jan's call)
        ["col.inactive_border"] = "rgba(000000ff)",
    },
    decoration = {
        rounding = 18,
        blur = {
            enabled = false,      -- OFF globally (2026-08-26). size5/passes3 over 3440x1440 on
                                  -- the HD 630 iGPU saturated the GPU on every window open ->
                                  -- dropped the app-open animation + sluggish launches. Even the
                                  -- Caelestia bar/panel frost cost too much. Jan's call: kill it.
                                  -- Flip to true (+ size 3 / passes 1 for a light, cheap frost)
                                  -- only on a real GPU.
            size = 5,
            passes = 3,
            xray = true,          -- blur samples the wallpaper, not windows behind
            new_optimizations = true,
        },
    },
    input = {
        -- Custom: plain US layout with sterling (£) on Shift+4 (see ~/.config/xkb/symbols/usgbp).
        -- Nothing else moves. AltGr+4 still gives $.
        kb_layout = "usgbp",
        follow_mouse = 1,
        -- flat = constant 1:1 pointer gain (no speed-based acceleration). Fixes the
        -- pointer "skipping/overshooting" when slowing down onto a target (2026-09-10).
        accel_profile = "flat",
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
    animations = {
        enabled = true,
    },
})

-- --- animations (2026-08-26) ---
-- The minimal config previously defined NO curves/animations, so Hyprland fell back
-- to its compiled-in defaults (global speed 8 = a laggy 0.8s window open, plain
-- `default` bezier = zero overshoot). That read as "sluggish + no bounce" even though
-- the machine is idle/HW-accelerated. Fix = snappier speeds + an easeOutBack overshoot
-- curve on windowsIn for a real pop. Speed is duration in 1/10s (lower = faster).
-- "shudder" = an underdamped SPRING (mass/stiffness/dampening), not a bezier. A bezier can
-- only overshoot ONCE over a fixed duration (= a slow single lob). A spring with high
-- stiffness + low dampening snaps open fast and then OSCILLATES a few times before settling
-- = the sudden bouncy/shuddering stop Jan wants. Damping ratio ~0.25 (underdamped) here.
hl.curve("shudder",  { type = "spring", mass = 0.6, stiffness = 1400, dampening = 17 })  -- SPED UP 2026-09-10 (was m0.8/s1100/d13): quick snap, one clear bounce + short settle; ζ~0.29
hl.curve("snapOut",  { type = "bezier", points = { {0.16, 1},    {0.3,  1} } })  -- fast, smooth settle (no overshoot)
hl.curve("linear",   { type = "bezier", points = { {0, 0},       {1,    1} } })

hl.animation({ leaf = "global",     enabled = true, speed = 5,   bezier = "default" })
hl.animation({ leaf = "windows",    enabled = true, speed = 4,   bezier = "snapOut" })
hl.animation({ leaf = "windowsIn",  enabled = true, speed = 4, spring = "shudder", style = "popin 70%" })  -- fast snap + shudder (spring governs timing; speed field still required by parser)
hl.animation({ leaf = "windowsOut", enabled = true, speed = 2.5, bezier = "linear",  style = "popin 80%" })
hl.animation({ leaf = "border",     enabled = true, speed = 5,   bezier = "default" })
hl.animation({ leaf = "fade",       enabled = true, speed = 2.5, bezier = "snapOut" })
hl.animation({ leaf = "fadeIn",     enabled = true, speed = 2.5, bezier = "snapOut" })
hl.animation({ leaf = "fadeOut",    enabled = true, speed = 2,   bezier = "snapOut" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 3,   bezier = "snapOut", style = "slide" })
hl.animation({ leaf = "layers",     enabled = true, speed = 3,   bezier = "snapOut", style = "fade" })

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
-- (Super+O toggle moved to the >>> openclaw-flyout >>> block below to avoid a duplicate bind)
hl.bind(mod .. " + ALT + O", hl.dsp.exec_cmd("alacritty --title OpenClaw -e ~/.local/bin/openclaw-cli-chat.sh"),      { description = "OpenClaw chat (terminal)" })
hl.bind(mod .. " + SHIFT + O", hl.dsp.exec_cmd("~/.local/bin/openclaw-dashboard.sh"),             { description = "OpenClaw web Control UI" })
hl.bind(mod .. " + Y", hl.dsp.exec_cmd("gtk-launch floorp-fe0c47aa-eaaf-4a45-8cda-01aca864f927.desktop"), { description = "YouTube (webapp)" })
hl.bind(mod .. " + F", hl.dsp.window.fullscreen(), { description = "Fullscreen" })
hl.bind(mod .. " + SHIFT + F", hl.dsp.exec_cmd("hyprctl dispatch fullscreen 1"), { description = "Maximise (keep bar)" })
hl.bind(mod .. " + V", hl.dsp.exec_cmd("hyprctl dispatch togglefloating"), { description = "Toggle floating" })
-- Super+H launches Home Assistant (floorp webapp). Minimise/scratchpad moved to Super+Ctrl+H.
hl.bind(mod .. " + H",         hl.dsp.exec_cmd("gtk-launch floorp-414d8096-59bb-4ae6-acd0-74cd643dfea4.desktop"), { description = "Home Assistant" })
hl.bind(mod .. " + CTRL + H",  hl.dsp.exec_cmd("hyprctl dispatch movetoworkspacesilent special:magic"), { description = "Minimise (stash to scratchpad)" })
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
hl.bind(mod .. " + SHIFT + M",     hl.dsp.exec_cmd("/usr/bin/shakefree-mouse-toggle"),          { description = "Toggle Shakefree Mouse (tremor filter)" })

-- float the yad fallback window like a proper overlay
hl.window_rule({ name = "float-keybinds", match = { class = "yad" }, float = true })

-- float the Desktop Manager (system-replica) GUI instead of tiling it fullscreen
hl.window_rule({ name = "float-desktop-manager", match = { class = "system-replica" }, float = true })

-- float the Shakefree Mouse (tremor filter) control panel, centred like the others
hl.window_rule({ name = "float-shakefree-mouse", match = { class = "io.github.janszafranski.shakefreemouse" }, float = true })


-- >>> openclaw-flyout >>>
-- (launch moved into the hyprland.start block above — a bare exec here ran too early on cold boot)
hl.bind(mod .. " + O", hl.dsp.exec_cmd("qs -c openclaw-sidebar ipc call sidebar toggle"), { description = "OpenClaw flyout" })
hl.layer_rule({ name = "openclaw-flyout-noblur", match = { namespace = "openclaw-sidebar" }, blur = false })
-- <<< openclaw-flyout <<<
