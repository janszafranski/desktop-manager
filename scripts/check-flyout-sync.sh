#!/usr/bin/env bash
# check-flyout-sync.sh — verify the OpenClaw AI-flyout critical files are in sync
# between the LIVE system and their hand-maintained copies in this repo.
#
# WHY THIS EXISTS: the flyout system spans files that live OUTSIDE the normal
# collect.sh/manifest.sh backup path (collect.sh writes into files/; these are
# hand-copied into profiles/*/). collect.sh does NOT capture them, so a change
# made live can silently fail to reach the repo (and vice-versa). This script is
# the single source of truth for "are they in sync?" — run it before committing
# flyout work, and after any OpenClaw upgrade that might have clobbered them.
#
# Exit 0 = all in sync. Exit 1 = drift found (prints which, and the diff hint).

set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# live path | repo copies (space-separated, relative to $REPO)
# Keep this table in step with flyout-blank-sqlite-history.md memory.
MAP=(
  "$HOME/.local/bin/openclaw-ai-bridge.js|profiles/end4/openclaw-ai-bridge.js profiles/openclaw-flyout/openclaw-ai-bridge.js profiles/caelestia/openclaw-ai-bridge.js"
  "$HOME/.local/bin/openclaw-cli-chat.sh|profiles/openclaw-flyout/openclaw-cli-chat.sh profiles/caelestia/openclaw-cli-chat.sh"
  "$HOME/.config/quickshell/openclaw-sidebar/shell.qml|profiles/openclaw-flyout/openclaw-sidebar/shell.qml profiles/caelestia/openclaw-sidebar/shell.qml"
)

drift=0
for row in "${MAP[@]}"; do
  live="${row%%|*}"
  copies="${row#*|}"
  if [[ ! -e "$live" ]]; then
    printf '\033[1;33m!! MISSING LIVE\033[0m %s\n' "$live"
    drift=1
    continue
  fi
  for rel in $copies; do
    repo="$REPO/$rel"
    if [[ ! -e "$repo" ]]; then
      printf '\033[1;33m!! MISSING COPY\033[0m %s\n' "$rel"
      drift=1
    elif ! diff -q "$live" "$repo" >/dev/null 2>&1; then
      printf '\033[1;31mDRIFT\033[0m %s\n      vs live %s\n' "$rel" "$live"
      drift=1
    else
      printf '\033[1;32mSYNC \033[0m %s\n' "$rel"
    fi
  done
done

if [[ $drift -eq 0 ]]; then
  printf '\n\033[1;32m:: all flyout files in sync\033[0m\n'
else
  printf '\n\033[1;31m:: DRIFT — copy live -> repo (or repo -> live) before committing.\033[0m\n'
  printf '   e.g.  cp "%s" "%s/%s"\n' "$HOME/.local/bin/openclaw-ai-bridge.js" "$REPO" "profiles/openclaw-flyout/openclaw-ai-bridge.js"
fi
exit $drift
