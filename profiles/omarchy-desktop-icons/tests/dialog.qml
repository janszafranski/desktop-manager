import QtQuick
import QtQuick.Window

// Harness for SettingsDialog.qml. Loads the real dialog (with the layer-shell
// surface swapped for a plain Item) against the real Config logic, drives the
// controls, and asserts what landed in the config.
Window {
    id: win

    visible: true
    width: 920
    height: 820
    color: "#2e2e38"
    title: "settings-harness"

    property int passed: 0
    property int failed: 0
    property var sliders: []
    property var segments: []
    property var drops: []
    property var buttons: []

    function ok(name, cond, detail) {
        if (cond) { passed++; console.log("  PASS  " + name); }
        else { failed++; console.log("  FAIL  " + name + (detail ? "   -> " + detail : "")); }
    }

    function eq(name, got, want) {
        ok(name, got === want, "got " + JSON.stringify(got) + ", want " + JSON.stringify(want));
    }

    function walk(o, out) {
        const kids = o.children || [];
        for (let i = 0; i < kids.length; i++) { out.push(kids[i]); walk(kids[i], out); }
        return out;
    }

    function classify() {
        sliders = []; segments = []; drops = []; buttons = [];
        for (const o of walk(dlg, [])) {
            if (o.commit !== undefined && o.heldValue !== undefined) sliders.push(o);
            else if (o.options !== undefined && o.expanded !== undefined) drops.push(o);
            else if (o.options !== undefined) segments.push(o);
            else if (o.quiet !== undefined) buttons.push(o);
        }
    }

    // Pick an option on a segmented control by its visible label.
    function pick(seg, label) {
        for (const o of seg.options) if (o.label === label) { seg.picked(o.value); return true; }
        return false;
    }

    // Neutral backdrop: the dialog's own scrim darkens this, exactly as it
    // darkens the wallpaper on a real desktop.
    Rectangle {
        anchors.fill: parent
        color: "#4a4a57"
    }

    Dialog {
        id: dlg
        anchors.fill: parent
    }

    // --- the script ---------------------------------------------------------

    property int step: 0
    readonly property var steps: [
        function () {
            console.log("\n[1] dialog opens and finds its controls");
            dlg.show();
            classify();
            eq("4 segmented controls", segments.length, 4);
            eq("2 sliders while per-side is collapsed", sliders.length, 2);
            eq("1 monitor dropdown", drops.length, 1);
            eq("2 footer buttons", buttons.length, 2);
            ok("dialog is open", dlg.open === true);
            ok("per-side starts collapsed for uniform margins", dlg.perSide === false);
        },

        function () {
            console.log("\n[2] every non-item config key is settable");
            const w0 = Config.writes;

            ok("corner picked", pick(segments[0], "Bottom right"));
            eq("geometry.anchor", Config.geometry.anchor, "bottom-right");

            ok("icon size picked", pick(segments[1], "Large"));
            eq("behaviour.icon_size", Config.behaviour.icon_size, "large");
            eq("icon pixels followed", Config.iconPixels, 72);

            ok("activate picked", pick(segments[2], "Single click"));
            eq("behaviour.activate", Config.behaviour.activate, "single");

            ok("labels picked", pick(segments[3], "Right"));
            eq("behaviour.label_position", Config.behaviour.label_position, "right");
            eq("labelBeside followed", Config.labelBeside, true);

            drops[0].picked("HDMI-A-1");
            eq("geometry.screen", Config.geometry.screen, "HDMI-A-1");

            // columns slider, by keyboard (immediate, no debounce)
            sliders[1].nudge(1);
            eq("geometry.columns", Config.geometry.columns, 1);

            eq("one save per change", Config.writes - w0, 6);

            const parsed = JSON.parse(Config.serialize());
            ok("serialize() is valid JSON with the same shape",
               parsed.geometry !== undefined && parsed.behaviour !== undefined
               && parsed.items !== undefined
               && parsed.geometry.margins !== undefined
               && Object.keys(parsed).length === 3,
               Config.serialize());
        },

        function () {
            console.log("\n[3] edge-spacing slider debounces, then writes all four sides");
            const w0 = Config.writes;
            sliders[0].held = true;
            sliders[0].dragTo(10);
            sliders[0].dragTo(20);
            sliders[0].dragTo(40);
            eq("nothing written yet (debounced)", Config.writes - w0, 0);
            ok("handle shows the dragged value", sliders[0].shown === sliders[0].heldValue);
            win.pendingDrag = sliders[0].heldValue;
            win.dragBaseWrites = w0;
        },

        function () {
            // ~300ms later: the trailing timer should have fired exactly once.
            eq("one write after the trailing delay", Config.writes - win.dragBaseWrites, 1);
            const m = Config.geometry.margins;
            eq("margins.top", m.top, Math.round(win.pendingDrag));
            eq("margins.left", m.left, Math.round(win.pendingDrag));
            eq("margins.right", m.right, Math.round(win.pendingDrag));
            eq("margins.bottom", m.bottom, Math.round(win.pendingDrag));
            ok("still uniform", dlg.uniformMargins === true);
        },

        function () {
            console.log("\n[4] per-side disclosure drives one side at a time");
            dlg.perSide = true;
            classify();
            eq("6 sliders when expanded", sliders.length, 6);
            // sliders: [edge, top, left, right, bottom, columns]
            const before = Config.geometry.margins;
            sliders[2].nudge(20);   // Left, +20 steps of 1
            const m = Config.geometry.margins;
            eq("left moved", m.left, before.left + 20);
            eq("top untouched", m.top, before.top);
            eq("right untouched", m.right, before.right);
            eq("bottom untouched", m.bottom, before.bottom);
            ok("no longer uniform", dlg.uniformMargins === false);
            ok("per-side slider reaches past 120", sliders[2].to === 600);
        },

        function () {
            console.log("\n[5] a hand-edit to the file moves the controls and is not clobbered");
            const w0 = Config.writes;
            Config.externalEdit(JSON.stringify({
                geometry: { anchor: "top-right",
                            margins: { top: 11, left: 560, right: 12, bottom: 13 },
                            columns: 5, screen: "DP-1" },
                behaviour: { icon_size: "small", activate: "double", label_position: "below" },
                items: []
            }));
            eq("no write provoked by the external edit", Config.writes - w0, 0);
            classify();
            eq("corner control followed the file", segments[0].value, "top-right");
            eq("icon size control followed", segments[1].value, "small");
            eq("labels control followed", segments[3].value, "below");
            eq("monitor control followed", drops[0].value, "DP-1");
            eq("columns slider followed", sliders[5].value, 5);
            eq("edge slider shows the file's top margin", sliders[0].value, 11);
            eq("per-side left slider shows 560", sliders[2].value, 560);
            ok("560 displays without being clamped away",
               sliders[2].fraction > 0.9 && sliders[2].fraction <= 1, String(sliders[2].fraction));
            ok("mixed margins detected", dlg.uniformMargins === false);
        },

        function () {
            console.log("\n[6] arrow keys clamp to the slider range");
            Config.setGeometry({ columns: 0 });
            classify();
            sliders[5].nudge(-1);
            eq("columns cannot go below 0", Config.geometry.columns, 0);
            for (let i = 0; i < 20; i++) sliders[5].nudge(1);
            eq("columns cannot go above 12", Config.geometry.columns, 12);
        },

        function () {
            console.log("\n[7] footer: Edit config file… and Done");
            let edits = 0;
            dlg.editRequested.connect(function () { edits++; });
            buttons[0].clicked();
            eq("edit button asked the shell to open an editor", edits, 1);
            ok("edit button closed the dialog", dlg.open === false);

            dlg.show();
            buttons[1].clicked();
            ok("Done closed the dialog", dlg.open === false);
        },

        function () {
            console.log("\n[8] present the dialog for the screenshot");
            classify();
            for (const s of sliders) s.held = false;   // clear the held-handle test state
            Config.externalEdit(JSON.stringify({
                geometry: { anchor: "top-left",
                            margins: { top: 24, left: 24, right: 24, bottom: 24 },
                            columns: 0, screen: "" },
                behaviour: { icon_size: "medium", activate: "double", label_position: "below" },
                items: []
            }));
            dlg.show();
            dlg.perSide = false;

            // Crop the window down to the panel plus a margin, so the saved
            // image is the dialog rather than a mostly-empty desktop.
            for (const o of walk(dlg, [])) {
                if (o.width === 520 && o.radius === 14) { win.panel = o; break; }
            }
            ok("found the panel", win.panel !== null);
            win.width = 520 + 120;
            win.height = Math.round(win.panel.height) + 120;
        },

        function () {
            eq("edge spacing reads back from the file", Math.round(sliders[0].shown), 24);
            win.contentItem.grabToImage(function (res) {
                const out = Qt.resolvedUrl("shot.png").toString().replace("file://", "");
                win.ok("screenshot grabbed", res.saveToFile(out), out);
                win.report();
            }, Qt.size(win.width, win.height));
        }
    ]

    property real pendingDrag: 0
    property int dragBaseWrites: 0
    property Item panel: null

    function report() {
        console.log("\n==== " + passed + " passed, " + failed + " failed ====");
        Qt.exit(failed === 0 ? 0 : 1);
    }

    Timer {
        id: runner
        interval: 320
        repeat: true
        running: true
        onTriggered: {
            if (win.step >= win.steps.length) { runner.running = false; return; }
            const f = win.steps[win.step++];
            try { f(); } catch (e) { win.failed++; console.log("  THREW  " + e + "\n" + e.stack); }
        }
    }
}
