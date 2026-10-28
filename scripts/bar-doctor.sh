#!/usr/bin/env bash
# bar-doctor.sh — "my bar disappeared": find out why, and put it back.
#
# Installing a package on Arch/Omarchy with `yay -S something` refreshes the
# package database and can pull in new system libraries. That occasionally
# leaves an unrelated part of your desktop — most often waybar, the bar along
# the top of an Omarchy screen — unable to start. The bar is then simply gone
# at the next login, with no error message anywhere you would look.
#
# This script tells you which of those happened and, when the bar is fine,
# starts it again so you get it back without a reboot.
#
# It never installs, removes or upgrades a package, never edits a config file,
# and never starts or kills a compositor. The only thing it can start is your
# bar; everything else it does is read-only. Commands that need `sudo` are
# printed for you to read, not run.
#
# Usage:
#   ./bar-doctor.sh             # diagnose, and start the bar if it is healthy
#   ./bar-doctor.sh --dry-run   # diagnose only, start nothing
#   ./bar-doctor.sh --log-only  # just show what packages changed recently
#
# Exit status: 0 the bar is up, 1 the bar is broken and the fix is printed,
# 2 could not tell.
set -euo pipefail

PACMAN_LOG="${BAR_DOCTOR_PACMAN_LOG:-/var/log/pacman.log}"
PROBE_SECONDS="${BAR_DOCTOR_PROBE_SECONDS:-5}"
HISTORY_DAYS="${BAR_DOCTOR_HISTORY_DAYS:-3}"
BAR=waybar

DRY=0
LOG_ONLY=0

say()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
good() { printf '\033[1;32mok\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
bad()  { printf '\033[1;31m!!\033[0m %s\n' "$*"; }

usage() { sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)  DRY=1 ;;
    --log-only) LOG_ONLY=1 ;;
    -h|--help)  usage; exit 0 ;;
    *) bad "Unknown option: $1"; usage; exit 2 ;;
  esac
  shift
done

# ---------------------------------------------------------------- package log

# Lines from the last $HISTORY_DAYS days that added, removed or upgraded
# something. A removal is what we care about most: if the bar's package went
# away, that is the whole answer.
package_history() {
  [[ -r "$PACMAN_LOG" ]] || { warn "No readable package log at $PACMAN_LOG."; return 0; }
  local since
  since="$(date -d "-$HISTORY_DAYS days" +%Y-%m-%d 2>/dev/null || true)"
  awk -v since="$since" '
    match($0, /\[[0-9]{4}-[0-9]{2}-[0-9]{2}/) {
      day = substr($0, RSTART + 1, 10)
      if (since != "" && day < since) next
      if ($0 ~ /\[ALPM\] (installed|removed|upgraded) /) print
    }
  ' "$PACMAN_LOG"
}

removed_recently() { package_history | grep -E '\[ALPM\] removed ' || true; }

show_history() {
  local hist
  hist="$(package_history)"
  if [[ -z "$hist" ]]; then
    say "No packages have changed in the last $HISTORY_DAYS days."
    return
  fi
  local n
  n="$(printf '%s\n' "$hist" | wc -l)"
  if (( n > 40 )); then
    say "Packages changed in the last $HISTORY_DAYS days ($n of them, last 40):"
  else
    say "Packages changed in the last $HISTORY_DAYS days:"
  fi
  printf '%s\n' "$hist" | tail -40 | sed 's/^/    /'
}

# ------------------------------------------------------------------- the bar

bar_path()    { command -v "$BAR" 2>/dev/null || true; }
bar_running() { pgrep -x "$BAR" >/dev/null 2>&1; }

# Run the bar for a few seconds and keep whatever it says. `timeout` returns
# 124 when it had to kill it, which here means the bar stayed up: healthy.
probe_output=""
probe_bar() {
  local rc=0
  probe_output="$(timeout "${PROBE_SECONDS}s" "$BAR" 2>&1)" || rc=$?
  return "$rc"
}

classify() {
  local out="$1"
  if grep -qE 'error while loading shared libraries|symbol lookup error|undefined symbol|GLIBC_|not found \(required by|version .* not found' <<<"$out"; then
    echo libraries
  elif grep -qiE 'json|parse|unexpected (token|character|end)|mismatched|config file|configuration' <<<"$out"; then
    echo config
  else
    echo other
  fi
}

start_bar() {
  if [[ $DRY == 1 ]]; then
    say "[dry-run] would start your bar now."
    return 0
  fi
  if command -v omarchy-restart-waybar >/dev/null 2>&1; then
    omarchy-restart-waybar >/dev/null 2>&1 &
  else
    setsid "$BAR" >/dev/null 2>&1 &
  fi
  disown 2>/dev/null || true
  sleep 1
}

print_fix_libraries() {
  bad "Your bar is installed but cannot start: it is linked against system"
  echo "   libraries that have since been replaced by newer ones."
  echo
  echo "   This is what a half-finished system update looks like. Installing one"
  echo "   package with yay can update some libraries and not the programs that"
  echo "   use them. Finishing the update fixes it:"
  echo
  echo "       sudo pacman -Syu"
  echo
  echo "   Say yes to everything, let it finish, then log out and back in."
  echo "   If your bar came from the AUR it also has to be rebuilt:"
  echo
  echo "       yay -S --rebuild $BAR"
}

print_fix_config() {
  bad "Your bar is installed and its libraries are fine, but it starts up,"
  echo "   rejects its own settings and exits. Something in those settings is"
  echo "   no longer valid for the version you now have."
  echo
  if command -v omarchy-refresh-waybar >/dev/null 2>&1; then
    echo "   Omarchy ships a command that puts the stock settings back:"
    echo
    echo "       omarchy-refresh-waybar"
  else
    echo "   Move your bar's settings aside so it falls back to the defaults:"
    echo
    echo "       mv ~/.config/waybar ~/.config/waybar-broken"
  fi
  echo
  echo "   Then run this script again. Send Jan the message above either way —"
  echo "   it says exactly which line it did not like."
}

# ----------------------------------------------------------------------- main

if [[ $LOG_ONLY == 1 ]]; then
  show_history
  exit 0
fi

say "Looking at your bar ($BAR)."

if bar_running; then
  good "It is already running."
  echo "   So the bar itself is alive. If you still cannot see it, it is"
  echo "   probably hidden rather than gone — try moving the mouse to the top"
  echo "   of the screen, or log out and back in."
  echo
  show_history
  exit 0
fi

if [[ -z "$(bar_path)" ]]; then
  removal="$(removed_recently | grep -E "removed $BAR " || true)"
  # Never installed and never removed: this desktop's bar is something other
  # than waybar, which is all this script knows about. Telling the owner of a
  # non-Omarchy desktop to install waybar would be worse than useless.
  if [[ -z "$removal" ]] && ! grep -qE "\[ALPM\] (installed|removed) $BAR " "$PACMAN_LOG" 2>/dev/null; then
    warn "$BAR has never been installed on this machine, so its bar is"
    warn "something else. This script only knows Omarchy's $BAR."
    echo
    show_history
    exit 2
  fi
  bad "$BAR is not installed on this machine any more."
  echo
  if [[ -n "$removal" ]]; then
    echo "   The package log shows when it went:"
    printf '%s\n' "$removal" | sed 's/^/     /'
    echo
    echo "   Something you installed asked to remove it and was told yes."
  fi
  echo "   Putting it back:"
  echo
  echo "       sudo pacman -S $BAR"
  echo
  echo "   Then log out and back in. Send Jan the lines below."
  echo
  show_history
  exit 1
fi

say "Installed at $(bar_path), but not running. Trying to start it, which"
say "takes about $PROBE_SECONDS seconds."

if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
  warn "This terminal is not inside a desktop session (no WAYLAND_DISPLAY),"
  warn "so the bar cannot be started from here."
  warn "Run this from a terminal on your own desktop."
  echo
  show_history
  exit 2
fi

rc=0
probe_bar || rc=$?

if [[ $rc == 124 ]]; then
  good "It starts and stays up — nothing is wrong with the bar itself."
  echo "   It just was not started when you logged in. Starting it now."
  start_bar
  if [[ $DRY == 1 ]]; then
    :
  elif bar_running; then
    good "Your bar is back."
  else
    warn "It did not stay up this time. Log out and back in; if it is still"
    warn "missing, run this script again."
  fi
  echo
  show_history
  exit 0
fi

bad "It exited instead of starting. This is what it said:"
echo
printf '%s\n' "${probe_output:-(it said nothing at all)}" | tail -20 | sed 's/^/     /'
echo

case "$(classify "$probe_output")" in
  libraries) print_fix_libraries ;;
  config)    print_fix_config ;;
  other)
    bad "I cannot tell from that message what is wrong. Send the lines above"
    echo "   to Jan — that message is the answer, and he will recognise it."
    ;;
esac

echo
show_history
exit 1
