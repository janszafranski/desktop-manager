#!/usr/bin/env bash
# install-launcher.sh — add "System Replica" to your application menu.
# Generates a .desktop entry pointing at this repo's gui.sh (absolute path).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$SCRIPT_DIR")"
GUI="$SCRIPT_DIR/gui.sh"
TEMPLATE="$REPO/system-replica.desktop"
DEST="$HOME/.local/share/applications/system-replica.desktop"

chmod +x "$GUI"
mkdir -p "$(dirname "$DEST")"
sed "s|__GUI__|$GUI|g" "$TEMPLATE" > "$DEST"
command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$(dirname "$DEST")" 2>/dev/null || true

echo "Installed launcher: $DEST"
echo "Look for \"System Replica\" in your application menu."
