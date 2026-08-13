#!/usr/bin/env bash

set -euo pipefail

FILE="$1"

DIR="$(dirname "$FILE")"
NAME="$(basename "$FILE")"

cd "$DIR"

PROMPT="$(cat ~/Documents/Welcomers/claude_prompt.txt)"

PROMPT="${PROMPT//\{\{FILENAME\}\}/$NAME}"

konsole --hold -e fish -c "
cd \"$DIR\"

claude \
  --allow-dangerously-skip-permissions \
  --permission-mode bypassPermissions \
  \"$PROMPT\"
"
