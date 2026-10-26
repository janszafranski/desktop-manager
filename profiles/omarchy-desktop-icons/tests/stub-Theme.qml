pragma Singleton
import QtQuick
QtObject {
    readonly property color labelColor: "#ffffff"
    readonly property color labelShadow: Qt.rgba(0, 0, 0, 0.85)
    property bool light: false
    property color accent: "#7aa2f7"
    property color surface: "#1b1b20"
    property color surfaceText: "#e8e8ee"
    readonly property color selection: Qt.rgba(accent.r, accent.g, accent.b, 0.28)
    readonly property color selectionBorder: Qt.rgba(accent.r, accent.g, accent.b, 0.7)
    readonly property color hover: light ? Qt.rgba(0, 0, 0, 0.08) : Qt.rgba(1, 1, 1, 0.12)
    readonly property color surfaceBorder: light ? Qt.rgba(0, 0, 0, 0.14) : Qt.rgba(1, 1, 1, 0.14)
    readonly property color surfaceTextDim: light ? Qt.rgba(0, 0, 0, 0.5) : Qt.rgba(1, 1, 1, 0.45)
}
