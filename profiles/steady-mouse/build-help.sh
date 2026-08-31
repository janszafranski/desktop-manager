#!/usr/bin/env bash
# build-help.sh — generate the local HTML help doc from DOCUMENTATION.md.
# DOCUMENTATION.md is the single source of truth; this derives help.html from it
# (with a styled header + an "updates on GitHub" banner). Prefers pandoc, falls
# back to python-markdown (markdown_py). Exits 3 if no converter is available.
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SELF/DOCUMENTATION.md"
OUT="${1:-$HOME/.local/share/steady-mouse/help.html}"
HDR="$SELF/assets/help-header.html"
BAN="$SELF/assets/help-banner.html"
mkdir -p "$(dirname "$OUT")"

if command -v pandoc >/dev/null 2>&1; then
  pandoc "$SRC" -s --metadata title="Steady Mouse — Help" \
    --include-in-header "$HDR" --include-before-body "$BAN" -o "$OUT"
elif command -v markdown_py >/dev/null 2>&1; then
  {
    echo '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    echo '<meta name="viewport" content="width=device-width, initial-scale=1">'
    echo '<title>Steady Mouse — Help</title>'
    cat "$HDR"
    echo '</head><body>'
    cat "$BAN"
    markdown_py -x tables -x fenced_code "$SRC"
    echo '</body></html>'
  } > "$OUT"
else
  echo "build-help: no markdown converter (pandoc / markdown_py) found" >&2
  exit 3
fi
echo "build-help: wrote $OUT"
