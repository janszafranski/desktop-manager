pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Best-effort theme integration, in this order:
//
//   1. Omarchy    ~/.config/omarchy/current/theme — `light.mode` marks a light
//                 theme, and `col.active_border` in the theme's hyprland.conf
//                 gives us an accent. (Omarchy has no single colours file.)
//   2. end-4 / illogical-impulse — material_colors.scss, so the thing looks
//                 right on a non-Omarchy Hyprland box too.
//   3. Hardcoded defaults.
Singleton {
    id: root

    readonly property string configHome: Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config"
    readonly property string omarchyTheme: configHome + "/omarchy/current/theme"
    readonly property string endFourColors: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state")
        + "/quickshell/user/generated/material_colors.scss"

    property bool light: false
    property color accent: "#7aa2f7"
    property color surface: "#1b1b20"
    property color surfaceText: "#e8e8ee"

    // Icon labels sit on the wallpaper, which has nothing to do with the UI
    // theme, so they do not follow `light`. White on a dark shadow is the
    // Windows/macOS treatment and survives both light and dark wallpapers.
    readonly property color labelColor: "#ffffff"
    readonly property color labelShadow: Qt.rgba(0, 0, 0, 0.85)

    readonly property color selection: Qt.rgba(accent.r, accent.g, accent.b, 0.28)
    readonly property color selectionBorder: Qt.rgba(accent.r, accent.g, accent.b, 0.7)
    readonly property color hover: light ? Qt.rgba(0, 0, 0, 0.08) : Qt.rgba(1, 1, 1, 0.12)
    readonly property color surfaceBorder: light ? Qt.rgba(0, 0, 0, 0.14) : Qt.rgba(1, 1, 1, 0.14)
    readonly property color surfaceTextDim: light ? Qt.rgba(0, 0, 0, 0.5) : Qt.rgba(1, 1, 1, 0.45)

    function read(view, path) {
        view.path = "";
        view.path = path;
        return view.text();
    }

    function scssVar(text, name) {
        const m = text.match(new RegExp("\\$" + name + ":\\s*([^;\\s]+)"));
        return m ? m[1] : "";
    }

    function reload() {
        if (loadOmarchy()) return;
        if (loadEndFour()) return;
        light = false;
        accent = "#7aa2f7";
        surface = "#1b1b20";
        surfaceText = "#e8e8ee";
    }

    function loadOmarchy() {
        const conf = read(hyprConf, omarchyTheme + "/hyprland.conf");
        if (!hyprConf.loaded) return false;

        read(lightMode, omarchyTheme + "/light.mode"); // usually an empty marker file
        light = lightMode.loaded;

        const m = conf.match(/col\.active_border\s*=\s*(?:rgba?\()?\s*([0-9a-fA-F]{6,8})/);
        if (m) accent = "#" + m[1].slice(0, 6);
        surface = light ? "#f5f5f7" : "#1b1b20";
        surfaceText = light ? "#101014" : "#e8e8ee";
        return true;
    }

    function loadEndFour() {
        const text = read(scss, endFourColors);
        if (!scss.loaded || !text) return false;

        light = scssVar(text, "darkmode").toLowerCase() !== "true";
        const primary = scssVar(text, "primary");
        if (primary) accent = primary;
        const container = scssVar(text, "surfaceContainer");
        if (container) surface = container;
        const onSurface = scssVar(text, "onSurface");
        if (onSurface) surfaceText = onSurface;
        return true;
    }

    FileView { id: lightMode; blockLoading: true; printErrors: false }
    FileView { id: hyprConf; blockLoading: true; printErrors: false }
    FileView { id: scss; blockLoading: true; printErrors: false }

    Component.onCompleted: reload()
}
