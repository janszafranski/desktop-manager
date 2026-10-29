#!/usr/bin/env bash
# Tests for scripts/fix-my-bar.sh.
#
# Puts a stub `waybar` and `pgrep` on $PATH so every branch of the diagnosis
# can be driven without a real bar, and stub `pacman`/`yay`/`pkill`/`sudo` that
# fail the test if the script ever calls them. Needs no compositor and changes
# nothing outside its temp directory, so it is safe to run on a live desktop.
#
#   ./scripts/tests/fix-my-bar-test.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$(dirname "$SCRIPT_DIR")")"
SCRIPT="$REPO/scripts/fix-my-bar.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/fix-my-bar-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
ok() { pass=$((pass+1)); printf '  \033[32mok\033[0m   %s\n' "$1"; }
no() { fail=$((fail+1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
check()    { if [[ "$2" == "$3" ]]; then ok "$1"; else no "$1 (got '$3', want '$2')"; fi; }
contains() { if grep -qF -- "$2" <<<"$3"; then ok "$1"; else no "$1 — no '$2' in output"; fi; }
lacks()    { if grep -qF -- "$2" <<<"$3"; then no "$1 — found '$2'"; else ok "$1"; fi; }

BIN="$TMP/bin"
mkdir -p "$BIN" "$TMP/bin-empty"

# --- stubs -------------------------------------------------------------------
cat > "$BIN/waybar" <<'EOF'
#!/usr/bin/env bash
touch "$STUB_MARKERS/waybar-ran"
case "${STUB_WAYBAR_MODE:-up}" in
  up)     sleep 30 ;;
  libs)   echo "waybar: error while loading shared libraries: libfmt.so.11: cannot open shared object file"; exit 127 ;;
  config) echo "waybar: parse error: unexpected token at line 4 of config.jsonc"; exit 1 ;;
  weird)  echo "waybar: something nobody has ever seen before"; exit 3 ;;
esac
EOF
cat > "$BIN/pgrep" <<'EOF'
#!/usr/bin/env bash
exit "${STUB_PGREP_RC:-1}"
EOF
for forbidden in pacman yay pkill sudo; do
  cat > "$BIN/$forbidden" <<EOF
#!/usr/bin/env bash
touch "\$STUB_MARKERS/VIOLATION-$forbidden"
exit 0
EOF
done
cat > "$BIN/setsid" <<'EOF'
#!/usr/bin/env bash
touch "$STUB_MARKERS/bar-started"
EOF
chmod +x "$BIN"/*

# --- a package log with one recent removal and one ancient entry -------------
LOG="$TMP/pacman.log"
today="$(date +%Y-%m-%d)"
old="$(date -d '-40 days' +%Y-%m-%d)"
{
  printf '[%sT09:00:00+0100] [ALPM] installed ancient-thing (1.0-1)\n' "$old"
  printf '[%sT10:00:00+0100] [ALPM] installed quickshell (0.3.2-1.1)\n' "$today"
  printf '[%sT10:00:01+0100] [ALPM] removed waybar (0.15.0-3.1)\n' "$today"
  printf '[%sT10:00:02+0100] [ALPM] upgraded qt6-base (6.11.2-1 -> 6.12.0-1)\n' "$today"
} > "$LOG"

export STUB_MARKERS="$TMP/markers"
mkdir -p "$STUB_MARKERS"

# Every run drives a *copy* of the script sitting on its own in a directory
# with no repository anywhere near it, from a working directory that is not the
# repo either — the way it reaches someone who was sent the one file. If the
# script ever grows a dependency on a sibling file, every case below breaks.
LOOSE="$TMP/downloads/fix-my-bar.sh"
mkdir -p "$TMP/downloads" "$TMP/elsewhere" "$TMP/home"
cp "$SCRIPT" "$LOOSE"
REPORT="$TMP/home/bar-report.txt"

# Run the script against the stubs only. $1 is the stub directory to put first
# on $PATH, the rest are the script's own arguments. Callers set MODE (what the
# stub bar does), PGREP_RC (whether a bar looks like it is running) and
# NO_WAYLAND as prefix assignments.
#
# BASH_ENV is cleared because some environments point it at a file that
# re-exports $PATH, which would undo the stubbing.
run_fix() {
  local stubs="$1"; shift
  local -a wayland=(WAYLAND_DISPLAY=wayland-test)
  [[ "${NO_WAYLAND:-0}" == 1 ]] && wayland=()
  rm -f "$STUB_MARKERS"/* "$REPORT"
  out=""; rc=0
  out="$(cd "$TMP/elsewhere" && env -i -u BASH_ENV \
           PATH="$stubs:/usr/bin:/bin" \
           HOME="$TMP/home" \
           "${wayland[@]}" \
           STUB_MARKERS="$STUB_MARKERS" \
           STUB_WAYBAR_MODE="${MODE:-up}" \
           STUB_PGREP_RC="${PGREP_RC:-1}" \
           FIX_MY_BAR_PACMAN_LOG="$LOG" \
           FIX_MY_BAR_PROBE_SECONDS=1 \
           bash "$LOOSE" "$@" 2>&1)" || rc=$?
}

no_violations() {
  local found
  found="$(find "$STUB_MARKERS" -name 'VIOLATION-*' -printf '%f ' 2>/dev/null)"
  if [[ -z "$found" ]]; then
    ok "$1"
  else
    no "$1 — it ran: $found"
  fi
}

echo "=== one loose file, no repository ==="
# The whole point of this script: someone is sent the single file and runs it.
lacks "refers to no sibling file in the repo" "scripts/" "$(cat "$LOOSE")"
MODE=libs run_fix "$BIN"
contains "works from a directory with no repo in it" "half-finished system update" "$out"
if [[ -s "$REPORT" ]]; then ok "writes the report file"; else no "writes the report file"; fi
contains "says where the report is" "bar-report.txt" "$out"
contains "the report has the diagnosis in it" "libfmt.so.11" "$(cat "$REPORT" 2>/dev/null)"
contains "the report says which machine"     "kernel" "$(cat "$REPORT" 2>/dev/null)"
lacks    "the report has no colour codes"    $'\033[' "$(cat "$REPORT" 2>/dev/null)"
MODE=libs run_fix "$BIN" --no-report
if [[ -e "$REPORT" ]]; then no "--no-report writes nothing"; else ok "--no-report writes nothing"; fi
check "--no-report keeps the exit status" 1 "$rc"

echo "=== --log-only ==="
run_fix "$BIN" --log-only
check    "exits 0" 0 "$rc"
contains "shows today's install" "installed quickshell" "$out"
contains "shows today's removal" "removed waybar" "$out"
contains "shows today's upgrade" "upgraded qt6-base" "$out"
lacks    "hides entries older than the window" "ancient-thing" "$out"
if [[ -e "$STUB_MARKERS/waybar-ran" ]]; then no "does not run the bar"; else ok "does not run the bar"; fi
no_violations "touches no package manager"

echo "=== bar already running ==="
PGREP_RC=0 run_fix "$BIN"
check    "exits 0" 0 "$rc"
contains "says it is already running" "already running" "$out"
contains "still reports the package history" "removed waybar" "$out"
if [[ -e "$STUB_MARKERS/waybar-ran" ]]; then no "does not start a second one"; else ok "does not start a second one"; fi

echo "=== bar not installed ==="
run_fix "$TMP/bin-empty"
check    "exits 1" 1 "$rc"
contains "says it is gone"           "not installed on this machine" "$out"
contains "quotes the removal line"   "removed waybar (0.15.0-3.1)" "$out"
contains "prints the reinstall line" "sudo pacman -S waybar" "$out"
no_violations "prints the sudo command without running it"

echo "=== this desktop's bar was never waybar ==="
# Jan's own machine: no waybar, and no record of one. Must not tell the owner
# of a different desktop to install the bar they do not run.
OTHER_LOG="$TMP/pacman-no-waybar.log"
grep -v waybar "$LOG" > "$OTHER_LOG"
saved_log="$LOG"; LOG="$OTHER_LOG"
run_fix "$TMP/bin-empty"
check    "exits 2 (cannot tell)" 2 "$rc"
contains "says the bar is something else" "its bar is" "$out"
lacks    "does not prescribe waybar"      "sudo pacman -S waybar" "$out"
LOG="$saved_log"

echo "=== bar is healthy, just was not started ==="
MODE=up run_fix "$BIN" --dry-run
check    "exits 0" 0 "$rc"
contains "says the bar itself is fine" "starts and stays up" "$out"
contains "says it would start it"      "[dry-run] would start your bar" "$out"
if [[ -e "$STUB_MARKERS/waybar-ran" ]]; then ok "probed the real binary"; else no "probed the real binary"; fi
if [[ -e "$STUB_MARKERS/bar-started" ]]; then no "dry-run starts nothing"; else ok "dry-run starts nothing"; fi

echo "=== broken libraries ==="
MODE=libs run_fix "$BIN"
check    "exits 1" 1 "$rc"
contains "quotes what the bar said"    "libfmt.so.11" "$out"
contains "names the half-done update"  "half-finished system update" "$out"
contains "prints the full-update fix"  "sudo pacman -Syu" "$out"
lacks    "does not blame the settings" "settings file" "$out"
no_violations "fixes nothing itself"

echo "=== rejected settings ==="
MODE=config run_fix "$BIN"
check    "exits 1" 1 "$rc"
contains "quotes the parse error"     "unexpected token at line 4" "$out"
contains "names the settings file"    "rejects its own settings and exits" "$out"
lacks    "does not prescribe -Syu"    "pacman -Syu" "$out"

echo "=== unrecognised failure ==="
MODE=weird run_fix "$BIN"
check    "exits 1" 1 "$rc"
contains "still quotes the message" "nobody has ever seen before" "$out"
contains "admits it cannot tell"    "cannot tell from that message" "$out"

echo "=== run from outside a desktop session ==="
NO_WAYLAND=1 run_fix "$BIN"
check    "exits 2" 2 "$rc"
contains "says where to run it" "terminal on your own desktop" "$out"
if [[ -e "$STUB_MARKERS/waybar-ran" ]]; then no "does not try to start it headless"; else ok "does not try to start it headless"; fi

echo "=== bad option ==="
run_fix "$BIN" --nonsense
check    "exits 2" 2 "$rc"
contains "shows usage" "Usage:" "$out"

printf '\n==== %d passed, %d failed ====\n' "$pass" "$fail"
[[ $fail == 0 ]]
