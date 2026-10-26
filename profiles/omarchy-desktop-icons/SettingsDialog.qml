import QtQuick
import Quickshell
import Quickshell.Wayland

// The Settings… dialog: every knob in config.json except the icons themselves,
// as controls rather than text. Same surface pattern as AppPicker/TextPrompt —
// its own overlay-layer window with exclusive keyboard focus, because Hyprland
// never focuses the `bottom` layer the grid lives on.
//
// Everything is live: a control writes straight through Config and saves, so
// the grid behind the dialog moves while you drag. There is no OK/Cancel.
// Sliders debounce their writes, otherwise dragging one would do an atomic
// file write per pixel.
//
// The controls are hand-rolled rather than QtQuick.Controls, to match the
// hand-rolled menus and text inputs elsewhere in the app and to keep the
// import list at QtQuick + Quickshell.
PanelWindow {
    id: root

    property bool open: false
    signal editRequested()

    visible: open
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "omarchy-desktop-icons-settings"
    WlrLayershell.keyboardFocus: open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    anchors { top: true; left: true; right: true; bottom: true }

    readonly property var margins: Config.geometry.margins
    readonly property bool uniformMargins: margins.top === margins.left
        && margins.left === margins.right && margins.right === margins.bottom

    property bool perSide: false

    readonly property var cornerOptions: [
        { label: "Top left", value: "top-left" },
        { label: "Top right", value: "top-right" },
        { label: "Bottom left", value: "bottom-left" },
        { label: "Bottom right", value: "bottom-right" }
    ]

    readonly property var screenOptions: [{ label: "Automatic", value: "" }]
        .concat((Quickshell.screens ?? []).map(s => ({ label: s.name, value: s.name })))

    function show() {
        // Land on the advanced view if the four sides already differ, so the
        // single slider never silently misrepresents them.
        perSide = !uniformMargins;
        open = true;
        keys.forceActiveFocus();
    }

    function close() {
        monitor.expanded = false;
        open = false;
    }

    // --- controls ----------------------------------------------------------

    // A row of pills, exactly one of them lit. `options` is [{ label, value }].
    component Segmented: FocusScope {
        id: seg

        property var options: []
        property var value: ""
        signal picked(var v)

        implicitWidth: pills.implicitWidth + 6
        implicitHeight: 30
        activeFocusOnTab: true

        function step(d) {
            const n = seg.options.length;
            if (n === 0) return;
            const at = seg.options.findIndex(o => o.value === seg.value);
            seg.picked(seg.options[at < 0 ? 0 : (at + d + n) % n].value);
        }

        Keys.onLeftPressed: seg.step(-1)
        Keys.onRightPressed: seg.step(1)
        Keys.onUpPressed: seg.step(-1)
        Keys.onDownPressed: seg.step(1)

        Rectangle {
            width: pills.implicitWidth + 6
            height: seg.height
            radius: 9
            color: Theme.hover
            border.width: seg.activeFocus ? 1 : 0
            border.color: Theme.selectionBorder
        }

        Row {
            id: pills
            x: 3
            y: 3
            spacing: 3

            Repeater {
                model: seg.options

                Rectangle {
                    required property var modelData

                    height: seg.height - 6
                    width: Math.max(56, pillText.implicitWidth + 18)
                    radius: 6
                    color: seg.value === modelData.value ? Theme.selection
                        : (pillMouse.containsMouse ? Theme.hover : "transparent")
                    border.width: seg.value === modelData.value ? 1 : 0
                    border.color: Theme.selectionBorder

                    Text {
                        id: pillText
                        anchors.centerIn: parent
                        text: modelData.label
                        color: Theme.surfaceText
                        font.pixelSize: 12
                    }

                    MouseArea {
                        id: pillMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            seg.forceActiveFocus();
                            seg.picked(modelData.value);
                        }
                    }
                }
            }
        }
    }

    // Hand-rolled slider. `value` stays bound to the config, so an edit made in
    // an editor moves the handle; while the handle is actually held we show the
    // dragged value instead and commit it on a trailing timer.
    component MiniSlider: FocusScope {
        id: sl

        property real from: 0
        property real to: 100
        property real stepSize: 1
        property real value: 0
        signal commit(real v)

        property bool held: false
        property real heldValue: 0
        readonly property real shown: held ? heldValue : value

        readonly property real span: Math.max(1, to - from)
        readonly property real fraction: Math.max(0, Math.min(1, (shown - from) / span))

        implicitHeight: 26
        activeFocusOnTab: true

        function quantize(v) {
            const q = from + Math.round((v - from) / stepSize) * stepSize;
            return Math.max(from, Math.min(to, q));
        }

        function dragTo(px) {
            heldValue = quantize(from + (px / Math.max(1, sl.width - 16)) * span);
            trail.restart();
        }

        // Arrow keys step once, which is already slow enough not to need the
        // timer — and going through `value` keeps them exact.
        function nudge(d) {
            trail.stop();
            held = false;
            sl.commit(quantize(sl.value + d * stepSize));
        }

        Keys.onLeftPressed: sl.nudge(-1)
        Keys.onRightPressed: sl.nudge(1)
        Keys.onDownPressed: sl.nudge(-1)
        Keys.onUpPressed: sl.nudge(1)

        Timer {
            id: trail
            interval: 200
            onTriggered: if (sl.held) sl.commit(sl.heldValue)
        }

        Rectangle {
            id: groove
            anchors.verticalCenter: parent.verticalCenter
            width: sl.width
            height: 6
            radius: 3
            color: Theme.hover

            Rectangle {
                width: 8 + Math.round((groove.width - 16) * sl.fraction)
                height: parent.height
                radius: 3
                color: Theme.selectionBorder
            }
        }

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            x: Math.round((sl.width - width) * sl.fraction)
            width: 16
            height: 16
            radius: 8
            color: Theme.accent
            border.width: sl.activeFocus ? 2 : 1
            border.color: sl.activeFocus ? Theme.surfaceText : Theme.surfaceBorder
        }

        MouseArea {
            anchors.fill: parent
            onPressed: event => {
                sl.forceActiveFocus();
                sl.held = true;
                sl.dragTo(event.x - 8);
            }
            onPositionChanged: event => { if (sl.held) sl.dragTo(event.x - 8); }
            // Flush on release so the handle never snaps back to the old value
            // while the trailing timer is still pending.
            onReleased: {
                trail.stop();
                if (sl.held) sl.commit(sl.heldValue);
                sl.held = false;
            }
        }
    }

    // Collapsed list of choices. Used for the monitor, which is the only
    // setting whose options are not known until runtime.
    component Dropdown: FocusScope {
        id: dd

        property var options: []
        property var value: ""
        property bool expanded: false
        signal picked(var v)

        implicitWidth: 200
        implicitHeight: 30
        activeFocusOnTab: true
        z: expanded ? 10 : 0

        readonly property string currentLabel: {
            const o = dd.options.find(x => x.value === dd.value);
            return o ? o.label : String(dd.value);
        }

        function step(d) {
            const n = dd.options.length;
            if (n === 0) return;
            const at = dd.options.findIndex(o => o.value === dd.value);
            dd.picked(dd.options[at < 0 ? 0 : (at + d + n) % n].value);
        }

        Keys.onLeftPressed: dd.step(-1)
        Keys.onRightPressed: dd.step(1)
        Keys.onUpPressed: dd.step(-1)
        Keys.onDownPressed: dd.step(1)
        Keys.onReturnPressed: dd.expanded = !dd.expanded
        // Only swallow Escape if it has something to do here; otherwise let it
        // bubble up and close the dialog.
        Keys.onEscapePressed: event => {
            event.accepted = dd.expanded;
            dd.expanded = false;
        }

        Rectangle {
            id: field
            width: dd.width
            height: dd.height
            radius: 8
            color: Theme.hover
            border.width: dd.activeFocus ? 1 : 0
            border.color: Theme.selectionBorder

            Text {
                x: 10
                width: parent.width - 32
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                text: dd.currentLabel
                color: Theme.surfaceText
                font.pixelSize: 12
            }

            Text {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: "▾"
                color: Theme.surfaceTextDim
                font.pixelSize: 11
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    dd.forceActiveFocus();
                    dd.expanded = !dd.expanded;
                }
            }
        }

        Rectangle {
            visible: dd.expanded
            y: field.height + 4
            width: dd.width
            height: ddList.implicitHeight + 8
            radius: 8
            color: Theme.surface
            border.width: 1
            border.color: Theme.surfaceBorder

            Column {
                id: ddList
                y: 4
                width: parent.width

                Repeater {
                    model: dd.options

                    Rectangle {
                        required property var modelData

                        width: ddList.width
                        height: 26
                        color: ddHover.containsMouse ? Theme.hover : "transparent"

                        Text {
                            x: 10
                            width: parent.width - 20
                            anchors.verticalCenter: parent.verticalCenter
                            elide: Text.ElideRight
                            text: (modelData.value === dd.value ? "● " : "") + modelData.label
                            color: Theme.surfaceText
                            font.pixelSize: 12
                        }

                        MouseArea {
                            id: ddHover
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                dd.expanded = false;
                                dd.picked(modelData.value);
                            }
                        }
                    }
                }
            }
        }
    }

    component PushButton: FocusScope {
        id: btn

        property string label: ""
        property bool quiet: false
        signal clicked()

        implicitWidth: btnText.implicitWidth + (quiet ? 16 : 34)
        implicitHeight: quiet ? 26 : 30
        activeFocusOnTab: true

        Keys.onReturnPressed: btn.clicked()
        Keys.onSpacePressed: btn.clicked()

        Rectangle {
            anchors.fill: parent
            radius: 8
            color: btn.quiet
                ? (btnMouse.containsMouse ? Theme.hover : "transparent")
                : (btnMouse.containsMouse ? Theme.selection : Theme.hover)
            border.width: btn.activeFocus ? 1 : 0
            border.color: Theme.selectionBorder
        }

        Text {
            id: btnText
            anchors.centerIn: parent
            text: btn.label
            color: btn.quiet ? Theme.surfaceTextDim : Theme.surfaceText
            font.pixelSize: btn.quiet ? 11 : 12
        }

        MouseArea {
            id: btnMouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: {
                btn.forceActiveFocus();
                btn.clicked();
            }
        }
    }

    // Label on the left, control on the right.
    component SettingRow: Item {
        id: srow

        property string label: ""
        property real rowHeight: 36
        default property alias content: holder.data

        width: parent ? parent.width : 0
        height: rowHeight

        Text {
            x: 0
            width: 104
            anchors.verticalCenter: parent.verticalCenter
            text: srow.label
            color: Theme.surfaceText
            font.pixelSize: 13
            elide: Text.ElideRight
        }

        Item {
            id: holder
            x: 112
            width: Math.max(0, srow.width - 112)
            height: srow.height
        }
    }

    component SectionHeader: Item {
        id: header

        property string label: ""
        width: parent ? parent.width : 0
        height: 30

        Text {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 3
            text: header.label
            color: Theme.surfaceTextDim
            font.pixelSize: 11
            font.bold: true
        }
    }

    // --- surface -----------------------------------------------------------

    MouseArea {
        anchors.fill: parent
        onClicked: root.close()
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.35)
        z: -1
    }

    FocusScope {
        id: keys
        anchors.fill: parent
        focus: root.open

        Keys.onEscapePressed: root.close()

        Rectangle {
            anchors.centerIn: parent
            width: 520
            height: body.implicitHeight + 32
            radius: 14
            color: Theme.surface
            border.width: 1
            border.color: Theme.surfaceBorder

            // Swallow clicks so they do not fall through to the click-away
            // backdrop, and use them to dismiss an open dropdown.
            MouseArea {
                anchors.fill: parent
                onClicked: monitor.expanded = false
            }

            Column {
                id: body
                x: 16
                y: 16
                width: parent.width - 32
                spacing: 2

                Text {
                    text: "Desktop icons"
                    color: Theme.surfaceText
                    font.pixelSize: 15
                    font.bold: true
                    bottomPadding: 6
                }

                SectionHeader { label: "POSITION" }

                SettingRow {
                    label: "Corner"
                    Segmented {
                        anchors.verticalCenter: parent.verticalCenter
                        options: root.cornerOptions
                        value: Config.geometry.anchor
                        onPicked: v => Config.setGeometry({ anchor: v })
                    }
                }

                SettingRow {
                    label: "Edge spacing"

                    MiniSlider {
                        id: spacing
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 56
                        from: 0
                        to: 120
                        value: root.margins.top
                        onCommit: v => {
                            const n = Math.round(v);
                            Config.setMargins({ top: n, left: n, right: n, bottom: n });
                        }
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        width: 50
                        horizontalAlignment: Text.AlignRight
                        text: root.uniformMargins || spacing.held
                            ? Math.round(spacing.shown) + " px"
                            : "Mixed"
                        color: Theme.surfaceTextDim
                        font.pixelSize: 12
                    }
                }

                // Disclosure. The single slider above is the normie path; this
                // is for the "my bar covers the first column" case.
                Item {
                    width: parent.width
                    height: 26

                    Text {
                        id: discText
                        x: 112
                        anchors.verticalCenter: parent.verticalCenter
                        text: (root.perSide ? "▾  " : "▸  ") + "Different spacing per side"
                        color: Theme.surfaceTextDim
                        font.pixelSize: 11
                    }

                    MouseArea {
                        x: 112
                        width: discText.implicitWidth + 8
                        height: parent.height
                        onClicked: root.perSide = !root.perSide
                    }
                }

                Repeater {
                    model: root.perSide
                        ? [{ key: "top", label: "Top" }, { key: "left", label: "Left" },
                           { key: "right", label: "Right" }, { key: "bottom", label: "Bottom" }]
                        : []

                    SettingRow {
                        id: sideRow
                        required property var modelData

                        label: "    " + modelData.label
                        rowHeight: 32

                        MiniSlider {
                            id: sideSlider
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width - 56
                            from: 0
                            // Wider than the single slider on purpose: a bar
                            // that reserves 500px down one side is a real
                            // layout, and clamping to 120 would make it
                            // unreachable from here.
                            to: 600
                            value: root.margins[sideRow.modelData.key]
                            onCommit: v => {
                                const change = {};
                                change[sideRow.modelData.key] = Math.round(v);
                                Config.setMargins(change);
                            }
                        }

                        Text {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: 50
                            horizontalAlignment: Text.AlignRight
                            text: Math.round(sideSlider.shown) + " px"
                            color: Theme.surfaceTextDim
                            font.pixelSize: 12
                        }
                    }
                }

                SettingRow {
                    label: "Columns"

                    MiniSlider {
                        id: columns
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 56
                        from: 0
                        to: 12
                        value: Config.geometry.columns
                        onCommit: v => Config.setGeometry({ columns: Math.round(v) })
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        width: 50
                        horizontalAlignment: Text.AlignRight
                        text: Math.round(columns.shown) === 0 ? "Auto" : Math.round(columns.shown)
                        color: Theme.surfaceTextDim
                        font.pixelSize: 12
                    }
                }

                // Pointless with one screen, and the names mean nothing to
                // someone who has never seen "DP-1".
                SettingRow {
                    label: "Monitor"
                    visible: (Quickshell.screens ?? []).length > 1
                    z: monitor.expanded ? 10 : 0

                    Dropdown {
                        id: monitor
                        anchors.verticalCenter: parent.verticalCenter
                        width: 200
                        options: root.screenOptions
                        value: Config.geometry.screen
                        onPicked: v => Config.setGeometry({ screen: v })
                    }
                }

                SectionHeader { label: "APPEARANCE" }

                SettingRow {
                    label: "Icon size"
                    Segmented {
                        anchors.verticalCenter: parent.verticalCenter
                        options: [{ label: "Small", value: "small" },
                                  { label: "Medium", value: "medium" },
                                  { label: "Large", value: "large" }]
                        value: Config.behaviour.icon_size
                        onPicked: v => Config.setIconSize(v)
                    }
                }

                SettingRow {
                    label: "Open with"
                    Segmented {
                        anchors.verticalCenter: parent.verticalCenter
                        options: [{ label: "Single click", value: "single" },
                                  { label: "Double click", value: "double" }]
                        value: Config.behaviour.activate
                        onPicked: v => Config.setBehaviour({ activate: v })
                    }
                }

                SettingRow {
                    label: "Labels"
                    Segmented {
                        anchors.verticalCenter: parent.verticalCenter
                        options: [{ label: "Below", value: "below" },
                                  { label: "Right", value: "right" },
                                  { label: "Hidden", value: "none" }]
                        value: Config.behaviour.label_position
                        onPicked: v => Config.setBehaviour({ label_position: v })
                    }
                }

                Item {
                    width: parent.width
                    height: 18

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width
                        height: 1
                        color: Theme.surfaceBorder
                    }
                }

                Item {
                    width: parent.width
                    height: 34

                    PushButton {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        quiet: true
                        label: "Edit config file…"
                        onClicked: {
                            root.close();
                            root.editRequested();
                        }
                    }

                    PushButton {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        label: "Done"
                        onClicked: root.close()
                    }
                }

                Text {
                    text: "Changes apply straight away · Esc to close"
                    color: Theme.surfaceTextDim
                    font.pixelSize: 11
                    topPadding: 2
                }
            }
        }
    }
}
