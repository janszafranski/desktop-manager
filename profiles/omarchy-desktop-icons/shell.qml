import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// omarchy-desktop-icons — double-clickable app icons on the Hyprland desktop.
//
// Two surfaces over one grid:
//   desktop  wlr-layer-shell `bottom`  - above the wallpaper, below every
//                                        window. Always there.
//   overlay  wlr-layer-shell `top`     - SUPER+I, for when windows cover the
//                                        desktop (i.e. most of the time).
ShellRoot {
    id: shell

    // One grid, on one screen. Showing the same cells on every monitor would
    // just be confusing; `geometry.screen` picks a specific output by name.
    readonly property var targetScreen: {
        const want = Config.geometry.screen;
        if (want) {
            const match = Quickshell.screens.find(s => s.name === want);
            if (match) return match;
        }
        return Quickshell.screens[0] ?? null;
    }

    property int pendingIndex: -1
    property var pendingCell: null

    // --- menu contents -----------------------------------------------------

    function globalEntries(grid) {
        const size = Config.behaviour.icon_size;
        return [
            // pendingCell is set by whoever opened the menu: the cell that was
            // right-clicked on empty space, or null from an icon's menu.
            { label: "Add app…", action: () => picker.show() },
            { label: "Icon size", submenu: [
                { label: "Small", checked: size === "small", action: () => Config.setIconSize("small") },
                { label: "Medium", checked: size === "medium", action: () => Config.setIconSize("medium") },
                { label: "Large", checked: size === "large", action: () => Config.setIconSize("large") }
            ] },
            { label: "Auto-arrange", action: () => Config.autoArrange(grid.rows) },
            { separator: true },
            { label: "Reload config", action: () => { Config.reload(); Theme.reload(); } },
            { label: "Settings…", action: () => settingsDialog.show() },
            { separator: true },
            { label: "Quit", action: () => Qt.quit() }
        ];
    }

    function iconEntries(grid, index) {
        const item = Config.items[index];
        const name = Apps.labelFor(item);
        return [
            { label: "Open", action: () => Apps.launch(item) },
            { label: "Open on new workspace", action: () => Apps.launchOnNewWorkspace(item) },
            { label: "Rename…", action: () => {
                shell.pendingIndex = index;
                prompt.show("Rename “" + name + "”", name);
            } },
            { label: "Remove “" + name + "”", action: () => {
                Config.removeItem(index);
                grid.clearSelection();
            } },
            { separator: true }
        ].concat(globalEntries(grid));
    }

    function addApp(desktopId, grid) {
        const cell = pendingCell ?? Config.firstFreeCell(grid ? grid.rows : 8, -1);
        Config.addItem({ label: "", desktop_id: desktopId, exec: "", icon: "", cell: cell });
        pendingCell = null;
    }

    // $EDITOR in a terminal if there is one, otherwise whatever handles JSON.
    // No longer in the right-click menu — it is the footer escape hatch in the
    // Settings dialog, and `omarchy-desktop-icons edit` from a shell.
    function editConfig() {
        const editor = Quickshell.env("VISUAL") || Quickshell.env("EDITOR");
        if (editor)
            Quickshell.execDetached([Apps.terminal, "-e", "/bin/sh", "-c",
                editor + " " + Apps.quote(Config.path)]);
        else
            Quickshell.execDetached(["xdg-open", Config.path]);
    }

    // --- desktop surface (bottom layer) ------------------------------------

    PanelWindow {
        id: desktop

        screen: shell.targetScreen
        visible: shell.targetScreen !== null
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        anchors { top: true; left: true; right: true; bottom: true }

        WlrLayershell.layer: WlrLayer.Bottom
        WlrLayershell.namespace: "omarchy-desktop-icons"
        // Never takes keyboard focus; the context menu has its own surface
        // for that, because Hyprland does not focus `bottom` layer surfaces.
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

        IconGrid {
            id: desktopGrid
            anchors.fill: parent
            onIconMenuRequested: (index, pos) => {
                shell.pendingCell = null;
                menu.popup(pos, shell.iconEntries(desktopGrid, index));
            }
            onEmptyMenuRequested: pos => {
                shell.pendingCell = desktopGrid.placeAt(pos.x, pos.y, -1);
                menu.popup(pos, shell.globalEntries(desktopGrid));
            }
        }
    }

    // --- overlay surface (top layer, SUPER+I) ------------------------------

    PanelWindow {
        id: overlay

        property bool open: false

        screen: shell.targetScreen
        visible: open && shell.targetScreen !== null
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        anchors { top: true; left: true; right: true; bottom: true }

        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.namespace: "omarchy-desktop-icons-overlay"
        WlrLayershell.keyboardFocus: open ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.None

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, 0.45)

            MouseArea {
                anchors.fill: parent
                onClicked: overlay.open = false
            }
        }

        IconGrid {
            id: overlayGrid
            anchors.fill: parent
            focus: overlay.open
            Keys.onEscapePressed: overlay.open = false
            onIconMenuRequested: (index, pos) => {
                shell.pendingCell = null;
                menu.popup(pos, shell.iconEntries(overlayGrid, index));
            }
            onEmptyMenuRequested: pos => {
                shell.pendingCell = overlayGrid.placeAt(pos.x, pos.y, -1);
                menu.popup(pos, shell.globalEntries(overlayGrid));
            }
        }
    }

    // --- menu and dialogs --------------------------------------------------

    ContextMenu {
        id: menu
        screen: shell.targetScreen
    }

    AppPicker {
        id: picker
        screen: shell.targetScreen
        onPicked: desktopId => shell.addApp(desktopId, overlay.open ? overlayGrid : desktopGrid)
    }

    SettingsDialog {
        id: settingsDialog
        screen: shell.targetScreen
        onEditRequested: shell.editConfig()
    }

    TextPrompt {
        id: prompt
        screen: shell.targetScreen
        onAccepted: value => {
            if (shell.pendingIndex >= 0 && value.trim() !== "")
                Config.updateItem(shell.pendingIndex, { label: value.trim() });
            shell.pendingIndex = -1;
        }
    }

    // --- IPC ---------------------------------------------------------------
    //
    // `omarchy-desktop-icons toggle` calls into the running instance over
    // Quickshell's socket in $XDG_RUNTIME_DIR. Nothing is ever relaunched.
    IpcHandler {
        target: "desktop"

        // Named open/close rather than show/hide: `qs ipc call desktop show`
        // collides with the `qs ipc show` subcommand and prints the handler
        // listing instead of calling anything.
        function toggle(): void { overlay.open = !overlay.open; }
        function open(): void { overlay.open = true; }
        function close(): void { overlay.open = false; }
        function reload(): void { Config.reload(); Theme.reload(); }
        function settings(): void { settingsDialog.show(); }
    }
}
