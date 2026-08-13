// Create a macOS-style floating, centered bottom dock (native Plasma panel with
// an Icons-Only Task Manager). Run via:
//   qdbus6 org.kde.plasmashell /PlasmaShell evaluateScript "$(cat add-dock.js)"
var panel = new Panel;
panel.location = "bottom";
panel.height = 58;
panel.floating = true;
try { panel.alignment = "center"; } catch (e) {}
try { panel.lengthMode = "fit"; } catch (e) {}

var tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers",
    "applications:systemsettings.desktop," +
    "applications:org.kde.dolphin.desktop," +
    "applications:Alacritty.desktop," +
    "applications:org.kde.kate.desktop," +
    "applications:firefox.desktop," +
    "applications:zen.desktop");
tasks.writeConfig("showOnlyCurrentDesktop", false);
tasks.writeConfig("showOnlyCurrentActivity", false);
tasks.reloadConfig();
