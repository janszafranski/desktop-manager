import QtQuick
import Quickshell

// The grid itself. Fills whatever surface it is put in (bottom layer on the
// desktop, or the SUPER+I overlay) and lays icons out in cells from the
// configured corner.
Item {
    id: root

    property int selectedIndex: -1

    signal iconMenuRequested(int index, point windowPos)
    signal emptyMenuRequested(point windowPos)

    readonly property int iconSize: Config.iconPixels
    readonly property int cellW: Config.cellWidth
    readonly property int cellH: Config.cellHeight
    readonly property var margins: Config.geometry.margins
    readonly property bool fromLeft: !String(Config.geometry.anchor).endsWith("right")
    readonly property bool fromTop: !String(Config.geometry.anchor).startsWith("bottom")

    readonly property int usableWidth: Math.max(cellW, width - margins.left - margins.right)
    readonly property int usableHeight: Math.max(cellH, height - margins.top - margins.bottom)
    readonly property int rows: Math.max(1, Math.floor(usableHeight / cellH))
    readonly property int columns: Config.geometry.columns > 0
        ? Config.geometry.columns
        : Math.max(1, Math.floor(usableWidth / cellW))

    function cellX(col) {
        return fromLeft ? margins.left + col * cellW : width - margins.right - (col + 1) * cellW;
    }

    function cellY(row) {
        return fromTop ? margins.top + row * cellH : height - margins.bottom - (row + 1) * cellH;
    }

    function colAt(x) {
        const c = fromLeft ? (x - margins.left) / cellW : (width - margins.right - x) / cellW - 1;
        return Math.max(0, Math.round(c));
    }

    function rowAt(y) {
        const r = fromTop ? (y - margins.top) / cellH : (height - margins.bottom - y) / cellH - 1;
        return Math.max(0, Math.min(rows - 1, Math.round(r)));
    }

    function clearSelection() { selectedIndex = -1; }

    // Drop a new item at the position it was released, falling back to the
    // first free cell if that one is taken.
    function placeAt(x, y, exceptIndex) {
        const col = colAt(x);
        const row = rowAt(y);
        if (Config.isCellFree(col, row, exceptIndex === undefined ? -1 : exceptIndex)) return [col, row];
        return Config.firstFreeCell(rows, exceptIndex === undefined ? -1 : exceptIndex);
    }

    // Drag a .desktop file (or anything else) in from the file manager.
    DropArea {
        anchors.fill: parent
        z: -1 // nothing else here accepts drops; keep it clear of the mouse items

        onDropped: drop => {
            if (!drop.hasUrls) { drop.accepted = false; return; }
            let x = drop.x, y = drop.y;
            for (const url of drop.urls) {
                const path = decodeURIComponent(String(url).replace(/^file:\/\//, ""));
                const item = Apps.itemFromFile(path);
                if (!item) continue;
                item.cell = root.placeAt(x + root.cellW / 2, y + root.cellH / 2, -1);
                Config.addItem(item);
                y += root.cellH; // stack multiple drops down the column
            }
            drop.accepted = true;
        }
    }

    // Right-click / click-away on bare wallpaper. Sits below the icons.
    MouseArea {
        anchors.fill: parent
        // hoverEnabled is load-bearing: without it this MouseArea never
        // becomes the hovered target on a layer-shell surface and button
        // presses on bare wallpaper are not delivered to it at all.
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: event => {
            root.clearSelection();
            if (event.button === Qt.RightButton)
                root.emptyMenuRequested(mapToItem(null, event.x, event.y));
        }
    }

    Repeater {
        model: Config.items

        DesktopIcon {
            id: icon

            required property var modelData
            required property int index

            item: modelData
            iconSize: root.iconSize
            width: root.cellW
            height: root.cellH
            selected: root.selectedIndex === index
            dragging: dragX !== 0 || dragY !== 0
            z: dragging ? 10 : 1

            property real dragX: 0
            property real dragY: 0

            x: root.cellX(modelData.cell[0]) + dragX
            y: root.cellY(modelData.cell[1]) + dragY

            onSelectRequested: root.selectedIndex = index
            onActivated: Apps.launch(modelData)
            onActivatedNewWorkspace: Apps.launchOnNewWorkspace(modelData)
            onContextRequested: pos => root.iconMenuRequested(index, pos)
            onDragMoved: (dx, dy) => { dragX = dx; dragY = dy; }
            onDragFinished: {
                const cell = root.placeAt(x + root.cellW / 2, y + root.cellH / 2, index);
                dragX = 0;
                dragY = 0;
                Config.updateItem(index, { cell: cell });
            }
        }
    }

}
