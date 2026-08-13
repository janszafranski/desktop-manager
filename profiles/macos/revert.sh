#!/usr/bin/env bash
# revert.sh — restore the desktop to the state saved before the macOS profile
# was applied (see restore/state.env and the backed-up config files).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$HERE/restore"
# shellcheck source=/dev/null
source "$R/state.env"

echo ":: Restoring config files"
for f in kdeglobals kwinrc kcminputrc plasma-org.kde.plasma.desktop-appletsrc plasmashellrc; do
  [[ -f "$R/$f" ]] && cp -a "$R/$f" ~/.config/"$f" && echo "  <- $f"
done

echo ":: Re-applying Global Theme: $LOOKANDFEEL"
plasma-apply-lookandfeel -a "$LOOKANDFEEL" --resetLayout 2>/dev/null || \
  plasma-apply-lookandfeel -a "$LOOKANDFEEL" || true
[[ -n "${COLORSCHEME:-}" ]] && plasma-apply-colorscheme "$COLORSCHEME" 2>/dev/null || true
[[ -n "${CURSOR:-}" ]] && plasma-apply-cursortheme "$CURSOR" 2>/dev/null || true

echo ":: Restarting Plasma shell"
kquitapp6 plasmashell 2>/dev/null || true
(setsid plasmashell >/dev/null 2>&1 &) 2>/dev/null || true
qdbus6 org.kde.KWin /KWin reconfigure 2>/dev/null || true

echo ":: Reverted to $LOOKANDFEEL. A logout/login makes it fully clean."
