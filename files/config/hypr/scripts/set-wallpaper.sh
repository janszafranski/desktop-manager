#!/usr/bin/env bash
# Set the Caelestia wallpaper, keeping the black surfaces.
# Usage: set-wallpaper.sh [image]   (default: Hyprland's "cats" wallpaper)
# The three Hyprland built-in wallpapers live in /usr/share/hypr/wall{0,1,2}.png
# (wall2 = anime girl + cats). These are what you see before the shell loads.
set -euo pipefail
wall="${1:-/usr/share/hypr/wall2.png}"

caelestia wallpaper -f "$wall"

# caelestia re-reads the catppuccin theme colours on a wallpaper change, which
# undoes the black surfaces -- re-apply them (matches install.sh section 2d).
scheme="${XDG_STATE_HOME:-$HOME/.local/state}/caelestia/scheme.json"
python3 - "$scheme" <<'PY'
import json, os, sys, tempfile
p = sys.argv[1]
d = json.load(open(p))
d.setdefault("colours", {}).update({
    "background": "000000", "surface": "000000", "surfaceDim": "000000",
    "surfaceBright": "1a1a1a", "surfaceContainerLowest": "000000",
    "surfaceContainerLow": "0a0a0a", "surfaceContainer": "0d0d0d",
    "surfaceContainerHigh": "141414", "surfaceContainerHighest": "1c1c1c",
    "surfaceVariant": "2a2a2a", "surface0": "121212", "surface1": "1a1a1a",
    "surface2": "222222",
})
fd, t = tempfile.mkstemp(dir=os.path.dirname(p))
os.write(fd, json.dumps(d).encode()); os.close(fd); os.replace(t, p)
PY
echo "Wallpaper: $wall  (black surfaces preserved)"
