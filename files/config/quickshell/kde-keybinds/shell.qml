// KDE keybind widget (standalone QuickShell config, mirrors the Caelestia one).
// Run with:  qs -c kde-keybinds   (persistent: top-right hot corner + Meta+/ toggle)
// Reads KDE global shortcuts from ~/.config/kglobalshortcutsrc via list-shortcuts.sh.
// Runs under KWin/Plasma (Wayland) using wlr-layer-shell. Colours come from
// Caelestia's scheme.json if present, otherwise the dark fallbacks below.

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

ShellRoot {
    id: root

    readonly property string home: Quickshell.env("HOME")

    // ---------- theme (reuse Caelestia's scheme.json when available) ----------
    property var colours: ({})
    function col(name, fallback) {
        return "#" + (colours[name] !== undefined ? colours[name] : fallback);
    }

    readonly property string stateDir:
        (Quickshell.env("XDG_STATE_HOME") || (root.home + "/.local/state")) + "/caelestia"

    FileView {
        path: root.stateDir + "/scheme.json"
        printErrors: false
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

    // remembers the dragged position across opens (separate file from the hypr widget)
    FileView {
        id: posStore
        path: root.stateDir + "/kde-keybinds-widget.json"
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
    property bool pinned: false        // toggled open via Meta+/ (stays until toggled)
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
    // re-read shortcuts whenever the widget opens, so it reflects the live config
    onShownChanged: {
        if (shown)
            listProc.running = true;
    }

    // Meta+/ flips the pinned state: `qs -c kde-keybinds ipc call keybinds toggle`
    IpcHandler {
        target: "keybinds"
        function toggle(): void {
            root.pinned = !root.pinned;
        }
    }

    // ---------- data (built from list-shortcuts.sh -> "combo<TAB>action" lines) ----------
    property var rows: []

    Process {
        id: listProc
        running: true
        command: [root.home + "/.config/quickshell/kde-keybinds/list-shortcuts.sh"]
        stdout: StdioCollector {
            onStreamFinished: {
                const out = [];
                const lines = text.split("\n");
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    if (!line)
                        continue;
                    const t = line.indexOf("\t");
                    if (t < 0)
                        continue;
                    out.push({ combo: line.substring(0, t), action: line.substring(t + 1) });
                }
                root.rows = out;   // already sorted by key combo in the script
            }
        }
    }

    // ---------- window ----------
    PanelWindow {
        id: win
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        WlrLayershell.namespace: "kde-keybinds"
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
            x: parent.width - width - 16
            y: 16
            height: Math.min(parent.height - 32, 820, 56 + header.implicitHeight + 16 + list.contentHeight)
            radius: 28
            color: root.col("surface", "0b0b0d")
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
                        text: "KDE Keybindings"
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
                        color: root.col("surfaceContainer", "18181c")

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
