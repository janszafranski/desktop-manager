#!/usr/bin/env bash
# Checks for the confirmation that guards `install.sh files` in the GUI
# (scripts/gui_gtk.py) — the behavioural half of JAN-55.
#
# What it asserts:
#   * the path list shown is derived from scripts/manifest.sh, not a second
#     hardcoded copy of it (every path shown is in the manifest, and a path
#     added to the manifest shows up without touching gui_gtk.py)
#   * it fires when the user has files to lose, and not on a fresh machine
#   * it fires only for the `files` stage, and never for a Dry run
#   * "this isn't the machine the snapshot came from" is said in the dialog
#   * "Restore my own settings" is live only when a ~/.config-backup-* exists
#   * the restore-backup.sh command line gui.sh builds is one the script takes
#
# Nothing here touches the real $HOME: every check runs against a fabricated
# one under $TMPDIR. GTK needs a display, so the window is built on a private
# `broadwayd` (GTK's HTML backend: no compositor, no seat, nothing drawn on
# anyone's screen) exactly as scripts/tests/gui-layout-test.sh does. It kills
# only the broadwayd PID it started, and skips rather than fails if broadwayd is
# missing or another broadwayd on this machine is holding the display.
#
#   ./scripts/tests/install-guard-test.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$(dirname "$SCRIPT_DIR")")"

if ! command -v broadwayd >/dev/null 2>&1; then
  echo "SKIP: broadwayd not installed — cannot build a GTK window headlessly."
  exit 0
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/install-guard-test.XXXXXX")"
BROADWAY_PID=""
cleanup() {
  [[ -n "$BROADWAY_PID" ]] && kill "$BROADWAY_PID" 2>/dev/null
  rm -rf "$TMP" "$REPO/scripts/__pycache__"
}
trap cleanup EXIT

DISP=45
PORT=8145

# Each probe needs its own broadwayd — this broadwayd aborts as soon as its
# client disconnects, so one server cannot serve several probes in a row.
#
# Only one broadwayd can run on the machine at a time, whatever display numbers
# are used: a second one fails with "Can't listen ... Address already in use"
# even on an unused number. So this waits for a neighbour (another run of this
# test, or another agent's window) to finish rather than hunting for a free
# number, and gives up with a SKIP rather than reporting false failures.
start_broadway() {
  if [[ -n "$BROADWAY_PID" ]]; then
    kill "$BROADWAY_PID" 2>/dev/null
    # Wait for it to actually exit — until it does, it holds the bind itself.
    for _ in $(seq 1 50); do
      kill -0 "$BROADWAY_PID" 2>/dev/null || break
      sleep 0.1
    done
    BROADWAY_PID=""
  fi
  local try pid
  for try in 1 2 3 4 5 6; do
    broadwayd --port "$PORT" ":$DISP" >"$TMP/broadwayd.log" 2>&1 &
    pid=$!
    sleep 2
    if kill -0 "$pid" 2>/dev/null \
       && ! grep -q "Can't listen" "$TMP/broadwayd.log"; then
      BROADWAY_PID=$pid
      return 0
    fi
    kill "$pid" 2>/dev/null
    sleep 5
  done
  return 1
}

pass=0; fail=0
ok() { pass=$((pass+1)); printf '  \033[32mok\033[0m   %s\n' "$1"; }
no() { fail=$((fail+1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; }

if ! start_broadway; then
  echo "SKIP: broadwayd did not start:"; sed 's/^/    /' "$TMP/broadwayd.log"
  exit 0
fi

# --- the probe ---------------------------------------------------------------
# probe.py <scripts-dir> <fake-home> — prints one `key<TAB>value` line per fact.
#
# The fake $HOME is swapped in *after* GTK has initialised, not via the
# environment: broadwayd puts its socket in the real $HOME/.cache, so a client
# started with HOME already pointing elsewhere cannot find the display at all.
cat > "$TMP/probe.py" <<'PY'
import os, sys, gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
ok, _ = Gtk.init_check([])
if not ok:
    sys.exit("could not connect to the broadway display")

HOME = sys.argv[2]
os.environ["HOME"] = HOME
os.environ["XDG_CONFIG_HOME"] = os.path.join(HOME, ".config")
sys.path.insert(0, sys.argv[1])
import gui_gtk
assert os.path.expanduser("~") == HOME, os.path.expanduser("~")

def emit(k, v):
    print("%s\t%s" % (k, v))

replaced, added = gui_gtk.files_stage_targets()
signals = gui_gtk.foreign_desktop_signals()
emit("replaced_n", len(replaced))
emit("added_n", len(added))
for p in replaced:
    emit("replaced", p)
emit("signals_n", len(signals))
emit("confirm", int(gui_gtk.needs_files_confirmation(replaced, added, signals)))
emit("backups_n", len(gui_gtk.backup_dirs()))

# The two halves of the live-session probe, with the process check stubbed so
# the branch is exercised rather than whatever happens to run on this box.
real_running = gui_gtk._running
os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = "test"
gui_gtk._running = lambda n: n == "Hyprland"
emit("hypr_only_signal",
     int(any("Hyprland session" in s for s in gui_gtk.foreign_desktop_signals())))
gui_gtk._running = lambda n: True          # Hyprland *and* plasmashell
emit("hypr_and_plasma_signal",
     int(any("Hyprland session" in s for s in gui_gtk.foreign_desktop_signals())))
del os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
gui_gtk._running = real_running

win = gui_gtk.ReplicaWindow(gui_gtk._p(".preview-thumb.png"))
win.show_all()
emit("restore_sensitive", int(win.restore.get_sensitive()))

# Which stage selections reach the guard, and what a refusal does. The dialog
# itself is not run here (it would block); confirm_files_stage is recorded.
card = win.cards[0]
calls = []
def fake_confirm(answer):
    def f():
        calls.append(True)
        return answer
    return f

def select(stages):
    for sid, cb in card.checks.items():
        cb.set_active(sid in stages)

for stages, dry, answer, tag in (
        (["files"],              False, True,  "files"),
        (["files"],              True,  True,  "files_dry"),
        (["packages"],           False, True,  "packages"),
        (["packages", "files"],  False, True,  "packages_files"),
        (["files"],              False, False, "files_refused")):
    select(stages)
    win.dry.set_active(dry)
    win.result = None
    del calls[:]
    win.confirm_files_stage = fake_confirm(answer)
    win.on_install()
    emit("guard_" + tag, len(calls))
    emit("result_" + tag, win.result[1] if win.result else "none")

# The dialog's own content: built, not run, and read back as rendered text.
dlg = gui_gtk.ConfirmReplaceDialog(
    win, ["~/.config/hypr/hyprland.lua", "~/.bashrc"], ["~/.icons/X"],
    ["~/.config/omarchy is present, so this looks like an Omarchy desktop."])
def texts(w, out):
    if isinstance(w, Gtk.Label):
        out.append(w.get_text())
    if isinstance(w, Gtk.Container):
        for c in w.get_children():
            texts(c, out)
    return out
emit("dialog_text", " ¶ ".join(texts(dlg, [])).replace("\n", " "))
default = dlg.get_default_widget()
emit("dialog_default", default.get_label() if default is not None else "none")
dlg.destroy()
PY

probe() {   # probe <fake-home> [scripts-dir] ; stdout = key<TAB>value lines
  start_broadway || return 1
  GDK_BACKEND=broadway BROADWAY_DISPLAY=":$DISP" \
    timeout 90 python3 "$TMP/probe.py" "${2:-$REPO/scripts}" "$1" \
    2>"$TMP/err.log"
}
val()  { awk -F'\t' -v k="$2" '$1==k {print $2; exit}' <<<"$1"; }
vals() { awk -F'\t' -v k="$2" '$1==k {print $2}' <<<"$1"; }

# --- scenario 1: a machine with its own config (Miya's case) -----------------
MIYA="$TMP/miya"
mkdir -p "$MIYA/.config/hypr" "$MIYA/.config/omarchy" "$MIYA/.config/autostart"
touch "$MIYA/.bashrc" "$MIYA/.zshrc" "$MIYA/.config/hypr/hyprland.lua"
out="$(probe "$MIYA")"
if [[ -z "$out" ]] || ! grep -q '^dialog_default' <<<"$out"; then
  echo "FAIL: the probe did not finish"; sed 's/^/    /' "$TMP/err.log"; exit 1
fi

echo "=== a machine with its own config (an Omarchy box) ==="
printf '%s\n' "$out" | grep -v '^replaced	' | sed 's/^/    /'
echo "    replaced:"; vals "$out" replaced | sed 's/^/      /'

[[ "$(val "$out" confirm)" == 1 ]] \
  && ok "the confirmation fires when there are files to lose" \
  || no "the confirmation fires when there are files to lose"

replaced_list="$(vals "$out" replaced)"
for want in '~/.bashrc' '~/.zshrc' '~/.config/hypr/hyprland.lua' \
            '~/.config/autostart'; do
  grep -qxF "$want" <<<"$replaced_list" \
    && ok "lists $want" \
    || no "lists $want (the paths Miya lost)"
done

# No drift: every path offered must come from the manifest, so the dialog
# cannot claim a file install.sh does not deploy (or miss one it does).
mapfile -t manifest_rels < <(
  bash -c 'source "$1"
           printf "%s\n" "${HOME_ITEMS[@]}" "${CONFIG_ITEMS[@]}" \
                         "${LOCALSHARE_ITEMS[@]}" "${ICONS_ITEMS[@]}" \
                         "${BIN_ITEMS[@]}" "${PICTURES_ITEMS[@]}"' \
       bash "$REPO/scripts/manifest.sh")
stray=""
while read -r p; do
  [[ -z "$p" ]] && continue
  found=0
  for rel in "${manifest_rels[@]}"; do
    [[ "$p" == */"$rel" ]] && { found=1; break; }
  done
  [[ $found == 1 ]] || stray+=" $p"
done <<<"$replaced_list"
[[ -z "$stray" ]] \
  && ok "every path shown comes from manifest.sh" \
  || no "every path shown comes from manifest.sh (stray:$stray)"

[[ "$(val "$out" signals_n)" -ge 1 ]] \
  && ok "says this is not the machine the snapshot came from" \
  || no "says this is not the machine the snapshot came from"

# --- scenario 2: the manifest is the single source of the list ---------------
# Add an entry to a copy of the manifest and it must appear with no edit to
# gui_gtk.py. Run from a scratch copy of the repo's scripts/ so the real
# manifest is untouched.
FAKEREPO="$TMP/repo"
mkdir -p "$FAKEREPO/scripts" "$FAKEREPO/files/config"
cp "$REPO/scripts/gui_gtk.py" "$FAKEREPO/scripts/"
{ cat "$REPO/scripts/manifest.sh"; echo 'CONFIG_ITEMS+=(jan55-probe-file)'; } \
  > "$FAKEREPO/scripts/manifest.sh"
mkdir -p "$MIYA/.config"
touch "$FAKEREPO/files/config/jan55-probe-file" "$MIYA/.config/jan55-probe-file"
out2="$(probe "$MIYA" "$FAKEREPO/scripts")"
echo
echo "=== the manifest is the only list ==="
vals "$out2" replaced | grep -F 'jan55-probe-file' | sed 's/^/    /'
vals "$out2" replaced | grep -qxF '~/.config/jan55-probe-file' \
  && ok "a path added to manifest.sh appears with no change to gui_gtk.py" \
  || no "a path added to manifest.sh appears with no change to gui_gtk.py"
rm -rf "$FAKEREPO/scripts/__pycache__"

# --- scenario 3: a fresh machine -------------------------------------------
FRESH="$TMP/fresh"
mkdir -p "$FRESH/.config"
out3="$(probe "$FRESH")"
echo
echo "=== a fresh machine (nothing of the user's in the way) ==="
printf '%s\n' "$out3" | grep -v '^replaced	' | sed 's/^/    /'
[[ "$(val "$out3" replaced_n)" == 0 && "$(val "$out3" added_n)" -gt 0 \
   && "$(val "$out3" confirm)" == 0 ]] \
  && ok "no nag on a fresh machine — there is nothing to lose" \
  || no "no nag on a fresh machine — there is nothing to lose"

# --- the stage wiring, the dry-run path and the dialog ----------------------
echo
echo "=== which stages are guarded ==="
printf '%s\n' "$out" | grep -E '^(guard|result|restore_sensitive|hypr|dialog)' \
  | sed 's/^/    /' | cut -c1-160

[[ "$(val "$out" guard_files)" == 1 ]] \
  && ok "the files stage is guarded" \
  || no "the files stage is guarded"
[[ "$(val "$out" guard_packages)" == 0 && "$(val "$out" result_packages)" == packages ]] \
  && ok "packages alone is not guarded, and still runs" \
  || no "packages alone is not guarded, and still runs"
[[ "$(val "$out" guard_packages_files)" == 1 ]] \
  && ok "files alongside another stage is still guarded" \
  || no "files alongside another stage is still guarded"
[[ "$(val "$out" guard_files_dry)" == 0 \
   && "$(val "$out" result_files_dry)" == files ]] \
  && ok "Dry run is not guarded and still previews (JAN-55: do not regress it)" \
  || no "Dry run is not guarded and still previews (JAN-55: do not regress it)"
[[ "$(val "$out" result_files_refused)" == none ]] \
  && ok "saying no to the confirmation installs nothing" \
  || no "saying no to the confirmation installs nothing"

[[ "$(val "$out" hypr_only_signal)" == 1 \
   && "$(val "$out" hypr_and_plasma_signal)" == 0 ]] \
  && ok "a live Hyprland session with no plasmashell is flagged (and KDE is not)" \
  || no "a live Hyprland session with no plasmashell is flagged (and KDE is not)"

dtext="$(val "$out" dialog_text)"
[[ "$dtext" == *"hyprland.lua"* && "$dtext" == *".bashrc"* ]] \
  && ok "the dialog names the paths" \
  || no "the dialog names the paths"
[[ "$dtext" == *"Omarchy desktop"* ]] \
  && ok "the dialog carries the wrong-machine warning" \
  || no "the dialog carries the wrong-machine warning"
[[ "$dtext" == *"config-backup"* && "$dtext" == *"Restore my own settings"* ]] \
  && ok "the dialog points at the backup and the undo" \
  || no "the dialog points at the backup and the undo"
[[ "$(val "$out" dialog_default)" == Cancel ]] \
  && ok "Cancel is the default response (Enter and Escape both back out)" \
  || no "Cancel is the default response (got '$(val "$out" dialog_default)')"

# --- the Restore button ------------------------------------------------------
echo
echo "=== Restore my own settings ==="
[[ "$(val "$out" restore_sensitive)" == 0 && "$(val "$out" backups_n)" == 0 ]] \
  && ok "disabled with no ~/.config-backup-* to restore from" \
  || no "disabled with no ~/.config-backup-* to restore from"

mkdir -p "$MIYA/.config-backup-20261028-093000/.config/hypr"
cp "$MIYA/.config/hypr/hyprland.lua" \
   "$MIYA/.config-backup-20261028-093000/.config/hypr/" 2>/dev/null
out4="$(probe "$MIYA")"
[[ "$(val "$out4" restore_sensitive)" == 1 && "$(val "$out4" backups_n)" == 1 ]] \
  && ok "enabled once a backup exists" \
  || no "enabled once a backup exists"

# The command line gui.sh builds for MODE=restore, run for real against the
# fabricated home. Proves the two halves agree on the argument order.
if HOME="$MIYA" bash "$REPO/scripts/restore-backup.sh" --dry-run \
     "$MIYA/.config-backup-20261028-093000" >"$TMP/restore.log" 2>&1; then
  ok "restore-backup.sh takes the argv gui.sh builds (--dry-run <backup>)"
else
  no "restore-backup.sh takes the argv gui.sh builds (--dry-run <backup>)"
  sed 's/^/      /' "$TMP/restore.log"
fi
bash -n "$REPO/scripts/gui.sh" \
  && ok "gui.sh parses" || no "gui.sh parses"
grep -q 'restore)' "$REPO/scripts/gui.sh" \
  && grep -q 'restore-backup.sh' "$REPO/scripts/gui.sh" \
  && ok "gui.sh routes the restore request to restore-backup.sh" \
  || no "gui.sh routes the restore request to restore-backup.sh"

printf '\n==== %d passed, %d failed ====\n' "$pass" "$fail"
[[ $fail == 0 ]]
