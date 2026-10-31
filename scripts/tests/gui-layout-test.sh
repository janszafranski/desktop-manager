#!/usr/bin/env bash
# Layout checks for scripts/gui_gtk.py — how many scrollbars the window has,
# whether the Apps list is squeezed, and whether the card grid actually grows
# with the window (it used to be a fixed height, so the second row of cards was
# cut off at every window size and growing the window only added dead space
# under the Apps box).
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
from gi.repository import Gtk, GLib, Gdk
sys.path.insert(0, sys.argv[1])
import gui_gtk

# Heights the window is resized to, to prove the grid is elastic. The tall one
# is comfortably above the grid's natural height plus the rest of the window.
SHORT_H, TALL_H = 900, 1500

win = gui_gtk.ReplicaWindow(gui_gtk._p(".preview-thumb.png"))
win.show_all()


def areas(w, out):
    if isinstance(w, Gtk.ScrolledWindow):
        out.append(w)
    if isinstance(w, Gtk.Container):
        for c in w.get_children():
            areas(c, out)
    return out


def settle():
    for _ in range(600):
        Gtk.main_iteration_do(False)


def emit(tag):
    """One line per scroll area: tag, allocation, what the child wants, bar."""
    settle()
    for sw in areas(win, []):
        a = sw.get_allocation()
        bar = sw.get_vscrollbar()
        print("%s %d %d %s %s" % (
            tag,
            a.height,
            sw.get_child().get_preferred_height()[1],
            "bar" if (bar.get_visible() and bar.get_mapped()) else "nobar",
            sw.get_policy()[1].value_nick))


def report():
    # Usable screen height, so the caller knows whether the opening height was
    # clamped to the screen (broadwayd reports no work area, so it is not).
    try:
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        work_h = monitor.get_workarea().height
    except Exception:
        work_h = 0
    print("workarea %d" % work_h)
    settle()
    width = win.get_allocation().width
    emit("area")
    win.resize(width, SHORT_H)
    emit("short")
    win.resize(width, TALL_H)
    emit("tall")
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

work_h="$(awk '/^workarea /{print $2}' <<<"$out")"
# Within each tag, line 1 is the card grid and line 2 the Apps list — in
# packing order.
read -r _ grid_h grid_want grid_bar grid_policy <<<"$(grep '^area ' <<<"$out" | sed -n 1p)"
read -r _ apps_h apps_want apps_bar _ <<<"$(grep '^area ' <<<"$out" | sed -n 2p)"
read -r _ short_grid_h _ _ _ <<<"$(grep '^short ' <<<"$out" | sed -n 1p)"
read -r _ short_apps_h short_apps_want short_apps_bar _ <<<"$(grep '^short ' <<<"$out" | sed -n 2p)"
read -r _ tall_grid_h tall_grid_want _ _ <<<"$(grep '^tall ' <<<"$out" | sed -n 1p)"
read -r _ tall_apps_h tall_apps_want tall_apps_bar _ <<<"$(grep '^tall ' <<<"$out" | sed -n 2p)"

echo
echo "--- at the size the window opens at ---"

bars="$(grep -c ' bar ' <<<"$(grep '^area ' <<<"$out")")"
if [[ "$bars" == 1 ]]; then ok "exactly one visible scrollbar"
else no "exactly one visible scrollbar (found $bars)"; fi

# The card grid is the scroll area, not the Apps list: it is the one with the
# permanent track. (It no longer has to *overflow* for that to be true — the
# window now opens tall enough to show every row.)
if [[ "$grid_bar" == bar && "$grid_policy" == always ]]; then
  ok "the card grid is the one that scrolls"
else no "the card grid is the one that scrolls (bar=$grid_bar policy=$grid_policy)"; fi

if [[ "$apps_bar" == nobar ]]; then ok "the Apps list has no scrollbar of its own"
else no "the Apps list has no scrollbar of its own"; fi

if (( apps_h >= apps_want )); then ok "the Apps list is not squeezed ($apps_h >= $apps_want needed)"
else no "the Apps list is squeezed ($apps_h < $apps_want needed) — rows are cut off"; fi

# JAN-58: the window used to open with a fixed 620px of grid against 879px of
# cards, so row 2 was cut off on open and no resize could help. Only assert the
# opening height when the screen is tall enough to honour it — on a short screen
# the opening height is deliberately clamped to the work area.
need_open=$(( grid_want + apps_h + 220 ))
if (( work_h == 0 || work_h >= need_open )); then
  if (( grid_h >= grid_want )); then
    ok "it opens with every card row visible ($grid_h >= $grid_want needed)"
  else
    no "it opens with card rows cut off ($grid_h < $grid_want needed)"
  fi
else
  ok "opening height clamped to a ${work_h}px screen — skipping the open-height check"
fi

echo
echo "--- resized to ${short_grid_h}px and ${tall_grid_h}px of grid ---"

# The bug: the grid had a fixed height request, so it was allocated the same
# number of pixels no matter how large the window got, and the extra height
# became dead space under the Apps box.
if (( tall_grid_h > short_grid_h )); then
  ok "the card grid grows with the window ($short_grid_h -> $tall_grid_h)"
else
  no "the card grid is a fixed height ($short_grid_h -> $tall_grid_h) — growing the window cannot reveal row 2"
fi

if (( tall_grid_h >= tall_grid_want )); then
  ok "a tall enough window shows every card row ($tall_grid_h >= $tall_grid_want needed)"
else
  no "even a tall window cuts cards off ($tall_grid_h < $tall_grid_want needed)"
fi

# The grid, not the Apps list, is what absorbs a resize in either direction.
if [[ "$short_apps_bar" == nobar ]] && (( short_apps_h >= short_apps_want )); then
  ok "shrinking the window does not squeeze the Apps list ($short_apps_h >= $short_apps_want needed)"
else
  no "shrinking the window squeezes the Apps list ($short_apps_h < $short_apps_want needed, bar=$short_apps_bar)"
fi

if [[ "$tall_apps_bar" == nobar ]] && (( tall_apps_h == apps_h )); then
  ok "growing the window gives the space to the cards, not the Apps box ($tall_apps_h px)"
else
  no "growing the window moved the Apps box ($apps_h -> $tall_apps_h, bar=$tall_apps_bar)"
fi

printf '\n==== %d passed, %d failed ====\n' "$pass" "$fail"
[[ $fail == 0 ]]
