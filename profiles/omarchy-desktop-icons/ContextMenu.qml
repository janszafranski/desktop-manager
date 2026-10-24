import QtQuick
import Quickshell
import Quickshell.Wayland

// A context menu on its own full-screen overlay surface.
//
// It is not drawn inside the desktop surface because Hyprland never gives
// keyboard focus to a `bottom` layer surface, so Escape and the arrow keys
// would be dead there. On the overlay layer with exclusive focus it behaves
// like a real menu grab: keys work, and any click outside dismisses it.
//
// `entries` is an array of:
//   { label, action }                         - a normal row
//   { label, submenu: [...] }                 - a flyout
//   { label, action, checked: bool }          - a radio/check row
//   { separator: true }
PanelWindow {
    id: root

    property bool open: false

    visible: open
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "omarchy-desktop-icons-menu"
    WlrLayershell.keyboardFocus: open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    anchors { top: true; left: true; right: true; bottom: true }

    property var entries: []
    property int current: -1
    property int openSubmenu: -1
    property real requestedX: 0
    property real requestedY: 0

    function popup(windowPos, newEntries) {
        entries = newEntries;
        current = -1;
        openSubmenu = -1;
        requestedX = windowPos.x;
        requestedY = windowPos.y;
        open = true;
        keys.forceActiveFocus();
    }

    function close() {
        open = false;
        openSubmenu = -1;
    }

    function trigger(entry) {
        if (!entry || entry.separator || entry.submenu) return;
        close();
        if (entry.action) entry.action();
    }

    // Keyboard navigation plus click-away. The MouseArea covers the whole
    // screen, so this behaves as a grab: any click outside the panel closes it.
    Item {
        id: keys
        anchors.fill: parent
        focus: root.open

        Keys.onEscapePressed: root.close()
        Keys.onUpPressed: root.current = root.prevSelectable(root.current)
        Keys.onDownPressed: root.current = root.nextSelectable(root.current)
        Keys.onReturnPressed: root.trigger(root.entries[root.current])
        Keys.onRightPressed: if (root.entries[root.current] && root.entries[root.current].submenu)
            root.openSubmenu = root.current
        Keys.onLeftPressed: root.openSubmenu = -1

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            onPressed: root.close()
        }
    }

    function nextSelectable(from) {
        for (let i = from + 1; i < entries.length; i++) if (!entries[i].separator) return i;
        for (let i = 0; i <= from; i++) if (!entries[i].separator) return i;
        return from;
    }

    function prevSelectable(from) {
        for (let i = from - 1; i >= 0; i--) if (!entries[i].separator) return i;
        for (let i = entries.length - 1; i >= from && i >= 0; i--) if (!entries[i].separator) return i;
        return from;
    }

    Rectangle {
        id: panel
        width: 230
        height: column.implicitHeight + 10
        // Clamped as a binding so it re-settles once the rows have laid out.
        x: Math.max(4, Math.min(root.requestedX, root.width - width - 4))
        y: Math.max(4, Math.min(root.requestedY, root.height - height - 4))
        radius: 10
        color: Theme.surface
        border.width: 1
        border.color: Theme.surfaceBorder

        Column {
            id: column
            y: 5
            width: parent.width

            Repeater {
                model: root.entries

                Item {
                    id: row

                    required property var modelData
                    required property int index

                    width: column.width
                    height: modelData.separator ? 7 : 28

                    Rectangle {
                        visible: row.modelData.separator === true
                        anchors.centerIn: parent
                        width: parent.width - 20
                        height: 1
                        color: Theme.surfaceBorder
                    }

                    Rectangle {
                        visible: !row.modelData.separator
                        anchors.fill: parent
                        anchors.margins: 3
                        anchors.topMargin: 0
                        anchors.bottomMargin: 0
                        radius: 6
                        color: root.current === row.index ? Theme.hover : "transparent"
                    }

                    Text {
                        visible: !row.modelData.separator
                        anchors.verticalCenter: parent.verticalCenter
                        x: 14
                        width: parent.width - 34
                        elide: Text.ElideMiddle
                        text: (row.modelData.checked ? "● " : "") + (row.modelData.label ?? "")
                        color: Theme.surfaceText
                        font.pixelSize: 13
                    }

                    Text {
                        visible: row.modelData.submenu !== undefined
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        text: "›"
                        color: Theme.surfaceTextDim
                        font.pixelSize: 15
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: !row.modelData.separator
                        onEntered: {
                            root.current = row.index;
                            root.openSubmenu = row.modelData.submenu !== undefined ? row.index : -1;
                        }
                        onClicked: {
                            if (row.modelData.submenu !== undefined) root.openSubmenu = row.index;
                            else root.trigger(row.modelData);
                        }
                    }

                    // Flyout for submenu rows.
                    Rectangle {
                        visible: root.openSubmenu === row.index
                        x: panel.width - 6
                        y: -4
                        width: 160
                        height: subColumn.implicitHeight + 10
                        radius: 10
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.surfaceBorder

                        Column {
                            id: subColumn
                            y: 5
                            width: parent.width

                            Repeater {
                                model: row.modelData.submenu ?? []

                                Item {
                                    id: subRow
                                    required property var modelData
                                    width: subColumn.width
                                    height: 28

                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.margins: 3
                                        anchors.topMargin: 0
                                        anchors.bottomMargin: 0
                                        radius: 6
                                        color: subMouse.containsMouse ? Theme.hover : "transparent"
                                    }

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        x: 14
                                        text: (subRow.modelData.checked ? "● " : "") + subRow.modelData.label
                                        color: Theme.surfaceText
                                        font.pixelSize: 13
                                    }

                                    MouseArea {
                                        id: subMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: root.trigger(subRow.modelData)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
