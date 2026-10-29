#!/usr/bin/env bash
# Layout checks for scripts/gui_gtk.py — specifically, how many scrollbars the
# window has and whether the Apps list is squeezed.
#
# GTK needs a display, so this builds the window on a private `broadwayd`
# display (GTK's HTML backend: no compositor, no seat, nothing drawn on anyone's
# screen) and measures the real widget allocations. It kills only the broadwayd
# PID it started. If broadwayd is not installed the checks are skipped rather
# than failed.
#
#   ./scripts/tests/gui-layout-test.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$(dirname "$SCRIPT_DIR")")"

if ! command -v broadwayd >/dev/null 2>&1; then
  echo "SKIP: broadwayd not installed — cannot build a GTK window headlessly."
  exit 0
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/gui-layout-test.XXXXXX")"
BROADWAY_PID=""
cleanup() {
  [[ -n "$BROADWAY_PID" ]] && kill "$BROADWAY_PID" 2>/dev/null
  rm -rf "$TMP"
}
trap cleanup EXIT

# A display number and port unlikely to collide with anything.
DISP=19
PORT=8119
broadwayd --port "$PORT" ":$DISP" >"$TMP/broadwayd.log" 2>&1 &
BROADWAY_PID=$!
sleep 2
if ! kill -0 "$BROADWAY_PID" 2>/dev/null; then
  echo "SKIP: broadwayd did not start:"; sed 's/^/    /' "$TMP/broadwayd.log"
  exit 0
fi

cat > "$TMP/measure.py" <<'PY'
import sys, gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
sys.path.insert(0, sys.argv[1])
import gui_gtk

win = gui_gtk.ReplicaWindow(gui_gtk._p(".preview-thumb.png"))
win.show_all()

def areas(w, out):
    if isinstance(w, Gtk.ScrolledWindow):
        out.append(w)
    if isinstance(w, Gtk.Container):
        for c in w.get_children():
            areas(c, out)
    return out

def report():
    for _ in range(400):
        Gtk.main_iteration_do(False)
    for sw in areas(win, []):
        a = sw.get_allocation()
        bar = sw.get_vscrollbar()
        print("area %d %d %s %s" % (
            a.height,
            sw.get_child().get_preferred_height()[1],
            "bar" if (bar.get_visible() and bar.get_mapped()) else "nobar",
            sw.get_policy()[1].value_nick))
    Gtk.main_quit()
    return False

GLib.timeout_add(2000, report)
Gtk.main()
PY

out="$(GDK_BACKEND=broadway BROADWAY_DISPLAY=":$DISP" \
         timeout 60 python3 "$TMP/measure.py" "$REPO/scripts" 2>"$TMP/err")"
rc=$?
rm -rf "$REPO/scripts/__pycache__"
if [[ $rc != 0 || -z "$out" ]]; then
  echo "FAIL: could not build the window"; sed 's/^/    /' "$TMP/err"
  exit 1
fi

pass=0; fail=0
ok() { pass=$((pass+1)); printf '  \033[32mok\033[0m   %s\n' "$1"; }
no() { fail=$((fail+1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; }

echo "=== window layout ==="
printf '%s\n' "$out" | sed 's/^/    /'

bars="$(grep -c ' bar ' <<<"$out")"
if [[ "$bars" == 1 ]]; then ok "exactly one visible scrollbar"
else no "exactly one visible scrollbar (found $bars)"; fi

# Line 1 is the card grid, line 2 the Apps list — in packing order.
read -r _ grid_h grid_want _ _ <<<"$(sed -n '1p' <<<"$out")"
read -r _ apps_h apps_want apps_bar _ <<<"$(sed -n '2p' <<<"$out")"

if (( grid_want > grid_h )); then ok "the card grid is the one that scrolls"
else no "the card grid is the one that scrolls"; fi

if [[ "$apps_bar" == nobar ]]; then ok "the Apps list has no scrollbar of its own"
else no "the Apps list has no scrollbar of its own"; fi

if (( apps_h >= apps_want )); then ok "the Apps list is not squeezed ($apps_h >= $apps_want needed)"
else no "the Apps list is squeezed ($apps_h < $apps_want needed) — rows are cut off"; fi

printf '\n==== %d passed, %d failed ====\n' "$pass" "$fail"
[[ $fail == 0 ]]
