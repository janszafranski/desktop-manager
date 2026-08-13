#!/usr/bin/env bash
# revert.sh — restore the desktop to the state saved before the macOS profile
# was applied (see restore/state.env and the backed-up config files).
#
# Ordering matters: plasmashell rewrites its config on exit, so we must STOP it
# *before* restoring the panel layout, then start it again — otherwise it saves
# the current (macOS) layout back over the restored file and leaves phantom panels.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$HERE/restore"
# shellcheck source=/dev/null
source "$R/state.env"

echo ":: Re-applying Global Theme: $LOOKANDFEEL"
plasma-apply-lookandfeel -a "$LOOKANDFEEL" 2>/dev/null || true
[[ -n "${COLORSCHEME:-}" ]] && plasma-apply-colorscheme "$COLORSCHEME" 2>/dev/null || true
[[ -n "${CURSOR:-}" ]] && plasma-apply-cursortheme "$CURSOR" 2>/dev/null || true

echo ":: Stopping Plasma shell (so it can't overwrite the restored layout)"
kquitapp6 plasmashell 2>/dev/null || killall plasmashell 2>/dev/null || true
for _ in $(seq 1 40); do pgrep -x plasmashell >/dev/null || break; sleep 0.25; done

echo ":: Restoring config files"
for f in kdeglobals kwinrc kcminputrc plasma-org.kde.plasma.desktop-appletsrc plasmashellrc; do
  [[ -f "$R/$f" ]] && cp -a "$R/$f" ~/.config/"$f" && echo "  <- $f"
done

echo ":: Starting Plasma shell"
(setsid plasmashell >/dev/null 2>&1 &)
qdbus6 org.kde.KWin /KWin reconfigure 2>/dev/null || true

echo ":: Reverted to $LOOKANDFEEL. A logout/login makes it fully clean."
