#!/usr/bin/env bash
# check-webcreator-sync.sh — verify the installed "just a... WEBcreator" matches
# the copy in this repo (profiles/webcreator).
#
# This one is worth having because the app can update *itself*: Help ▸ Check for
# Updates… downloads webcreator.py and replaces the installed file in place. It
# is also what a stray webcreator-update.tar.gz does. Either way the live app
# drifts from the repo without anyone editing anything here.
#
# Exit 0 = in sync (or the app is not installed — nothing to drift).
# Exit 1 = drift; prints which file and which way to reconcile.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")/profiles/webcreator"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"

if [[ ! -e "$DATA/webcreator/webcreator.py" ]]; then
  printf '\033[1;33m!! WEBcreator is not installed\033[0m — nothing to compare.\n'
  printf '   Install it with: %s/install.sh\n' "$REPO"
  exit 0
fi

ver() { sed -n 's/^VERSION = "\([^"]*\)".*/\1/p' "$1" | head -1; }

# live path | repo-relative path
MAP=(
  "$DATA/webcreator/webcreator.py|webcreator.py"
  "$DATA/webcreator/test_webplus_import.py|test_webplus_import.py"
  "$DATA/applications/webcreator.desktop|webcreator.desktop"
  "$DATA/mime/packages/webcreator.xml|webcreator-mime.xml"
)

printf ':: comparing the installed app against %s\n' "$REPO"
drift=0
for row in "${MAP[@]}"; do
  live="${row%%|*}"
  rel="${row#*|}"
  repo="$REPO/$rel"
  if [[ ! -e "$live" ]]; then
    printf '\033[1;33m!! MISSING LIVE\033[0m %s\n' "$live"; drift=1; continue
  fi
  if [[ ! -e "$repo" ]]; then
    printf '\033[1;33m!! MISSING REPO\033[0m %s\n' "$rel"; drift=1; continue
  fi
  # The .desktop is rewritten at install time to carry an absolute Exec path,
  # so compare it with that one line normalised rather than reporting it daily.
  if [[ "$rel" == webcreator.desktop ]]; then
    if diff -q <(sed 's|^Exec=.*/webcreator|Exec=webcreator|' "$live") \
               <(sed 's|^Exec=.*/webcreator|Exec=webcreator|' "$repo") >/dev/null 2>&1; then
      printf '\033[1;32mSYNC \033[0m %s\n' "$rel"; continue
    fi
  elif diff -q "$live" "$repo" >/dev/null 2>&1; then
    printf '\033[1;32mSYNC \033[0m %s\n' "$rel"; continue
  fi
  printf '\033[1;31mDRIFT\033[0m %s\n      live %s\n' "$rel" "$live"
  drift=1
done

lv="$(ver "$DATA/webcreator/webcreator.py")"
rv="$(ver "$REPO/webcreator.py")"
printf ':: version  live %s  repo %s\n' "${lv:-?}" "${rv:-?}"

if [[ $drift -eq 0 ]]; then
  printf '\n\033[1;32m:: the installed app matches this repo\033[0m\n'
else
  printf '\n\033[1;31m:: DRIFT.\033[0m If the live copy is the newer one (it updated itself),\n'
  printf '   copy it back into %s and commit.\n' "$REPO"
  printf '   If the repo is right, reinstall:  %s/install.sh\n' "$REPO"
fi
exit $drift
