#!/usr/bin/env bash
# Tests bin/omarchy-desktop-icons against a stub `qs` that records its argv.
#
# No compositor and no real quickshell: the stub stands in for it, so this is
# safe to run on a live desktop and never puts a surface on the wallpaper.
#
#   ./tests/cli-test.sh
set -uo pipefail

APPDIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/odi-cli-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
check() {
  if [[ "$2" == "$3" ]]; then pass=$((pass+1)); printf '  \033[32mok\033[0m   %s\n' "$1"
  else fail=$((fail+1)); printf '  \033[31mFAIL\033[0m %s\n       want: %s\n        got: %s\n' "$1" "$2" "$3"; fi
}

# The stub logs every call, and fails `ipc call` when RUNNING is unset — which
# is what the real `qs` does ("No running instances", exit 255).
mkdir -p "$TMP/bin"
cat > "$TMP/bin/qs" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$QS_LOG"
for a in "$@"; do
  if [[ "$a" == "ipc" ]]; then
    [[ -n "${RUNNING:-}" ]] && exit 0
    echo "No running instances" >&2
    exit 255
  fi
done
exit 0
STUB
chmod +x "$TMP/bin/qs"
export PATH="$TMP/bin:$PATH"

# Report calls with the app dir collapsed, so assertions stay readable.
QS_LOG="$TMP/log"
calls() { sed "s#$APPDIR#APPDIR#g" "$QS_LOG" | paste -sd'|' -; }

# BASH_ENV is cleared deliberately: some sandboxes point it at a bashrc that
# re-sets PATH for every non-interactive bash, which would send the launcher to
# the real quickshell instead of the stub. Unset on a normal machine.
runcmd() {
  : > "$QS_LOG"
  env -u BASH_ENV PATH="$TMP/bin:$PATH" QS_LOG="$QS_LOG" RUNNING="${RUNNING:-}" \
      "$APPDIR/bin/omarchy-desktop-icons" "$@" >/dev/null 2>&1
}

echo "=== toggle with nothing running (the Desktop Manager button) ==="
unset RUNNING
runcmd toggle
check "tries IPC first, then starts the grid detached" \
      "-p APPDIR ipc call desktop toggle|-p APPDIR --no-duplicate --daemonize" "$(calls)"

echo "=== toggle with the grid already running ==="
RUNNING=1 runcmd toggle
check "just toggles, does not start a second instance" \
      "-p APPDIR ipc call desktop toggle" "$(calls)"

echo "=== the other subcommands are unchanged ==="
RUNNING=1 runcmd start;    check "start runs the config in the foreground" "-p APPDIR --no-duplicate" "$(calls)"
RUNNING=1 runcmd settings; check "settings calls the dialog over IPC" "-p APPDIR ipc call desktop settings" "$(calls)"
RUNNING=1 runcmd open;     check "open calls the overlay over IPC"   "-p APPDIR ipc call desktop open" "$(calls)"
RUNNING=1 runcmd close;    check "close calls the overlay over IPC"  "-p APPDIR ipc call desktop close" "$(calls)"
RUNNING=1 runcmd reload;   check "reload calls the reload handler"   "-p APPDIR ipc call desktop reload" "$(calls)"
RUNNING=1 runcmd stop;     check "stop kills only this config"       "-p APPDIR kill" "$(calls)"

echo "=== version and help need no quickshell at all ==="
check "version prints the shipped revision" "$(cat "$APPDIR/VERSION")" \
      "$("$APPDIR/bin/omarchy-desktop-icons" version 2>/dev/null)"
check "an unknown subcommand is an error" "2" \
      "$("$APPDIR/bin/omarchy-desktop-icons" wat >/dev/null 2>&1; echo $?)"

printf '\n==== %d passed, %d failed ====\n' "$pass" "$fail"
[[ $fail == 0 ]]
