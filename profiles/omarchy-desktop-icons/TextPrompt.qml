import QtQuick
import Quickshell
import Quickshell.Wayland

// One-line text prompt (used by Rename…). Overlay layer with exclusive
// keyboard focus for the same reason as AppPicker.
PanelWindow {
    id: root

    property bool open: false
    property string title: ""
    signal accepted(string value)

    visible: open
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "omarchy-desktop-icons-prompt"
    WlrLayershell.keyboardFocus: open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    anchors { top: true; left: true; right: true; bottom: true }

    function show(promptTitle, initial) {
        title = promptTitle;
        input.text = initial;
        open = true;
        input.forceActiveFocus();
        input.selectAll();
    }

    function close() { open = false; }

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
        width: 420
        height: 124
        radius: 14
        color: Theme.surface
        border.width: 1
        border.color: Theme.surfaceBorder

        MouseArea { anchors.fill: parent }

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            Text {
                text: root.title
                color: Theme.surfaceText
                font.pixelSize: 14
                font.bold: true
            }

            Rectangle {
                width: parent.width
                height: 38
                radius: 8
                color: Theme.hover

                TextInput {
                    id: input
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.surfaceText
                    font.pixelSize: 14
                    clip: true
                    selectByMouse: true
                    selectionColor: Theme.selectionBorder

                    Keys.onEscapePressed: root.close()
                    Keys.onReturnPressed: {
                        root.close();
                        root.accepted(text);
                    }
                }
            }

            Text {
                text: "Enter to save · Esc to cancel"
                color: Theme.surfaceTextDim
                font.pixelSize: 11
            }
        }
    }
}
