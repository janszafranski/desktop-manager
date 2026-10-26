pragma Singleton
import QtQuick
QtObject {
    // Two fake outputs, so the Monitor row is exercised.
    property var screens: [{ name: "DP-1" }, { name: "HDMI-A-1" }]
}
