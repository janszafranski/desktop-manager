// Create a macOS-style floating, centered bottom dock — a native Plasma panel
// hosting the Punchi Dock Remastered plasmoid (installed by apply.sh). Run via:
//   qdbus6 org.kde.plasmashell /PlasmaShell evaluateScript "$(cat add-dock.js)"
//
// Idempotent: WhiteSur's look-and-feel layout ships its own bottom dock, and
// re-running this would otherwise stack duplicate overlapping docks. So first
// remove any existing bottom panel that is a single-widget dock (either the
// WhiteSur Icons-Only Task Manager or a Punchi dock from a previous run).
var DOCK_WIDGETS = ["org.kde.plasma.icontasks", "org.kde.plasma.punchi-dock-remastered"];
var existing = panels();
for (var i = 0; i < existing.length; i++) {
    var p = existing[i];
    if (p.location != "bottom") continue;
    var w = p.widgets();
    if (w.length == 1 && DOCK_WIDGETS.indexOf(w[0].type) != -1) p.remove();
}

var panel = new Panel;
panel.location = "bottom";
panel.height = 80;               // room for Punchi's icons + hover magnification
panel.floating = true;
try { panel.alignment = "center"; } catch (e) {}
try { panel.lengthMode = "fit"; } catch (e) {}

// Punchi Dock manages its own items, magnification, indicators, etc.
panel.addWidget("org.kde.plasma.punchi-dock-remastered");

// Report the new panel's containment id so apply.sh can set its opacity
// (panelOpacity can't be persisted from here — writeConfig doesn't flush it).
print(panel.id);
