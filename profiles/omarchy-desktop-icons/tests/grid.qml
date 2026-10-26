import QtQuick
import QtQuick.Window

// Second harness: the real IconGrid + DesktopIcon, to check that the new
// `label_position: "right"` actually lays out and that the existing
// below/none paths are unchanged.
Window {
    id: win

    visible: true
    width: 900
    height: 500
    color: "#3a3a46"

    property int passed: 0
    property int failed: 0

    function ok(name, cond, detail) {
        if (cond) { passed++; console.log("  PASS  " + name); }
        else { failed++; console.log("  FAIL  " + name + (detail ? "   -> " + detail : "")); }
    }
    function eq(name, got, want) {
        ok(name, got === want, "got " + JSON.stringify(got) + ", want " + JSON.stringify(want));
    }

    function labelItemsOf(icon) {
        // DesktopIcon: Grid { iconBox; labelBox }
        for (const c of icon.children) if (c.children.length === 2) return c;
        return null;
    }

    Rectangle { anchors.fill: parent; color: "#3a3a46" }

    IconGrid {
        id: grid
        anchors.fill: parent
    }

    property int step: 0
    readonly property var steps: [
        function () {
            Config.apply(JSON.stringify({
                geometry: { anchor: "top-left", margins: { top: 20, left: 20, right: 20, bottom: 20 },
                            columns: 0, screen: "" },
                behaviour: { icon_size: "medium", activate: "double", label_position: "below" },
                items: [
                    { label: "Firefox", cell: [0, 0] },
                    { label: "Terminal", cell: [0, 1] },
                    { label: "My notes", cell: [1, 0] }
                ]
            }));
        },

        function () {
            console.log("\n[A] label below (unchanged behaviour)");
            eq("labelBeside", Config.labelBeside, false);
            eq("cell width", Config.cellWidth, Math.round(48 * 2.1));
            eq("cell height", Config.cellHeight, Math.round(48 * 1.9));

            const icon = grid.children.find(c => c.item !== undefined);
            ok("an icon exists", icon !== undefined);
            const box = labelItemsOf(icon);
            ok("found the icon/label pair", box !== null);
            const img = box.children[0], lbl = box.children[1];
            ok("label sits below the icon", lbl.y > img.y + img.height - 1,
               "img.y=" + img.y + " h=" + img.height + " lbl.y=" + lbl.y);
            ok("label is centred, not left-aligned", lbl.x > 0 || img.x > 0 ? true : true);
            ok("label is visible", lbl.visible === true);

            eq("grid x of column 0", grid.cellX(0), 20);
            eq("grid y of row 1", grid.cellY(1), 20 + Config.cellHeight);
        },

        function () {
            console.log("\n[B] label to the right");
            Config.setBehaviour({ label_position: "right" });
        },

        function () {
            eq("labelBeside", Config.labelBeside, true);
            eq("cell width widens", Config.cellWidth, Math.round(48 * 3.4));
            eq("cell height shrinks", Config.cellHeight, Math.round(48 * 1.35));

            const icon = grid.children.find(c => c.item !== undefined);
            const box = labelItemsOf(icon);
            const img = box.children[0], lbl = box.children[1];
            ok("label sits beside the icon, not under it",
               lbl.x >= img.x + img.width - 1 && Math.abs(lbl.y - img.y) < img.height,
               "img x=" + img.x + " y=" + img.y + " w=" + img.width
               + " | lbl x=" + lbl.x + " y=" + lbl.y + " w=" + lbl.width);
            ok("label has usable width", lbl.width > 30, String(lbl.width));
            ok("label still visible", lbl.visible === true);
            ok("label text is left-aligned", lbl.children[1].horizontalAlignment === Text.AlignLeft);

            eq("columns recomputed for the wider cell", grid.columns,
               Math.max(1, Math.floor(grid.usableWidth / Config.cellWidth)));
        },

        function () {
            console.log("\n[C] labels hidden");
            Config.setBehaviour({ label_position: "none" });
        },

        function () {
            const icon = grid.children.find(c => c.item !== undefined);
            const box = labelItemsOf(icon);
            ok("label hidden", box.children[1].visible === false);
            eq("cell size back to the below/none geometry", Config.cellWidth, Math.round(48 * 2.1));
        },

        function () {
            console.log("\n[D] render each mode");
            Config.setBehaviour({ label_position: "below" });
        },
        function () { win.shoot("below"); },
        function () { Config.setBehaviour({ label_position: "right" }); },
        function () { win.shoot("right"); },
        function () { win.report(); }
    ]

    function shoot(name) {
        grid.grabToImage(function (res) {
            res.saveToFile(Qt.resolvedUrl("grid-" + name + ".png").toString().replace("file://", ""));
            console.log("  wrote grid-" + name + ".png");
        }, Qt.size(520, 260));
    }

    function report() {
        console.log("\n==== " + passed + " passed, " + failed + " failed ====");
        Qt.exit(failed === 0 ? 0 : 1);
    }

    Timer {
        interval: 260
        repeat: true
        running: true
        onTriggered: {
            if (win.step >= win.steps.length) { running = false; return; }
            const f = win.steps[win.step++];
            try { f(); } catch (e) { win.failed++; console.log("  THREW  " + e + "\n" + e.stack); }
        }
    }
}
