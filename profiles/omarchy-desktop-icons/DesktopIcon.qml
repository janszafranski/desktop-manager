import QtQuick
import Quickshell
import Quickshell.Widgets

// One icon: image plus label, no opaque background. The label gets a soft
// offset shadow so it stays readable on light and dark wallpapers alike.
Item {
    id: root

    required property var item
    property bool selected: false
    property bool dragging: false
    property int iconSize: 48

    signal activated()
    signal activatedNewWorkspace()
    signal selectRequested()
    signal contextRequested(point windowPos)
    signal dragMoved(real dx, real dy)
    signal dragFinished()

    readonly property string label: Apps.labelFor(item)
    readonly property string iconSource: Apps.iconSourceFor(item)

    Rectangle {
        anchors.fill: parent
        anchors.margins: 2
        radius: 8
        color: root.selected ? Theme.selection : (mouse.containsMouse ? Theme.hover : "transparent")
        border.width: root.selected ? 1 : 0
        border.color: Theme.selectionBorder
        Behavior on color { ColorAnimation { duration: 90 } }
    }

    Column {
        anchors.centerIn: parent
        spacing: 4

        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            implicitWidth: root.iconSize
            implicitHeight: root.iconSize
            opacity: root.dragging ? 0.55 : 1

            IconImage {
                id: image
                anchors.fill: parent
                source: root.iconSource
                asynchronous: true
                visible: !placeholder.visible
            }

            // Nothing in the icon theme matched — draw an initial rather than
            // Qt's broken-image checkerboard.
            Rectangle {
                id: placeholder
                anchors.fill: parent
                visible: root.iconSource === "" || image.status === Image.Error
                radius: width * 0.22
                color: Theme.selectionBorder

                Text {
                    anchors.centerIn: parent
                    text: root.label.charAt(0).toUpperCase()
                    color: "white"
                    font.pixelSize: Math.round(parent.width * 0.55)
                    font.bold: true
                }
            }
        }

        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: root.width - 8
            height: labelText.height
            visible: Config.behaviour.label_position !== "none"

            Text {
                x: 1
                y: 1
                width: parent.width
                text: labelText.text
                font: labelText.font
                color: Theme.labelShadow
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }

            Text {
                id: labelText
                width: parent.width
                text: root.label
                color: Theme.labelColor
                font.pixelSize: Math.max(10, Math.round(root.iconSize / 4))
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

        property real pressX: 0
        property real pressY: 0
        property bool moved: false

        onPressed: event => {
            pressX = event.x;
            pressY = event.y;
            moved = false;
            if (event.button === Qt.LeftButton) root.selectRequested();
        }

        onPositionChanged: event => {
            if (!(pressedButtons & Qt.LeftButton)) return;
            const dx = event.x - pressX;
            const dy = event.y - pressY;
            if (!moved && Math.hypot(dx, dy) < 6) return;
            moved = true;
            root.dragMoved(dx, dy);
        }

        onReleased: event => {
            if (moved) root.dragFinished();
        }

        onClicked: event => {
            if (moved) return;
            if (event.button === Qt.RightButton) {
                root.selectRequested();
                root.contextRequested(root.mapToItem(null, event.x, event.y));
            } else if (event.button === Qt.MiddleButton) {
                root.activatedNewWorkspace();
            } else if (Config.behaviour.activate === "single") {
                root.activated();
            }
        }

        onDoubleClicked: event => {
            if (event.button === Qt.LeftButton && Config.behaviour.activate !== "single") root.activated();
        }
    }
}
