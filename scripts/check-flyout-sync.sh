#!/usr/bin/env bash
# check-flyout-sync.sh — verify the LIVE OpenClaw flyout files match the
# standalone source repo (github.com/janszafranski/openclaw-flyout).
#
# The flyout is no longer vendored in desktop-manager — it lives in its own repo,
# and this profile installs it by cloning that repo. So "sync" now means: do the
# files deployed on this machine match the flyout repo checkout? Point this at a
# local clone via OPENCLAW_FLYOUT_SRC (defaults to the install cache).
#
# Exit 0 = in sync. Exit 1 = drift (prints which). Exit 2 = no source checkout.

set -u
SRC="${OPENCLAW_FLYOUT_SRC:-${XDG_CACHE_HOME:-$HOME/.cache}/desktop-manager/openclaw-flyout}"
# Common alternate: a working clone under ~/src
[[ -d "$SRC" ]] || SRC="$HOME/src/openclaw-flyout"

if [[ ! -d "$SRC" ]]; then
  printf '\033[1;33m!! no flyout source checkout found\033[0m (set OPENCLAW_FLYOUT_SRC)\n'
  printf '   looked in: install cache and ~/src/openclaw-flyout\n'
  exit 2
fi

# live path | source-repo-relative path
MAP=(
  "$HOME/.local/bin/openclaw-ai-bridge.js|bin/openclaw-ai-bridge.js"
  "$HOME/.local/bin/openclaw-cli-chat.sh|bin/openclaw-cli-chat.sh"
  "$HOME/.local/bin/openclaw-dashboard.sh|bin/openclaw-dashboard.sh"
  "$HOME/.config/quickshell/openclaw-sidebar/shell.qml|quickshell/openclaw-sidebar/shell.qml"
  "$HOME/.config/systemd/user/openclaw-ai-bridge.service|systemd/openclaw-ai-bridge.service"
)

printf ':: comparing live files against %s\n' "$SRC"
drift=0
for row in "${MAP[@]}"; do
  live="${row%%|*}"
  rel="${row#*|}"
  repo="$SRC/$rel"
  if [[ ! -e "$live" ]]; then
    printf '\033[1;33m!! MISSING LIVE\033[0m %s\n' "$live"; drift=1; continue
  fi
  if [[ ! -e "$repo" ]]; then
    printf '\033[1;33m!! MISSING SRC \033[0m %s\n' "$rel"; drift=1; continue
  fi
  if diff -q "$live" "$repo" >/dev/null 2>&1; then
    printf '\033[1;32mSYNC \033[0m %s\n' "$rel"
  else
    printf '\033[1;31mDRIFT\033[0m %s\n      live %s\n' "$rel" "$live"; drift=1
  fi
done

if [[ $drift -eq 0 ]]; then
  printf '\n\033[1;32m:: live flyout matches the source repo\033[0m\n'
else
  printf '\n\033[1;31m:: DRIFT — reconcile live <-> %s (commit fixes upstream, then reinstall).\033[0m\n' "$SRC"
fi
exit $drift
