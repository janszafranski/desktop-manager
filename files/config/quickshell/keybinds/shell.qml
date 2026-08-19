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

                    // sort key: the base key first (so all variants of a key
                    // group together), then a modifier rank so the bare bind
                    // leads, followed by Alt, Shift, Ctrl (and their combos).
                    const sortKey = (b.key || "").toLowerCase();
                    let rank = 0;
                    if (m & 8) rank += 1;  // Alt
                    if (m & 1) rank += 2;  // Shift
                    if (m & 4) rank += 4;  // Ctrl

                    let action;
                    if (b.description && b.description.length > 0)
                        action = b.description;
                    else if (b.dispatcher === "exec")
                        action = b.arg;
                    else if (b.dispatcher === "global")
                        action = root.descs[b.arg] || b.arg;
                    else if (b.dispatcher && b.dispatcher.indexOf("lua") !== -1)
                        continue;  // opaque __lua bind with no description — nothing meaningful to show
                    else
                        action = b.dispatcher + (b.arg ? " " + b.arg : "");

                    const dedupKey = combo + "\t" + action;
                    if (seen[dedupKey])
                        continue;
                    seen[dedupKey] = true;
                    out.push({ combo: combo, action: action, sortKey: sortKey, rank: rank });
                }
                out.sort(function (a, b) {
                    const k = a.sortKey.localeCompare(b.sortKey);
                    return k !== 0 ? k : a.rank - b.rank;
                });
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
        // bar — on the Top layer the bar would eat the corner hover.
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
