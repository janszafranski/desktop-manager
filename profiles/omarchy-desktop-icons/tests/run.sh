#!/usr/bin/env bash
# Runs the QML behaviour tests for SettingsDialog and the icon layout.
#
#   ./tests/run.sh            # run both suites
#   ./tests/run.sh --shots    # also drop the rendered PNGs in the build dir
#
# These run OFF-COMPOSITOR, under Qt's offscreen platform, so they are safe to
# run on a live desktop — nothing is drawn on your wallpaper and the running
# copy of the app is never touched.
#
# The app's own QML is used as-is except for two mechanical substitutions, done
# into a scratch build directory:
#
#   * the layer-shell `PanelWindow` root becomes a plain `Item`, because
#     layer-shell needs a compositor;
#   * `Config`, `Theme`, `Apps` and `Quickshell` are replaced by the stubs in
#     this directory, so the config lives in memory instead of in a file.
#
# Config's real merge/serialize/setter code is kept — only its FileView I/O is
# swapped out — so the thing under test is the shipped logic, not a copy.
#
# What this therefore CANNOT cover: the dialog's own layer-shell surface, Esc
# and click-outside dismissal, and tab/arrow focus movement between rows. Those
# need a compositor and a human.
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
APP="$(dirname "$HERE")"
BUILD="${TMPDIR:-/tmp}/omarchy-desktop-icons-tests"

QML=""
for c in qml6 qml; do command -v "$c" >/dev/null 2>&1 && { QML="$c"; break; }; done
[ -n "$QML" ] || { echo "need qt6-declarative (qml6) to run these" >&2; exit 1; }

rm -rf "$BUILD"
mkdir -p "$BUILD"

python3 - "$APP" "$BUILD" <<'PY'
import pathlib, re, sys
app, build = (pathlib.Path(p) for p in sys.argv[1:3])

def strip_quickshell(text):
    # Quickshell's modules are C++ plugins; the stubs stand in for them.
    return re.sub(r"^import Quickshell[^\n]*\n", "", text, flags=re.M)

# SettingsDialog: layer-shell window -> plain Item.
s = strip_quickshell((app / "SettingsDialog.qml").read_text())
s = s.replace("PanelWindow {\n    id: root", "Item {\n    id: root")
for line in ('    visible: open\n',
             '    color: "transparent"\n',
             "    exclusionMode: ExclusionMode.Ignore\n",
             "    WlrLayershell.layer: WlrLayer.Overlay\n",
             '    WlrLayershell.namespace: "omarchy-desktop-icons-settings"\n',
             "    WlrLayershell.keyboardFocus: open ? WlrKeyboardFocus.Exclusive"
             " : WlrKeyboardFocus.None\n",
             "    anchors { top: true; left: true; right: true; bottom: true }\n"):
    if line not in s:
        sys.exit("tests/run.sh is out of date with SettingsDialog.qml: "
                 "could not find %r" % line)
    s = s.replace(line, "")
(build / "Dialog.qml").write_text(s)

for name in ("DesktopIcon.qml", "IconGrid.qml"):
    (build / name).write_text(strip_quickshell((app / name).read_text()))

# Config: keep everything above the FileView, swap the file write for a counter.
cfg = (app / "Config.qml").read_text()
head = strip_quickshell(cfg[:cfg.index("    FileView {")])
head = head.replace(
    'readonly property string dir: (Quickshell.env("XDG_CONFIG_HOME")'
    ' || Quickshell.env("HOME") + "/.config")\n        + "/omarchy-desktop-icons"',
    'readonly property string dir: "(in memory)"')
head = head.replace("Singleton {\n    id: root", "QtObject {\n    id: root")
head = head.replace("file.setText(lastWritten);", "writes = writes + 1;")
head = head.replace("function reload() {\n        file.reload();\n    }",
                    "function reload() { apply(lastWritten); }")
(build / "Config.qml").write_text(head + """
    // Test seam: count saves, and let a test pretend an editor rewrote the
    // file underneath us.
    property int writes: 0

    function externalEdit(text) {
        lastWritten = "";
        apply(text);
    }
}
""")

tests = app / "tests"
for stub in ("Theme", "Apps", "Quickshell", "IconImage"):
    (build / (stub + ".qml")).write_text((tests / ("stub-%s.qml" % stub)).read_text())

(build / "qmldir").write_text(
    "singleton Config 1.0 Config.qml\n"
    "singleton Theme 1.0 Theme.qml\n"
    "singleton Apps 1.0 Apps.qml\n"
    "singleton Quickshell 1.0 Quickshell.qml\n")

for t in ("dialog", "grid"):
    (build / ("test-%s.qml" % t)).write_text((tests / ("%s.qml" % t)).read_text())
PY

export QT_QPA_PLATFORM=offscreen
export QT_FORCE_STDERR_LOGGING=1
export QT_ASSUME_STDERR_HAS_CONSOLE=1

status=0
for t in dialog grid; do
    echo "=== $t ==="
    if ! (cd "$BUILD" && "$QML" -I . "test-$t.qml" 2>&1 | sed 's/^qml: //'); then
        status=1
    fi
done

if [ "${1:-}" = "--shots" ]; then
    echo
    echo "rendered images in $BUILD:"
    ls -1 "$BUILD"/*.png 2>/dev/null || echo "  (none)"
fi

exit "$status"
