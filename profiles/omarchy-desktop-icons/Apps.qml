pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Turns a config item into {label, icon, command} and launches it.
//
// A config item is either:
//   { desktop_id: "firefox.desktop" }  -> name, icon and Exec come from the
//                                         .desktop entry and the active icon
//                                         theme, so icons follow the theme.
//   { exec: "foo --bar", icon: "..." } -> raw command, explicit icon name/path.
Singleton {
    id: root

    readonly property string fallbackIcon: "application-x-executable"

    // Resolved once at startup; used for Terminal=true entries.
    property string terminal: "xterm"

    // DesktopEntries populates asynchronously after startup. Bindings that
    // call into the resolver functions below read `revision`, so they
    // re-evaluate once the entries actually arrive.
    property int revision: 0

    // valuesChanged fires once per entry as the index is built, so coalesce
    // instead of invalidating every icon's bindings a few hundred times.
    Connections {
        target: DesktopEntries.applications
        function onValuesChanged() { bump.restart(); }
    }

    Timer {
        id: bump
        interval: 50
        onTriggered: root.revision++
    }

    function entryFor(item) {
        if (revision < 0) return null; // reads `revision` so callers' bindings depend on it
        if (!item || !item.desktop_id) return null;
        // byId wants the id without the `.desktop` suffix.
        const bare = item.desktop_id.replace(/\.desktop$/, "");
        return DesktopEntries.byId(bare) ?? DesktopEntries.heuristicLookup(bare);
    }

    function labelFor(item) {
        if (item.label) return item.label;
        const e = entryFor(item);
        if (e) return e.name;
        if (item.exec) return item.exec.split(/\s+/)[0].split("/").pop();
        // Entry not installed (or not loaded yet): "org.gnome.Nautilus" -> "Nautilus".
        return item.desktop_id.replace(/\.desktop$/, "").split(".").pop();
    }

    // Both of these return "" when nothing resolves, so delegates can draw
    // their own placeholder rather than Qt's broken-image checkerboard.
    function themeIcon(name) {
        if (!name) return "";
        if (name.startsWith("/")) return "file://" + name;
        return Quickshell.hasThemeIcon(name) ? Quickshell.iconPath(name) : "";
    }

    function iconSourceFor(item) {
        const entry = entryFor(item);
        for (const name of [item.icon, entry ? entry.icon : "", fallbackIcon, "application-default-icon", "exec"]) {
            const source = themeIcon(name);
            if (source) return source;
        }
        return "";
    }

    function commandFor(item) {
        const e = entryFor(item);
        if (e) {
            const cmd = (e.command && e.command.length) ? e.command.slice() : shellWrap(e.execString);
            return e.runInTerminal ? [terminal, "-e"].concat(cmd) : cmd;
        }
        if (item.exec) return shellWrap(item.exec);
        return null;
    }

    // sh -c gives us quoting, env prefixes and shell syntax for free, and
    // `exec` means no stray shell is left behind.
    function shellWrap(execString) {
        return ["/bin/sh", "-c", "exec " + stripFieldCodes(execString)];
    }

    function stripFieldCodes(s) {
        return (s || "").replace(/%[fFuUdDnNickvm]/g, "").trim();
    }

    function quote(s) {
        return "'" + s.replace(/'/g, "'\\''") + "'";
    }

    function launch(item) {
        const cmd = commandFor(item);
        if (!cmd) { console.warn("omarchy-desktop-icons: nothing to launch for", JSON.stringify(item)); return; }
        // execDetached: the app is not a child of the shell, so it survives a
        // shell restart or crash.
        Quickshell.execDetached(cmd);
    }

    // Middle-click launches on a fresh workspace (Hyprland only).
    //
    // Hyprland 0.5x with a Lua config rejects the classic `dispatch exec ...`
    // string syntax, and older/`.conf` setups do not understand the Lua form,
    // so try one and fall back to the other.
    function launchOnNewWorkspace(item) {
        const cmd = commandFor(item);
        if (!cmd) return;
        if (!Quickshell.env("HYPRLAND_INSTANCE_SIGNATURE")) { launch(item); return; }

        const line = "[workspace emptyn] " + cmd.map(quote).join(" ");
        Quickshell.execDetached(["/bin/sh", "-c",
            'hyprctl dispatch exec ' + quote(line) + ' 2>/dev/null | grep -q "^ok" '
            + '|| hyprctl dispatch ' + quote('hl.dsp.exec_cmd("' + line.replace(/"/g, '\\"') + '")')]);
    }

    // First run: seed one icon per category from whatever is actually
    // installed, so the desktop is not blank the first time she sees it.
    function seedItems() {
        const groups = [
            ["firefox", "chromium", "google-chrome", "brave-browser", "microsoft-edge"],
            ["com.mitchellh.ghostty", "Alacritty", "alacritty", "kitty", "foot"],
            ["org.gnome.Nautilus", "nautilus", "thunar", "nemo", "pcmanfm-qt"],
            ["code", "org.gnome.TextEditor", "gedit"]
        ];
        const out = [];
        for (const group of groups)
            for (const id of group)
                if (DesktopEntries.byId(id)) {
                    out.push({ label: "", desktop_id: id + ".desktop", exec: "", icon: "", cell: [0, out.length] });
                    break;
                }
        return out;
    }

    // --- files dropped on the grid -----------------------------------------

    // Parses just Name / Icon / Exec / Terminal out of a .desktop file so we
    // can accept drops from anywhere, not only the installed app dirs.
    function itemFromDesktopFile(path) {
        const id = path.split("/").pop();
        // If it is an installed entry, prefer the desktop_id so it tracks the
        // icon theme instead of freezing today's values.
        if (entryFor({ desktop_id: id })) return { label: "", desktop_id: id, exec: "", icon: "" };

        reader.path = path;
        const text = reader.text();
        reader.path = "";
        if (!text) return null;

        let inEntry = false;
        const field = {};
        for (const raw of text.split("\n")) {
            const line = raw.trim();
            if (line.startsWith("[")) { inEntry = line === "[Desktop Entry]"; continue; }
            if (!inEntry) continue;
            const eq = line.indexOf("=");
            if (eq < 1) continue;
            field[line.slice(0, eq).trim()] = line.slice(eq + 1).trim();
        }
        if (!field.Exec) return null;
        const exec = stripFieldCodes(field.Exec);
        return {
            label: field.Name || id.replace(/\.desktop$/, ""),
            desktop_id: "",
            exec: field.Terminal === "true" ? terminal + " -e " + exec : exec,
            icon: field.Icon || ""
        };
    }

    function itemFromFile(path) {
        if (path.endsWith(".desktop")) {
            const item = itemFromDesktopFile(path);
            if (item) return item;
        }
        // Anything else opens with its default handler, which is what dropping
        // a folder or a document on a Windows desktop does too.
        return {
            label: path.split("/").pop(),
            desktop_id: "",
            exec: "xdg-open " + quote(path),
            icon: path.endsWith("/") ? "folder" : "text-x-generic"
        };
    }

    FileView { id: reader; blockLoading: true; printErrors: false }

    Process {
        running: true
        command: ["/bin/sh", "-c",
            'for t in "$TERMINAL" ghostty alacritty kitty foot xterm; do '
            + '[ -n "$t" ] && command -v "$t" >/dev/null 2>&1 && { echo "$t"; exit 0; }; done; echo xterm']
        stdout: StdioCollector { onStreamFinished: root.terminal = text.trim() || "xterm" }
    }
}
