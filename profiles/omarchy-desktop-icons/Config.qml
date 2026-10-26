pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Reads and writes ~/.config/omarchy-desktop-icons/config.json.
//
// JSON, not TOML: QML has JSON.parse/stringify built in, and a TOML parser
// would have been more code than the rest of this app. The file is still
// perfectly hand-editable.
Singleton {
    id: root

    readonly property string dir: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config")
        + "/omarchy-desktop-icons"
    readonly property string path: dir + "/config.json"

    // items: [{ label, desktop_id | exec, icon, cell: [col, row] }]
    property var items: []
    property var geometry: defaultGeometry()
    property var behaviour: defaultBehaviour()

    readonly property int iconPixels: ({ small: 32, medium: 48, large: 72 })[behaviour.icon_size] ?? 48
    // A label beside the icon needs width instead of height.
    readonly property bool labelBeside: behaviour.label_position === "right"
    readonly property int cellWidth: Math.round(iconPixels * (labelBeside ? 3.4 : 2.1))
    readonly property int cellHeight: Math.round(iconPixels * (labelBeside ? 1.35 : 1.9))

    // Set while we are writing, so our own write does not trigger a reload.
    property string lastWritten: ""

    // True between "there was no config file" and "the desktop entry index
    // loaded, so we can pick sensible starter icons".
    property bool needsSeed: false

    function defaultGeometry() {
        return { anchor: "top-left", margins: { top: 24, left: 24, right: 24, bottom: 24 }, columns: 0, screen: "" };
    }

    function defaultBehaviour() {
        return { icon_size: "medium", activate: "double", label_position: "below" };
    }

    function merge(base, over) {
        const out = Object.assign({}, base);
        if (over && typeof over === "object")
            for (const k in over) if (over[k] !== undefined && over[k] !== null) out[k] = over[k];
        return out;
    }

    function apply(text) {
        let data = {};
        try {
            data = JSON.parse(text);
        } catch (e) {
            console.warn("omarchy-desktop-icons: config.json is not valid JSON, keeping current config:", e);
            return;
        }
        const g = merge(defaultGeometry(), data.geometry);
        g.margins = merge(defaultGeometry().margins, data.geometry && data.geometry.margins);
        geometry = g;
        behaviour = merge(defaultBehaviour(), data.behaviour);
        items = (data.items ?? []).map((it, i) => ({
            label: it.label ?? "",
            desktop_id: it.desktop_id ?? "",
            exec: it.exec ?? "",
            icon: it.icon ?? "",
            cell: (it.cell && it.cell.length === 2) ? [it.cell[0] | 0, it.cell[1] | 0] : [0, i]
        }));
    }

    function serialize() {
        return JSON.stringify({ geometry: geometry, behaviour: behaviour, items: items }, null, 2) + "\n";
    }

    function save() {
        lastWritten = serialize();
        file.setText(lastWritten);
    }

    function reload() {
        file.reload();
    }

    // --- mutations ---------------------------------------------------------

    function addItem(item) {
        items = items.concat([item]);
        save();
    }

    function updateItem(index, changes) {
        const next = items.slice();
        next[index] = Object.assign({}, next[index], changes);
        items = next;
        save();
    }

    function removeItem(index) {
        const next = items.slice();
        next.splice(index, 1);
        items = next;
        save();
    }

    // Generic setters used by SettingsDialog. Each one merges over what is
    // already loaded and saves, so the grid updates before the write lands.
    function setGeometry(changes) {
        geometry = merge(geometry, changes);
        save();
    }

    function setMargins(changes) {
        const g = merge(geometry, {});
        g.margins = merge(geometry.margins, changes);
        geometry = g;
        save();
    }

    function setBehaviour(changes) {
        behaviour = merge(behaviour, changes);
        save();
    }

    function setIconSize(size) { setBehaviour({ icon_size: size }); }

    function isCellFree(col, row, exceptIndex) {
        return !items.some((it, i) => i !== exceptIndex && it.cell[0] === col && it.cell[1] === row);
    }

    // First free cell scanning down each column in turn.
    function firstFreeCell(rows, exceptIndex) {
        for (let col = 0; col < 64; col++)
            for (let row = 0; row < Math.max(1, rows); row++)
                if (isCellFree(col, row, exceptIndex)) return [col, row];
        return [0, 0];
    }

    function autoArrange(rows) {
        const next = items.map(it => Object.assign({}, it));
        let col = 0, row = 0;
        for (const it of next) {
            it.cell = [col, row];
            if (++row >= Math.max(1, rows)) { row = 0; col++; }
        }
        items = next;
        save();
    }

    FileView {
        id: file
        path: root.path
        atomicWrites: true
        watchChanges: true
        printErrors: false

        onLoaded: {
            const t = text();
            if (t !== root.lastWritten) root.apply(t);
        }
        onFileChanged: reload()
        onLoadFailed: {
            // No config yet: write out the defaults now, then seed a few real
            // apps as soon as the desktop entry index has finished loading.
            root.save();
            root.needsSeed = true;
            root.trySeed();
        }
    }

    // The desktop entry index and the config file load independently, so seed
    // from whichever finishes last.
    function trySeed() {
        if (!needsSeed || DesktopEntries.applications.values.length === 0) return;
        needsSeed = false;
        items = Apps.seedItems();
        save();
    }

    Connections {
        target: Apps
        function onRevisionChanged() { root.trySeed(); }
    }

    Component.onCompleted: ensureDir.running = true

    Process {
        id: ensureDir
        command: ["mkdir", "-p", root.dir]
        onExited: file.reload()
    }
}
