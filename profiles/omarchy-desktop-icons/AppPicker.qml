import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Widgets

// Searchable picker over the installed .desktop entries.
//
// Its own overlay-layer surface with exclusive keyboard focus, so typing works
// regardless of how the compositor treats keyboard focus on the bottom layer.
PanelWindow {
    id: root

    property bool open: false
    signal picked(string desktopId)

    visible: open
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "omarchy-desktop-icons-picker"
    WlrLayershell.keyboardFocus: open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    anchors { top: true; left: true; right: true; bottom: true }

    readonly property var allEntries: (DesktopEntries.applications.values ?? [])
        .filter(e => e && !e.noDisplay)
        .sort((a, b) => a.name.localeCompare(b.name))

    readonly property var matches: {
        const q = search.text.trim().toLowerCase();
        if (!q) return allEntries;
        return allEntries.filter(e =>
            e.name.toLowerCase().includes(q)
            || (e.genericName ?? "").toLowerCase().includes(q)
            || (e.id ?? "").toLowerCase().includes(q));
    }

    function show() {
        search.text = "";
        list.currentIndex = 0;
        open = true;
        search.forceActiveFocus();
    }

    function close() { open = false; }

    function accept() {
        const e = matches[list.currentIndex];
        if (!e) return;
        close();
        picked(e.id.endsWith(".desktop") ? e.id : e.id + ".desktop");
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.close()
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.35)
        z: -1
    }

    Rectangle {
        anchors.centerIn: parent
        width: 520
        height: 480
        radius: 14
        color: Theme.surface
        border.width: 1
        border.color: Theme.surfaceBorder

        MouseArea { anchors.fill: parent } // don't fall through to the backdrop

        Column {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            Rectangle {
                width: parent.width
                height: 38
                radius: 8
                color: Theme.hover

                TextInput {
                    id: search
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.surfaceText
                    font.pixelSize: 14
                    clip: true
                    selectByMouse: true
                    selectionColor: Theme.selectionBorder

                    onTextChanged: list.currentIndex = 0

                    Keys.onEscapePressed: root.close()
                    Keys.onReturnPressed: root.accept()
                    Keys.onDownPressed: list.incrementCurrentIndex()
                    Keys.onUpPressed: list.decrementCurrentIndex()

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: search.text === ""
                        text: "Search installed apps…"
                        color: Theme.surfaceTextDim
                        font.pixelSize: 14
                    }
                }
            }

            ListView {
                id: list
                width: parent.width
                height: parent.height - 48
                clip: true
                // Only built while the picker is up; otherwise every installed
                // app's icon would be loaded at startup for nothing.
                model: root.open ? root.matches : []
                currentIndex: 0
                highlightMoveDuration: 80

                delegate: Item {
                    required property var modelData
                    required property int index

                    width: list.width
                    height: 44

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 2
                        radius: 8
                        color: list.currentIndex === index ? Theme.selection
                            : (hover.containsMouse ? Theme.hover : "transparent")
                    }

                    Item {
                        id: img
                        anchors.verticalCenter: parent.verticalCenter
                        x: 10
                        width: 28
                        height: 28

                        readonly property string resolved:
                            Apps.themeIcon(modelData.icon) || Apps.themeIcon(Apps.fallbackIcon)

                        IconImage {
                            anchors.fill: parent
                            asynchronous: true
                            source: img.resolved
                            visible: !tile.visible
                        }

                        Rectangle {
                            id: tile
                            anchors.fill: parent
                            visible: img.resolved === ""
                            radius: 6
                            color: Theme.selectionBorder

                            Text {
                                anchors.centerIn: parent
                                text: modelData.name.charAt(0).toUpperCase()
                                color: "white"
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        x: img.x + img.width + 12
                        width: parent.width - x - 10
                        elide: Text.ElideRight
                        color: Theme.surfaceText
                        font.pixelSize: 13
                        text: modelData.name
                            + (modelData.genericName ? "  —  " + modelData.genericName : "")
                    }

                    MouseArea {
                        id: hover
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: { list.currentIndex = index; root.accept(); }
                    }
                }
            }
        }
    }
}
